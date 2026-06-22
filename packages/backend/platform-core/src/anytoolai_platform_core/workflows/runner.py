from __future__ import annotations

from dataclasses import replace

from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository


class WorkflowJobService:
    def __init__(self, repository: JobRepository, event_emitter: EventEmitter) -> None:
        self._repository = repository
        self._event_emitter = event_emitter

    def start(self, record: JobRecord) -> JobRecord:
        stored = self._repository.create(record)
        self._event_emitter.emit(
            "workflow.started",
            _context_from_record(stored),
            properties={"workflow_version": stored.workflow_version},
        )
        return stored

    def mark_succeeded(self, record: JobRecord) -> JobRecord:
        updated = self._repository.update(record)
        self._event_emitter.emit(
            "workflow.succeeded",
            _context_from_record(updated),
            result_status=updated.status.value,
            properties={"workflow_version": updated.workflow_version},
        )
        return updated

    def mark_failed(self, record: JobRecord, *, error_code: str) -> JobRecord:
        failed_record = replace(record, status=JobStatus.failed, error_code=error_code)
        updated = self._repository.update(failed_record)
        self._event_emitter.emit(
            "workflow.failed",
            _context_from_record(updated),
            result_status=updated.status.value,
            properties={
                "error_code": error_code,
                "workflow_version": updated.workflow_version,
            },
        )
        return updated


def _context_from_record(record: JobRecord) -> ExecutionContext:
    return ExecutionContext(
        tenant_id=record.tenant_id,
        region=record.region,
        product_id=record.product_id,
        frontend_id=record.frontend_id,
        scenario_session_id=record.scenario_session_id,
        job_id=record.id,
        workflow_id=record.workflow_id,
        workflow_version=record.workflow_version,
    )
