from __future__ import annotations

from dataclasses import asdict

import sqlalchemy as sa
from sqlalchemy.orm import Session

from anytoolai_platform_core.storage.db import jobs_table
from anytoolai_platform_core.workflows.models import JobRecord


class JobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, record: JobRecord) -> JobRecord:
        self._session.execute(sa.insert(jobs_table).values(asdict(record)))
        self._session.flush()
        stored = self.get(record.id)
        assert stored is not None
        return stored

    def get(self, job_id: str) -> JobRecord | None:
        row = (
            self._session.execute(sa.select(jobs_table).where(jobs_table.c.id == job_id))
            .mappings()
            .one_or_none()
        )
        return None if row is None else JobRecord(**dict(row))

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
        assert stored is not None
        return stored
