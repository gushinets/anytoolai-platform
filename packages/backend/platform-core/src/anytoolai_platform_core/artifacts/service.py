from __future__ import annotations

from anytoolai_platform_core.artifacts.models import ArtifactRecord
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter


class ArtifactService:
    def __init__(self, repository: ArtifactRepository, event_emitter: EventEmitter) -> None:
        self._repository = repository
        self._event_emitter = event_emitter

    def create(self, record: ArtifactRecord) -> ArtifactRecord:
        stored = self._repository.create(record)
        self._event_emitter.emit(
            "artifact.created",
            _context_from_record(stored),
            result_status=stored.status.value,
            properties={"artifact_type": stored.artifact_type},
        )
        return stored


def _context_from_record(record: ArtifactRecord) -> ExecutionContext:
    return ExecutionContext(
        tenant_id=record.tenant_id,
        region=record.region,
        product_id=record.product_id,
        frontend_id=record.frontend_id,
        scenario_session_id=record.scenario_session_id,
        job_id=record.job_id,
        artifact_id=record.id,
        action_run_id=record.action_run_id,
    )
