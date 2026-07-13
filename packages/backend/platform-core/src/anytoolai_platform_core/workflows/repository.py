from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, replace
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.storage.db import (
    artifacts_table,
    jobs_table,
    scenario_sessions_table,
)
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus


def _require_stored_job(stored: JobRecord | None, record_id: str, operation: str) -> JobRecord:
    if stored is None:
        raise RuntimeError(f"job round-trip failed after {operation}: {record_id}")
    return stored


class JobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, record: JobRecord) -> JobRecord:
        self._require_valid_scenario_session_link(record)
        self._session.execute(sa.insert(jobs_table).values(asdict(record)))
        self._session.flush()
        stored = self.get(record.id)
        return _require_stored_job(stored, record.id, "create")

    def get(self, job_id: str) -> JobRecord | None:
        row = (
            self._session.execute(sa.select(jobs_table).where(jobs_table.c.id == job_id))
            .mappings()
            .one_or_none()
        )
        return None if row is None else JobRecord(**dict(row))

    def claim_created(
        self,
        job_id: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> JobRecord | None:
        """Claim a created job exactly once within the caller's transaction.

        The conditional update is the coordination primitive for the MVP worker.  A caller must
        commit this transaction before beginning workflow execution so execution rollback cannot
        make the job visible as ``created`` again.
        """

        values: dict[str, Any] = {
            "status": JobStatus.running,
            "started_at": utc_now(),
        }
        if metadata is not None:
            values["metadata"] = dict(metadata)

        result = self._session.execute(
            sa.update(jobs_table)
            .where(
                jobs_table.c.id == job_id,
                jobs_table.c.status == JobStatus.created,
            )
            .values(values)
        )
        if result.rowcount == 0:
            return None
        self._session.flush()
        return _require_stored_job(self.get(job_id), job_id, "claim")

    def cancel_created(self, job_id: str) -> JobRecord | None:
        """Cancel a job before claim without interrupting running work."""

        result = self._session.execute(
            sa.update(jobs_table)
            .where(
                jobs_table.c.id == job_id,
                jobs_table.c.status == JobStatus.created,
            )
            .values(
                status=JobStatus.canceled,
                completed_at=utc_now(),
            )
        )
        if result.rowcount == 0:
            return None
        self._session.flush()
        return _require_stored_job(self.get(job_id), job_id, "cancel")

    def mark_succeeded(self, record: JobRecord) -> JobRecord:
        self._require_valid_success_record(record)
        return self._transition_from_running(record, expected_status=JobStatus.succeeded)

    def mark_failed(self, record: JobRecord) -> JobRecord:
        return self._transition_from_running(
            replace(
                record,
                status=JobStatus.failed,
                error_code=record.error_code or "workflow_execution_failed",
                error_message_safe=(
                    record.error_message_safe or "Workflow execution failed."
                ),
                completed_at=record.completed_at or utc_now(),
            ),
            expected_status=JobStatus.failed,
        )

    def mark_canceled(self, record: JobRecord) -> JobRecord:
        return self._transition_from_running(
            replace(
                record,
                status=JobStatus.canceled,
                completed_at=record.completed_at or utc_now(),
            ),
            expected_status=JobStatus.canceled,
        )

    def mark_failed_from_created(self, record: JobRecord) -> JobRecord:
        return self._transition_from_created(
            replace(
                record,
                status=JobStatus.failed,
                error_code=record.error_code or "workflow_execution_failed",
                error_message_safe=(
                    record.error_message_safe or "Workflow execution failed."
                ),
                completed_at=record.completed_at or utc_now(),
            ),
            expected_status=JobStatus.failed,
        )

    def _transition_from_running(
        self,
        record: JobRecord,
        *,
        expected_status: JobStatus,
    ) -> JobRecord:
        if record.status is not expected_status:
            raise ValueError(
                f"job {record.id} transition requires status={expected_status.value}"
            )

        result = self._session.execute(
            sa.update(jobs_table)
            .where(
                jobs_table.c.id == record.id,
                jobs_table.c.status == JobStatus.running,
            )
            .values(
                status=record.status,
                result_artifact_id=record.result_artifact_id,
                error_code=record.error_code,
                error_message_safe=record.error_message_safe,
                started_at=record.started_at,
                completed_at=record.completed_at,
                metadata=record.metadata,
            )
        )
        if result.rowcount == 0:
            existing = self.get(record.id)
            if existing is None:
                raise LookupError(f"job not found: {record.id}")
            if existing.status is expected_status:
                return existing
            raise RuntimeError(
                f"job {record.id} cannot transition from {existing.status.value} "
                f"to {expected_status.value}"
            )
        self._session.flush()
        return _require_stored_job(self.get(record.id), record.id, "transition")

    def _transition_from_created(
        self,
        record: JobRecord,
        *,
        expected_status: JobStatus,
    ) -> JobRecord:
        if record.status is not expected_status:
            raise ValueError(
                f"job {record.id} transition requires status={expected_status.value}"
            )

        result = self._session.execute(
            sa.update(jobs_table)
            .where(
                jobs_table.c.id == record.id,
                jobs_table.c.status == JobStatus.created,
            )
            .values(
                status=record.status,
                result_artifact_id=record.result_artifact_id,
                error_code=record.error_code,
                error_message_safe=record.error_message_safe,
                started_at=record.started_at,
                completed_at=record.completed_at,
                metadata=record.metadata,
            )
        )
        if result.rowcount == 0:
            existing = self.get(record.id)
            if existing is None:
                raise LookupError(f"job not found: {record.id}")
            if existing.status is expected_status:
                return existing
            raise RuntimeError(
                f"job {record.id} cannot transition from {existing.status.value} "
                f"to {expected_status.value}"
            )
        self._session.flush()
        return _require_stored_job(self.get(record.id), record.id, "transition")

    def update(self, record: JobRecord) -> JobRecord:
        existing = self.get(record.id)
        if existing is None:
            raise LookupError(f"job not found: {record.id}")
        self._require_update_invariants(existing, record)
        values = asdict(record)
        values.pop("id")
        result = self._session.execute(
            sa.update(jobs_table).where(jobs_table.c.id == record.id).values(values)
        )
        if result.rowcount == 0:
            raise LookupError(f"job not found: {record.id}")
        self._session.flush()
        stored = self.get(record.id)
        return _require_stored_job(stored, record.id, "update")

    def _require_valid_scenario_session_link(self, record: JobRecord) -> None:
        if not isinstance(record.scenario_session_id, str) or not record.scenario_session_id:
            raise ValueError("job create requires scenario_session_id")
        linked = self._session.execute(
            sa.select(scenario_sessions_table.c.id)
            .where(
                scenario_sessions_table.c.id == record.scenario_session_id,
                scenario_sessions_table.c.tenant_id == record.tenant_id,
                scenario_sessions_table.c.region == record.region,
                scenario_sessions_table.c.product_id == record.product_id,
                scenario_sessions_table.c.frontend_id == record.frontend_id,
            )
            .limit(1)
        ).scalar_one_or_none()
        if linked is None:
            raise LookupError(
                "job scenario session link is invalid for "
                f"{record.scenario_session_id}"
            )

    def _require_valid_success_record(self, record: JobRecord) -> None:
        artifact_id = record.result_artifact_id
        if not isinstance(artifact_id, str) or not artifact_id:
            raise ValueError(
                f"job {record.id} succeeded transition requires result_artifact_id"
            )
        if record.completed_at is None:
            raise ValueError(f"job {record.id} succeeded transition requires completed_at")

        artifact_row = (
            self._session.execute(
                sa.select(
                    artifacts_table.c.id,
                    artifacts_table.c.job_id,
                    artifacts_table.c.scenario_session_id,
                ).where(artifacts_table.c.id == artifact_id)
            )
            .mappings()
            .one_or_none()
        )
        if artifact_row is None:
            raise LookupError(f"result artifact not found: {artifact_id}")
        if artifact_row["job_id"] != record.id:
            raise ValueError(
                f"job {record.id} result artifact must belong to the same job"
            )
        if artifact_row["scenario_session_id"] != record.scenario_session_id:
            raise ValueError(
                f"job {record.id} result artifact must match scenario_session_id"
            )

    def _require_update_invariants(
        self,
        existing: JobRecord,
        record: JobRecord,
    ) -> None:
        if record.status is not existing.status:
            raise ValueError(
                "job status changes must use repository lifecycle methods"
            )
        immutable_fields = (
            "tenant_id",
            "region",
            "product_id",
            "frontend_id",
            "scenario_session_id",
            "workflow_id",
            "workflow_version",
            "created_at",
        )
        for field_name in immutable_fields:
            if getattr(record, field_name) != getattr(existing, field_name):
                raise ValueError(
                    f"job {record.id} update cannot change immutable field {field_name}"
                )
