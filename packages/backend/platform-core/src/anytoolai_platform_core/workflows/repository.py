from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, replace
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.storage.db import jobs_table
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus


def _require_stored_job(stored: JobRecord | None, record_id: str, operation: str) -> JobRecord:
    if stored is None:
        raise RuntimeError(f"job round-trip failed after {operation}: {record_id}")
    return stored


class JobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, record: JobRecord) -> JobRecord:
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

    def update(self, record: JobRecord) -> JobRecord:
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
