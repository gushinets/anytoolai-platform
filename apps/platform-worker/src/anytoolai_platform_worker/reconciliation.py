"""Reconciliation sweep for jobs orphaned by a dead lease-holder.

A `running` job is orphaned iff nobody currently holds its advisory lock -- see
`lease.py` for why that is a fact, not a timestamp comparison. The sweep is bounded
(one page of `running` rows per pass) so a large backlog of orphans cannot stall the
caller; it is meant to be run at worker startup and between jobs, not on a schedule.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

import sqlalchemy as sa
from anytoolai_platform_core.storage.db import jobs_table
from anytoolai_platform_core.storage.transactions import transaction_boundary
from anytoolai_platform_core.workflows.models import JobStatus
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from anytoolai_platform_worker.lease import JobLease, NullJobLease

logger = logging.getLogger(__name__)

_DEFAULT_SWEEP_LIMIT = 100
_Cursor = tuple[Any, str]


class OrphanTerminator(Protocol):
    def terminate_orphaned_job(self, job_id: str) -> None:
        """Move an orphaned `running` job to its terminal failed state. Never raises."""
        ...


class OrphanedRunningJobReconciler:
    """Sweeps `running` jobs, terminating any whose lease-holder is gone."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        lease: JobLease,
        terminator: OrphanTerminator,
        limit: int = _DEFAULT_SWEEP_LIMIT,
    ) -> None:
        self._session_factory = session_factory
        self._lease = lease
        self._terminator = terminator
        self._limit = limit
        # Keyset cursor into the `running` set, kept across calls so a fleet with
        # more than `limit` concurrently-running jobs still gets every job probed
        # eventually, instead of every pass re-selecting the same oldest `limit`
        # rows forever and starving anything sitting behind them.
        self._cursor: _Cursor | None = None

    def reconcile_once(self) -> int:
        """Terminate orphaned `running` jobs found in one bounded pass.

        Returns the number terminated. Two workers sweeping the same orphan
        concurrently is safe: `probe_orphaned_batch` is backed by an exclusive
        Postgres advisory lock, and a second `terminate_orphaned_job` call on an
        already-terminal job is an idempotent no-op.
        """
        job_ids = self._running_job_ids()
        orphaned_ids = self._lease.probe_orphaned_batch(job_ids)
        for job_id in orphaned_ids:
            logger.warning(
                "reconciliation.orphan_detected",
                extra={"event": "reconciliation.orphan_detected", "fields": {"job_id": job_id}},
            )
            self._terminator.terminate_orphaned_job(job_id)
        return len(orphaned_ids)

    def _running_job_ids(self) -> list[str]:
        with transaction_boundary(self._session_factory) as session:
            rows = self._select_running_page(session, after=self._cursor)
            if not rows and self._cursor is not None:
                # The cursor ran off the end of the running set -- wrap back to the
                # start in the same pass, so a fleet at or under `limit` still gets
                # swept every call instead of alternating with an empty one.
                rows = self._select_running_page(session, after=None)
            if rows:
                self._cursor = (rows[-1].started_at, rows[-1].id)
            else:
                self._cursor = None
            return [row.id for row in rows]

    def _select_running_page(
        self,
        session: Session,
        *,
        after: _Cursor | None,
    ) -> list[Any]:
        query = (
            sa.select(jobs_table.c.id, jobs_table.c.started_at)
            .where(jobs_table.c.status == JobStatus.running)
            .order_by(jobs_table.c.started_at, jobs_table.c.id)
            .limit(self._limit)
        )
        if after is not None:
            query = query.where(sa.tuple_(jobs_table.c.started_at, jobs_table.c.id) > after)
        return list(session.execute(query))


def build_job_lease_reconciler(
    engine: Engine,
    *,
    session_factory: sessionmaker[Session],
    lease: JobLease,
    terminator: OrphanTerminator,
) -> OrphanedRunningJobReconciler | None:
    """Build the reconciler for `engine`'s dialect; only Postgres has advisory locks.

    Mirrors `build_job_lease`'s gating: on SQLite there is no orphan detection
    primitive, so reconciliation is skipped entirely rather than running a sweep
    that can never find anything.
    """
    if engine.dialect.name != "postgresql" or isinstance(lease, NullJobLease):
        return None
    return OrphanedRunningJobReconciler(
        session_factory=session_factory,
        lease=lease,
        terminator=terminator,
    )
