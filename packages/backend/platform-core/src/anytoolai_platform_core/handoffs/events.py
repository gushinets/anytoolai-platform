from __future__ import annotations

from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.handoffs.models import HandoffRecord


def emit_handoff_event(
    event_emitter: EventEmitter,
    event_type: str,
    record: HandoffRecord,
    *,
    scenario_session_id: str | None = None,
    job_id: str | None = None,
    properties: dict[str, object] | None = None,
) -> None:
    target_scenario_session_id = scenario_session_id or record.target_scenario_session_id
    event_properties = {
        **(properties or {}),
        "handoff_id": record.id,
        "handoff_definition_id": record.handoff_definition_id,
        "source_scenario_session_id": record.source_scenario_session_id,
        "target_scenario_session_id": target_scenario_session_id,
        "source_job_id": record.source_job_id,
        "source_artifact_id": record.source_artifact_id,
    }
    event_emitter.emit(
        event_type,
        ExecutionContext(
            tenant_id=record.tenant_id,
            region=record.region,
            product_id=record.target_product_id
            if scenario_session_id
            else record.source_product_id,
            frontend_id=record.target_frontend_id
            if scenario_session_id
            else record.source_frontend_id,
            guest_id=record.accepted_by_guest_id or record.created_by_guest_id,
            scenario_session_id=scenario_session_id or record.source_scenario_session_id,
            scenario_chain_id=record.scenario_chain_id,
            job_id=job_id if job_id is not None else record.source_job_id,
            artifact_id=record.source_artifact_id,
            handoff_id=record.id,
        ),
        result_status=record.status.value,
        properties=event_properties,
    )
