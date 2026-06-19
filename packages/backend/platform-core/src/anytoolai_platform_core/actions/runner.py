from __future__ import annotations

from dataclasses import replace

from anytoolai_platform_core.actions.models import ActionRunRecord, ActionRunStatus
from anytoolai_platform_core.actions.repository import ActionRunRepository
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter


class ActionRunService:
    def __init__(self, repository: ActionRunRepository, event_emitter: EventEmitter) -> None:
        self._repository = repository
        self._event_emitter = event_emitter

    def start(self, record: ActionRunRecord) -> ActionRunRecord:
        stored = self._repository.create(record)
        self._event_emitter.emit("action.started", _context_from_record(stored))
        return stored

    def mark_succeeded(self, record: ActionRunRecord) -> ActionRunRecord:
        updated = self._repository.update(record)
        self._event_emitter.emit(
            "action.succeeded",
            _context_from_record(updated),
            result_status=updated.status.value,
        )
        return updated

    def mark_failed(self, record: ActionRunRecord, *, error_code: str) -> ActionRunRecord:
        failed_record = replace(record, status=ActionRunStatus.failed, error_code=error_code)
        updated = self._repository.update(failed_record)
        self._event_emitter.emit(
            "action.failed",
            _context_from_record(updated),
            result_status=updated.status.value,
            properties={"error_code": error_code},
        )
        return updated


def _context_from_record(record: ActionRunRecord) -> ExecutionContext:
    return ExecutionContext(
        tenant_id=record.tenant_id,
        region=record.region,
        product_id=record.product_id,
        frontend_id=record.frontend_id,
        scenario_session_id=record.scenario_session_id,
        job_id=record.job_id,
        workflow_id=record.workflow_id,
        step_id=record.step_id,
        action_type=record.action_type,
        action_config_id=record.action_config_id,
        action_run_id=record.id,
    )
