"""Minimal DB-backed job discovery; external queue transport is out of scope for MVP-A."""

from dataclasses import dataclass

import sqlalchemy as sa
from anytoolai_platform_core.storage.db import jobs_table
from anytoolai_platform_core.storage.transactions import transaction_boundary
from anytoolai_platform_core.workflows.models import JobStatus
from sqlalchemy.orm import Session, sessionmaker


@dataclass(frozen=True)
class WorkflowJobMessage:
    job_id: str


class DatabaseJobQueue:
    """Find created jobs; conditional claim remains the worker coordination primitive."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def next_message(self) -> WorkflowJobMessage | None:
        with transaction_boundary(self._session_factory) as session:
            job_id = session.execute(
                sa.select(jobs_table.c.id)
                .where(jobs_table.c.status == JobStatus.created)
                .order_by(jobs_table.c.created_at, jobs_table.c.id)
                .limit(1)
            ).scalar_one_or_none()
        return None if job_id is None else WorkflowJobMessage(job_id=job_id)
