"""Job liveness via Postgres session-scoped advisory locks (no wall-clock TTL).

A job's lease is a single dedicated, AUTOCOMMIT connection held open for exactly as
long as the job runs. If the holding process dies (crash, OOM-kill, SIGKILL, an
unhandled SIGTERM, or a dropped socket), Postgres releases the advisory lock itself
when the session goes away -- no timer, no heartbeat, no guessing at job duration.
`probe_orphaned()` distinguishes "dead" from "alive" by the one fact that matters:
whether the lock can be taken right now.

On non-Postgres backends (SQLite in the fast test suite) there is no advisory-lock
primitive, so `NullJobLease` is a no-op stand-in that never reports a job orphaned.
"""

from __future__ import annotations

import hashlib
import logging
import struct
from typing import Protocol

import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine

logger = logging.getLogger(__name__)


def _advisory_lock_key(job_id: str) -> int:
    """Stable signed 64-bit key for `pg_advisory_lock(bigint)`, derived from job_id.

    A full 64-bit hash (rather than Postgres's 32-bit `hashtext()`) keeps collision
    probability negligible; a collision would only make the reconciliation sweep
    conservatively treat an unrelated job as still-alive for one more pass, since the
    final status transition always keys off the job row's id, never the lock key.
    """
    digest = hashlib.sha256(job_id.encode("utf-8")).digest()[:8]
    return struct.unpack(">q", digest)[0]


class JobLease(Protocol):
    def acquire(self, job_id: str) -> bool:
        """Try to take the lease for job_id.

        Returns False if another worker already holds it -- that is expected
        coordination, not an error, and the caller should skip the job.
        """
        ...

    def release(self, job_id: str) -> None:
        """Release a previously acquired lease. Best-effort; never raises."""
        ...

    def probe_orphaned(self, job_id: str) -> bool:
        """Return True if nobody currently holds the lease for job_id."""
        ...


class NullJobLease:
    """No-op lease for backends without advisory locks (e.g. SQLite in tests)."""

    def acquire(self, job_id: str) -> bool:
        del job_id
        return True

    def release(self, job_id: str) -> None:
        del job_id

    def probe_orphaned(self, job_id: str) -> bool:
        del job_id
        return False


class AdvisoryJobLease:
    """Job liveness backed by Postgres session-scoped advisory locks."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._connections: dict[str, Connection] = {}

    def acquire(self, job_id: str) -> bool:
        connection = self._engine.connect()
        key = _advisory_lock_key(job_id)
        acquired = connection.execute(
            sa.text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
        ).scalar_one()
        if not acquired:
            connection.close()
            return False
        self._connections[job_id] = connection
        return True

    def release(self, job_id: str) -> None:
        connection = self._connections.pop(job_id, None)
        if connection is None:
            return
        key = _advisory_lock_key(job_id)
        try:
            connection.execute(sa.text("SELECT pg_advisory_unlock(:key)"), {"key": key})
        except Exception:
            logger.exception(
                "lease.unlock_failed",
                extra={"event": "lease.unlock_failed", "fields": {"job_id": job_id}},
            )
            connection.invalidate()
            return
        connection.close()

    def probe_orphaned(self, job_id: str) -> bool:
        key = _advisory_lock_key(job_id)
        connection = self._engine.connect()
        try:
            acquired = connection.execute(
                sa.text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
            ).scalar_one()
            if not acquired:
                return False
            try:
                connection.execute(sa.text("SELECT pg_advisory_unlock(:key)"), {"key": key})
            except Exception:
                logger.exception(
                    "lease.probe_unlock_failed",
                    extra={"event": "lease.probe_unlock_failed", "fields": {"job_id": job_id}},
                )
                connection.invalidate()
            return True
        finally:
            connection.close()


def build_job_lease(engine: Engine) -> JobLease:
    """Build the lease for `engine`'s dialect; only Postgres has advisory locks.

    Uses a small dedicated engine/pool rather than `engine` itself: the worker
    processes one job at a time, so exactly one long-held lease connection plus one
    short-lived probe connection (during reconciliation, between jobs) is ever
    needed -- sharing the main ORM pool would risk starving it during a long job.
    """
    if engine.dialect.name != "postgresql":
        return NullJobLease()
    lease_engine = sa.create_engine(
        engine.url,
        future=True,
        pool_size=2,
        max_overflow=0,
        isolation_level="AUTOCOMMIT",
        connect_args={
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
        },
    )
    return AdvisoryJobLease(lease_engine)
