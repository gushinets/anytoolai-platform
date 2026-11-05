from __future__ import annotations

from dataclasses import replace
from enum import StrEnum

from sqlalchemy.orm import Session

from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.quotas.models import (
    ConsumptionReadback,
    ExecutionReservation,
    PaidAllowanceUsageRecord,
    QuotaUnit,
)
from anytoolai_platform_core.quotas.readback import read_consumption


class ExecutionQuotaEvent(StrEnum):
    reserved = "quota.reserved"
    consumed = "quota.consumed"
    released = "quota.released"
    capacity_reserved = "quota.capacity_reserved"


def emit_execution_quota_event(
    session: Session,
    event_type: ExecutionQuotaEvent,
    reservation: ExecutionReservation,
    context: ExecutionContext,
) -> None:
    bucket_id = reservation.guest_quota_usage_id
    if bucket_id is None:
        bucket_id = reservation.paid_allowance_usage_id
    if bucket_id is None:
        raise RuntimeError("reservation lacks its original bucket")
    state = read_consumption(session, reservation.owner, bucket_id)
    if state is None:
        raise RuntimeError("reservation lacks its owned usage bucket")
    _emit_bucket_quota_event(
        session,
        event_type,
        state,
        replace(context, artifact_id=reservation.result_artifact_id),
        properties={"reservation_id": reservation.id, "scenario_id": reservation.scenario_id},
        result_status=reservation.state.value,
    )


def emit_capacity_reserved(
    session: Session,
    state: ConsumptionReadback,
    context: ExecutionContext,
    scenario_id: str,
) -> None:
    _emit_bucket_quota_event(
        session,
        ExecutionQuotaEvent.capacity_reserved,
        state,
        context,
        properties={"scenario_id": scenario_id, "error_code": "quota_capacity_reserved"},
        result_status="failed",
    )


def _emit_bucket_quota_event(
    session: Session,
    event_type: ExecutionQuotaEvent,
    state: ConsumptionReadback,
    context: ExecutionContext,
    *,
    properties: dict[str, object],
    result_status: str,
) -> None:
    properties.update(
        {
            "owner_kind": state.owner.owner_kind.value,
            "owner_id": state.owner.owner_id,
            "quantity": state.quantity,
            "used_count": state.used,
            "successful_used_count": state.successful_used,
            "legacy_used_count": state.legacy_used,
            "reserved_count": state.reserved,
            "remaining_count": state.remaining,
            "available_count": state.available,
            "exhausted": state.remaining == 0,
        }
    )
    bucket = state.bucket
    if isinstance(bucket, PaidAllowanceUsageRecord):
        properties.update(
            paid_allowance_usage_id=bucket.id,
            allowance_id=bucket.allowance.allowance_id,
            metric_key=bucket.allowance.metric_key,
            unit=bucket.allowance.unit,
        )
    else:
        properties.update(
            guest_quota_usage_id=bucket.id,
            quota_policy_id=bucket.quota_policy_id,
            quota_dimension=bucket.quota_dimension.value,
            quota_dimension_key=bucket.dimension_key,
            period_key=bucket.period_key,
            unit=QuotaUnit.scenario_run.value,
        )
    EventEmitter(EventLogRepository(session)).emit(
        event_type,
        context,
        result_status=result_status,
        properties=properties,
        timestamp=state.read_at,
    )
