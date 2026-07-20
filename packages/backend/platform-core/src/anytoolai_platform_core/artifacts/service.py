from __future__ import annotations

from typing import Any

from anytoolai_platform_core.artifacts.models import ArtifactRecord, ArtifactStatus
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.events.replay import ReplayTimestampSequencer
from anytoolai_platform_core.storage.transactions import (
    RollbackRecoveryPhase,
    register_rollback_recovery_callback,
    transaction_boundary,
)


class ArtifactService:
    def __init__(self, repository: ArtifactRepository, event_emitter: EventEmitter) -> None:
        self._repository = repository
        self._session = repository.session
        self._event_emitter = event_emitter

    def create(self, record: ArtifactRecord) -> ArtifactRecord:
        stored = self._repository.create(record)
        self._register_recovery(stored)
        self._event_emitter.emit(
            "artifact.created",
            _context_from_record(stored),
            result_status=stored.status.value,
            properties={"artifact_type": stored.artifact_type},
        )
        return stored

    def _register_recovery(self, record: ArtifactRecord) -> None:
        register_rollback_recovery_callback(
            self._session,
            lambda recovery_session_factory: _recover_artifact_row_after_rollback(
                recovery_session_factory,
                record,
            ),
            phase=RollbackRecoveryPhase.artifact_rows,
        )
        register_rollback_recovery_callback(
            self._session,
            lambda recovery_session_factory: _recover_artifact_events_after_rollback(
                recovery_session_factory,
                record.id,
            ),
            phase=RollbackRecoveryPhase.artifact_events,
        )

    def create_structured_output_artifact(
        self,
        *,
        tenant_id: str,
        region: str,
        product_id: str,
        frontend_id: str,
        scenario_session_id: str,
        job_id: str | None,
        action_run_id: str | None,
        content_json: dict[str, object],
        metadata: dict[str, object] | None = None,
    ) -> ArtifactRecord:
        return self.create(
            ArtifactRecord(
                tenant_id=tenant_id,
                region=region,
                product_id=product_id,
                frontend_id=frontend_id,
                scenario_session_id=scenario_session_id,
                job_id=job_id,
                action_run_id=action_run_id,
                artifact_type="structured_output",
                status=ArtifactStatus.stored,
                content_json=content_json,
                metadata={} if metadata is None else dict(metadata),
            )
        )

    def create_structured_output_debug_artifact(
        self,
        *,
        tenant_id: str,
        region: str,
        product_id: str,
        frontend_id: str,
        scenario_session_id: str,
        job_id: str | None,
        action_run_id: str | None,
        raw_output_text: str,
        metadata: dict[str, object] | None = None,
    ) -> ArtifactRecord:
        return self.create(
            ArtifactRecord(
                tenant_id=tenant_id,
                region=region,
                product_id=product_id,
                frontend_id=frontend_id,
                scenario_session_id=scenario_session_id,
                job_id=job_id,
                action_run_id=action_run_id,
                artifact_type="structured_output_debug_raw",
                status=ArtifactStatus.failed,
                content_text=raw_output_text,
                metadata={} if metadata is None else dict(metadata),
            )
        )


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


def _recover_artifact_row_after_rollback(
    recovery_session_factory: Any,
    record: ArtifactRecord,
) -> None:
    with transaction_boundary(recovery_session_factory) as recovery_session:
        repository = ArtifactRepository(recovery_session)

        existing = repository.get(record.id)
        if existing is None:
            repository.create(record)
            return

        repository.update(record)


def _recover_artifact_events_after_rollback(
    recovery_session_factory: Any,
    artifact_id: str,
) -> None:
    with transaction_boundary(recovery_session_factory) as recovery_session:
        repository = ArtifactRepository(recovery_session)
        stored = repository.get(artifact_id)
        if stored is None:
            return
        _emit_recovered_artifact_created_event(
            EventLogRepository(recovery_session),
            stored,
        )


def _emit_recovered_artifact_created_event(
    event_log_repository: EventLogRepository,
    record: ArtifactRecord,
    *,
    timestamp_sequencer: ReplayTimestampSequencer | None = None,
) -> None:
    existing_timestamp = event_log_repository.event_timestamp(
        event_type="artifact.created",
        artifact_id=record.id,
    )
    if existing_timestamp is not None:
        if timestamp_sequencer is not None:
            timestamp_sequencer.observe(existing_timestamp)
        return
    EventEmitter(event_log_repository).emit(
        "artifact.created",
        _context_from_record(record),
        result_status=record.status.value,
        properties={"artifact_type": record.artifact_type},
        timestamp=(
            record.created_at
            if timestamp_sequencer is None
            else timestamp_sequencer.next(record.created_at)
        ),
        replay=True,
    )
