from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.handoffs.events import emit_handoff_event
from anytoolai_platform_core.handoffs.repository import HandoffRepository
from anytoolai_platform_core.quotas.execution_repository import (
    ExecutionReservationRepository,
    PaidAllowanceConflictError,
    PaidAllowanceUsageRepository,
)
from anytoolai_platform_core.quotas.models import (
    ExecutionAcceptance,
    ExecutionCandidate,
    ExecutionOwner,
    ExecutionOwnerKind,
    ExecutionReservation,
    PaidAllowance,
)
from anytoolai_platform_core.quotas.service import (
    GuestQuotaService,
    QuotaCapacityReservedError,
    QuotaExhaustedError,
    QuotaValidation,
)
from anytoolai_platform_core.storage.db import event_log_table
from anytoolai_platform_core.storage.transactions import (
    RollbackRecoveryPhase,
    SessionFactory,
    register_rollback_recovery_callback,
    transaction_boundary,
)


class PaidAllowanceInvalidError(PlatformError):
    def __init__(self) -> None:
        super().__init__("paid_allowance_invalid", "Paid allowance does not match execution.")


class PaidAllowanceBindingConflictError(PlatformError):
    def __init__(self) -> None:
        super().__init__("paid_allowance_conflict", "Paid allowance binding cannot change.")


class ExecutionReservationService:
    """Admission only. Every write belongs to the caller's Session and savepoint."""

    def __init__(self, registry: ConfigRegistry, guest_quota: GuestQuotaService | None) -> None:
        self._registry = registry
        self._guest_quota = guest_quota

    def validate_paid_allowance(
        self, owner: ExecutionOwner, product_id: str, allowance: PaidAllowance
    ) -> None:
        product = self._registry.get_product(product_id)
        if allowance.owner != owner or allowance.product_id != product_id or product is None:
            raise PaidAllowanceInvalidError()
        metric = next(
            (
                metric
                for metric in product.usage_metrics
                if metric.metric_key == allowance.metric_key
            ),
            None,
        )
        # Commercial enabled/freshness/grant decisions are owned by ANY-766.
        if metric is None or metric.unit != allowance.unit:
            raise PaidAllowanceInvalidError()

    def reserve_execution(
        self,
        session: Session,
        owner: ExecutionOwner,
        execution: ExecutionCandidate,
        quota_input: QuotaValidation | PaidAllowance,
    ) -> ExecutionAcceptance:
        scenario, job = execution.session, execution.job
        context = ExecutionContext(
            tenant_id=owner.tenant_id,
            region=owner.region,
            product_id=scenario.product_id,
            frontend_id=scenario.frontend_id,
            scenario_session_id=scenario.id,
            scenario_chain_id=scenario.scenario_chain_id,
            job_id=job.id,
            guest_id=owner.owner_id if owner.owner_kind is ExecutionOwnerKind.guest else None,
            user_id=owner.owner_id if owner.owner_kind is ExecutionOwnerKind.portal_user else None,
            handoff_id=execution.handoff_id,
        )
        if isinstance(quota_input, PaidAllowance):
            self.validate_paid_allowance(owner, scenario.product_id, quota_input)
            paid = PaidAllowanceUsageRepository(session)
            try:
                bucket = paid.ensure_usage(quota_input)
            except PaidAllowanceConflictError as exc:
                raise PaidAllowanceBindingConflictError() from exc
            bucket_link = {"paid_allowance_usage_id": bucket.id}
        else:
            if owner.owner_kind is not ExecutionOwnerKind.guest or self._guest_quota is None:
                raise ValueError("guest quota requires a guest owner and guest quota service")
            bucket = self._guest_quota.ensure_execution_usage(
                tenant_id=owner.tenant_id,
                region=owner.region,
                product_id=scenario.product_id,
                guest_id=owner.owner_id,
                validation=quota_input,
            )
            bucket_link = {"guest_quota_usage_id": bucket.id}
        replay = execution.replay_identity
        reservation = ExecutionReservationRepository(session).create(
            ExecutionReservation(
                owner=owner,
                scenario_session_id=scenario.id,
                job_id=job.id,
                product_id=scenario.product_id,
                scenario_id=scenario.scenario_id,
                frontend_id=scenario.frontend_id,
                replay_namespace=None if replay is None else replay.namespace,
                replay_key=None if replay is None else replay.replay_key,
                request_hash=execution.request_hash,
                handoff_id=execution.handoff_id,
                **bucket_link,
            )
        )
        # Claim replay uniqueness before competing for capacity. The caller rolls back all
        # candidate rows on the losing unique race, then reads the original execution.
        if isinstance(quota_input, PaidAllowance):
            if not paid.reserve_if_available(bucket):
                latest = paid.get(
                    tenant_id=owner.tenant_id,
                    region=owner.region,
                    allowance_id=quota_input.allowance_id,
                )
                if latest is None:
                    raise RuntimeError("paid bucket disappeared during admission")
                if latest.used_count < latest.allowance.quantity:
                    raise QuotaCapacityReservedError()
                register_rollback_recovery_callback(
                    session,
                    lambda factory: _recover_paid_exhaustion(factory, quota_input, context),
                    phase=RollbackRecoveryPhase.quota_exhaustion,
                    critical=execution.handoff_id is not None,
                )
                raise QuotaExhaustedError()
            EventEmitter(EventLogRepository(session)).emit(
                "quota.checked",
                context,
                properties={
                    "owner_kind": owner.owner_kind.value,
                    "owner_id": owner.owner_id,
                    "paid_allowance_usage_id": bucket.id,
                    "allowance_id": quota_input.allowance_id,
                    "metric_key": quota_input.metric_key,
                    "unit": quota_input.unit,
                },
            )
        else:
            self._guest_quota.reserve_for_accepted_start(
                tenant_id=owner.tenant_id,
                region=owner.region,
                product_id=scenario.product_id,
                frontend_id=scenario.frontend_id,
                guest_id=owner.owner_id,
                scenario_id=scenario.scenario_id,
                scenario_session_id=scenario.id,
                scenario_chain_id=scenario.scenario_chain_id,
                handoff_id=execution.handoff_id,
                validation=quota_input,
                usage=bucket,
            )
        return ExecutionAcceptance(
            scenario_session_id=scenario.id,
            job_id=job.id,
            status=scenario.status,
            reservation=reservation,
        )


def _recover_paid_exhaustion(
    factory: SessionFactory, allowance: PaidAllowance, context: ExecutionContext
) -> None:
    with transaction_boundary(factory) as session:
        handoff = None
        if context.handoff_id is not None:
            transition = HandoffRepository(session).finalize_quota_failure_recovery(
                context.handoff_id,
                tenant_id=context.tenant_id,
                region=context.region,
                error_code="quota_exhausted",
                now=utc_now(),
            )
            if not transition.changed:
                event_types = set(
                    session.execute(
                        sa.select(event_log_table.c.event_type).where(
                            event_log_table.c.tenant_id == context.tenant_id,
                            event_log_table.c.region == context.region,
                            event_log_table.c.handoff_id == context.handoff_id,
                            event_log_table.c.user_id == allowance.owner.owner_id,
                        )
                    ).scalars()
                )
                if {"quota.checked", "quota.exhausted"}.issubset(event_types):
                    return
                raise RuntimeError("paid handoff exhaustion recovery lost terminal arbitration")
            handoff = transition.record
        bucket = PaidAllowanceUsageRepository(session).ensure_usage(allowance)
        emitter = EventEmitter(EventLogRepository(session))
        properties = {
            "owner_kind": allowance.owner.owner_kind.value,
            "owner_id": allowance.owner.owner_id,
            "paid_allowance_usage_id": bucket.id,
            "allowance_id": allowance.allowance_id,
            "metric_key": allowance.metric_key,
            "unit": allowance.unit,
            "error_code": "quota_exhausted",
        }
        emitter.emit("quota.checked", context, properties=properties)
        emitter.emit("quota.exhausted", context, result_status="failed", properties=properties)
        if handoff is not None:
            emit_handoff_event(
                emitter, "handoff.failed", handoff, properties={"error_code": "quota_exhausted"}
            )
