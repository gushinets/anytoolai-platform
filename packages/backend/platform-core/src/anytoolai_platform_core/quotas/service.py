from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.handoffs.repository import HandoffRepository
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.identity.service import GuestIdentityNotFoundError
from anytoolai_platform_core.quotas.models import (
    QuotaDimension,
    QuotaPeriod,
    QuotaPolicy,
    QuotaState,
    QuotaUsageRecord,
)
from anytoolai_platform_core.quotas.repository import QuotaUsageRepository
from anytoolai_platform_core.storage.transactions import (
    RollbackRecoveryPhase,
    register_rollback_recovery_callback,
    transaction_boundary,
)


class ProductNotFoundError(PlatformError):
    def __init__(self) -> None:
        super().__init__("product_not_found", "Product not found.")


class GuestIdentityRequiredError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "guest_identity_required",
            "Guest identity is required for this product.",
        )


class QuotaPolicyNotConfiguredError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "quota_policy_not_configured",
            "Quota policy is not configured for this product.",
        )


class QuotaExhaustedError(PlatformError):
    def __init__(self) -> None:
        super().__init__("quota_exhausted", "Guest quota exhausted.")


class QuotaDimensionRequiredError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "quota_dimension_required",
            "Scenario identity is required for this quota policy.",
        )


@dataclass(frozen=True)
class ResolvedQuotaDimension:
    quota_dimension: QuotaDimension
    dimension_key: str
    scenario_id: str | None


@dataclass(frozen=True)
class QuotaExhaustionRecovery:
    tenant_id: str
    region: str
    product_id: str
    frontend_id: str
    guest_id: str
    scenario_id: str
    scenario_session_id: str | None
    scenario_chain_id: str | None
    handoff_id: str | None
    policy: QuotaPolicy
    dimension: ResolvedQuotaDimension


class GuestQuotaService:
    def __init__(
        self,
        *,
        config_registry: ConfigRegistry,
        quota_repository: QuotaUsageRepository,
        guest_repository: GuestIdentityRepository,
        event_emitter: EventEmitter,
    ) -> None:
        self._config_registry = config_registry
        self._quota_repository = quota_repository
        self._guest_repository = guest_repository
        self._event_emitter = event_emitter

    def check_quota(
        self,
        *,
        tenant_id: str,
        region: str,
        product_id: str,
        guest_id: str,
        scenario_id: str | None = None,
        frontend_id: str = "",
        emit_event: bool = True,
        persist_usage: bool = True,
    ) -> QuotaState:
        policy = self._require_product_quota_policy(product_id)
        dimension = _resolve_dimension(
            policy=policy,
            product_id=product_id,
            scenario_id=scenario_id,
        )
        self._require_guest(
            guest_id,
            tenant_id=tenant_id,
            region=region,
        )
        usage = self._get_usage(
            tenant_id=tenant_id,
            region=region,
            guest_id=guest_id,
            product_id=product_id,
            policy=policy,
            dimension=dimension,
        )
        if usage is None and persist_usage:
            usage = self._ensure_usage(
                tenant_id=tenant_id,
                region=region,
                guest_id=guest_id,
                product_id=product_id,
                policy=policy,
                dimension=dimension,
            )
        state = (
            _state_from_usage(usage, policy)
            if usage is not None
            else _state_from_empty_usage(
                guest_id=guest_id,
                product_id=product_id,
                policy=policy,
                dimension=dimension,
            )
        )
        if emit_event:
            self._emit_quota_event(
                "quota.checked",
                state=state,
                tenant_id=tenant_id,
                region=region,
                frontend_id=frontend_id,
            )
        return state

    def consume_for_accepted_start(
        self,
        *,
        tenant_id: str,
        region: str,
        product_id: str,
        frontend_id: str,
        guest_id: str | None,
        scenario_id: str,
        scenario_session_id: str | None = None,
        scenario_chain_id: str | None = None,
        handoff_id: str | None = None,
    ) -> QuotaState | None:
        product = self._config_registry.get_product(product_id)
        if product is None:
            raise ProductNotFoundError()
        if not product.quota_policy_ref:
            return None
        if not guest_id:
            raise GuestIdentityRequiredError()

        policy = self._require_quota_policy(product.quota_policy_ref)
        dimension = _resolve_dimension(
            policy=policy,
            product_id=product_id,
            scenario_id=scenario_id,
        )
        self._require_guest(
            guest_id,
            tenant_id=tenant_id,
            region=region,
        )
        usage = self._ensure_usage(
            tenant_id=tenant_id,
            region=region,
            guest_id=guest_id,
            product_id=product_id,
            policy=policy,
            dimension=dimension,
        )
        checked_state = _state_from_usage(usage, policy)
        context_kwargs = {
            "tenant_id": tenant_id,
            "region": region,
            "frontend_id": frontend_id,
            "scenario_id": scenario_id,
            "scenario_session_id": scenario_session_id,
            "scenario_chain_id": scenario_chain_id,
            "handoff_id": handoff_id,
        }
        self._emit_quota_event(
            "quota.checked",
            state=checked_state,
            **context_kwargs,
        )

        consumed = self._quota_repository.consume_if_available(usage)
        if consumed is None:
            latest = self._quota_repository.get(usage.id) or usage
            exhausted_state = _state_from_usage(latest, policy)
            self._emit_quota_event(
                "quota.exhausted",
                state=exhausted_state,
                result_status="failed",
                error_code="quota_exhausted",
                **context_kwargs,
            )
            self._register_exhaustion_recovery(
                QuotaExhaustionRecovery(
                    tenant_id=tenant_id,
                    region=region,
                    product_id=product_id,
                    frontend_id=frontend_id,
                    guest_id=guest_id,
                    scenario_id=scenario_id,
                    scenario_session_id=scenario_session_id,
                    scenario_chain_id=scenario_chain_id,
                    handoff_id=handoff_id,
                    policy=policy,
                    dimension=dimension,
                )
            )
            raise QuotaExhaustedError()

        consumed_state = _state_from_usage(consumed, policy)
        self._emit_quota_event(
            "quota.consumed",
            state=consumed_state,
            result_status="accepted",
            **context_kwargs,
        )
        return consumed_state

    def _register_exhaustion_recovery(
        self,
        recovery: QuotaExhaustionRecovery,
    ) -> None:
        register_rollback_recovery_callback(
            self._quota_repository.session,
            lambda recovery_session_factory: _recover_quota_exhaustion(
                recovery_session_factory,
                config_registry=self._config_registry,
                recovery=recovery,
            ),
            phase=RollbackRecoveryPhase.quota_exhaustion,
        )

    def _require_product_quota_policy(self, product_id: str) -> QuotaPolicy:
        product = self._config_registry.get_product(product_id)
        if product is None:
            raise ProductNotFoundError()
        if not product.quota_policy_ref:
            raise QuotaPolicyNotConfiguredError()
        return self._require_quota_policy(product.quota_policy_ref)

    def _require_quota_policy(self, quota_policy_ref: str) -> QuotaPolicy:
        policy = self._config_registry.get_quota_policy(quota_policy_ref)
        if policy is None:
            raise QuotaPolicyNotConfiguredError()
        return policy

    def _require_guest(
        self,
        guest_id: str,
        *,
        tenant_id: str,
        region: str,
    ) -> None:
        guest = self._guest_repository.get(
            guest_id,
            tenant_id=tenant_id,
            region=region,
        )
        if guest is None:
            raise GuestIdentityNotFoundError()

    def _ensure_usage(
        self,
        *,
        tenant_id: str,
        region: str,
        guest_id: str,
        product_id: str,
        policy: QuotaPolicy,
        dimension: ResolvedQuotaDimension,
    ) -> QuotaUsageRecord:
        return self._quota_repository.ensure_usage(
            tenant_id=tenant_id,
            region=region,
            guest_id=guest_id,
            product_id=product_id,
            quota_policy_id=policy.quota_policy_id,
            quota_dimension=dimension.quota_dimension,
            dimension_key=dimension.dimension_key,
            scenario_id=dimension.scenario_id,
            period_key=_period_key(policy),
            limit_count=policy.limit_count,
            metadata={
                "unit": policy.unit.value,
                "period": policy.period.value,
                "quota_dimension": dimension.quota_dimension.value,
                "dimension_key": dimension.dimension_key,
            },
        )

    def _get_usage(
        self,
        *,
        tenant_id: str,
        region: str,
        guest_id: str,
        product_id: str,
        policy: QuotaPolicy,
        dimension: ResolvedQuotaDimension,
    ) -> QuotaUsageRecord | None:
        return self._quota_repository.get_by_dimension(
            tenant_id=tenant_id,
            region=region,
            guest_id=guest_id,
            product_id=product_id,
            quota_policy_id=policy.quota_policy_id,
            quota_dimension=dimension.quota_dimension,
            dimension_key=dimension.dimension_key,
            period_key=_period_key(policy),
        )

    def _emit_quota_event(
        self,
        event_type: str,
        *,
        state: QuotaState,
        tenant_id: str,
        region: str,
        frontend_id: str = "",
        scenario_id: str | None = None,
        scenario_session_id: str | None = None,
        scenario_chain_id: str | None = None,
        handoff_id: str | None = None,
        result_status: str | None = None,
        error_code: str | None = None,
    ) -> None:
        properties = {
            "quota_policy_id": state.quota_policy_id,
            "quota_dimension": state.quota_dimension.value,
            "quota_dimension_key": state.dimension_key,
            "unit": state.unit.value,
            "period": state.period.value,
            "period_key": state.period_key,
            "limit_count": state.limit_count,
            "used_count": state.used_count,
            "remaining_count": state.remaining_count,
            "exhausted": state.exhausted,
        }
        if state.scenario_id is not None:
            properties["quota_scenario_id"] = state.scenario_id
        if scenario_id is not None:
            properties["scenario_id"] = scenario_id
        if error_code is not None:
            properties["error_code"] = error_code

        self._event_emitter.emit(
            event_type,
            ExecutionContext(
                tenant_id=tenant_id,
                region=region,
                product_id=state.product_id,
                frontend_id=frontend_id,
                guest_id=state.guest_id,
                scenario_session_id=scenario_session_id,
                scenario_chain_id=scenario_chain_id,
                handoff_id=handoff_id,
            ),
            result_status=result_status,
            properties=properties,
        )


def _recover_quota_exhaustion(
    recovery_session_factory: sessionmaker[Session],
    *,
    config_registry: ConfigRegistry,
    recovery: QuotaExhaustionRecovery,
) -> None:
    with transaction_boundary(recovery_session_factory) as session:
        if recovery.handoff_id is not None:
            handoffs = HandoffRepository(session)
            handoff = handoffs.get_by_id(
                recovery.handoff_id,
                tenant_id=recovery.tenant_id,
                region=recovery.region,
            )
            if handoff is not None and not handoffs.reserve_quota_failure_recovery(
                handoff.id,
                error_code="quota_exhausted",
                now=utc_now(),
            ):
                return
        quota_repository = QuotaUsageRepository(session)
        usage = quota_repository.ensure_usage(
            tenant_id=recovery.tenant_id,
            region=recovery.region,
            guest_id=recovery.guest_id,
            product_id=recovery.product_id,
            quota_policy_id=recovery.policy.quota_policy_id,
            quota_dimension=recovery.dimension.quota_dimension,
            dimension_key=recovery.dimension.dimension_key,
            scenario_id=recovery.dimension.scenario_id,
            period_key=_period_key(recovery.policy),
            limit_count=recovery.policy.limit_count,
            metadata={
                "unit": recovery.policy.unit.value,
                "period": recovery.policy.period.value,
                "quota_dimension": recovery.dimension.quota_dimension.value,
                "dimension_key": recovery.dimension.dimension_key,
            },
        )
        state = _state_from_usage(usage, recovery.policy)
        service = GuestQuotaService(
            config_registry=config_registry,
            quota_repository=quota_repository,
            guest_repository=GuestIdentityRepository(session),
            event_emitter=EventEmitter(EventLogRepository(session)),
        )
        context = {
            "tenant_id": recovery.tenant_id,
            "region": recovery.region,
            "frontend_id": recovery.frontend_id,
            "scenario_id": recovery.scenario_id,
            "scenario_session_id": recovery.scenario_session_id,
            "scenario_chain_id": recovery.scenario_chain_id,
            "handoff_id": recovery.handoff_id,
        }
        service._emit_quota_event("quota.checked", state=state, **context)
        service._emit_quota_event(
            "quota.exhausted",
            state=state,
            result_status="failed",
            error_code="quota_exhausted",
            **context,
        )


def _state_from_usage(record: QuotaUsageRecord, policy: QuotaPolicy) -> QuotaState:
    remaining_count = max(record.limit_count - record.used_count, 0)
    return QuotaState(
        guest_id=record.guest_id,
        product_id=record.product_id,
        quota_policy_id=record.quota_policy_id,
        quota_dimension=record.quota_dimension,
        dimension_key=record.dimension_key,
        scenario_id=record.scenario_id,
        unit=policy.unit,
        period=policy.period,
        period_key=record.period_key,
        limit_count=record.limit_count,
        used_count=record.used_count,
        remaining_count=remaining_count,
        exhausted=remaining_count <= 0,
    )


def _state_from_empty_usage(
    *,
    guest_id: str,
    product_id: str,
    policy: QuotaPolicy,
    dimension: ResolvedQuotaDimension,
) -> QuotaState:
    return QuotaState(
        guest_id=guest_id,
        product_id=product_id,
        quota_policy_id=policy.quota_policy_id,
        quota_dimension=dimension.quota_dimension,
        dimension_key=dimension.dimension_key,
        scenario_id=dimension.scenario_id,
        unit=policy.unit,
        period=policy.period,
        period_key=_period_key(policy),
        limit_count=policy.limit_count,
        used_count=0,
        remaining_count=policy.limit_count,
        exhausted=policy.limit_count <= 0,
    )


def _resolve_dimension(
    *,
    policy: QuotaPolicy,
    product_id: str,
    scenario_id: str | None,
) -> ResolvedQuotaDimension:
    if policy.dimension is QuotaDimension.product:
        return ResolvedQuotaDimension(
            quota_dimension=QuotaDimension.product,
            dimension_key=product_id,
            scenario_id=None,
        )
    if policy.dimension is QuotaDimension.scenario:
        if not scenario_id:
            raise QuotaDimensionRequiredError()
        return ResolvedQuotaDimension(
            quota_dimension=QuotaDimension.scenario,
            dimension_key=scenario_id,
            scenario_id=scenario_id,
        )
    raise QuotaPolicyNotConfiguredError()


def _period_key(policy: QuotaPolicy) -> str:
    if policy.period is QuotaPeriod.lifetime:
        return "lifetime"
    raise QuotaPolicyNotConfiguredError()
