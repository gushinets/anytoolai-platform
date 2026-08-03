"""PostgreSQL-only coverage for A-1: advisory-lock lease + orphan reconciliation sweep.

The whole point of the lease design (see `lease.py`) is that liveness is a fact -- does
anyone hold the advisory lock right now -- never a timestamp comparison. These tests exist
to prove exactly that against a real Postgres: a `running` job whose lease connection died
gets reconciled to `failed` immediately, and a `running` job whose lease connection is still
alive is never touched, no matter how long it has been running.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlalchemy as sa
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.workflows.models import JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from anytoolai_platform_worker.composition import build_worker
from anytoolai_platform_worker.lease import _advisory_lock_key
from test_worker_boot import CONFIG_ROOT, FIXTURE_ROOT, _seed_job, _seed_running_job

from tests.db_support import provision_database

pytestmark = [pytest.mark.postgresql, pytest.mark.slow]

REPO_ROOT = Path(__file__).resolve().parents[3]


def _src_roots() -> list[str]:
    """Mirror the repo root `conftest.py`'s sys.path setup for the subprocess below,
    which runs outside pytest and so never goes through that conftest itself."""
    roots: list[str] = []
    for base in (REPO_ROOT / "apps", REPO_ROOT / "packages" / "backend"):
        for child in sorted(base.iterdir()):
            src_dir = child / "src"
            if src_dir.is_dir():
                roots.append(str(src_dir))
    return roots


@pytest.fixture
def db() -> Iterator[tuple[sa.engine.Engine, sa.orm.sessionmaker[sa.orm.Session], str]]:
    with provision_database(
        database_name_prefix="anytoolai_worker_lease_recovery_test",
        skip_reason="PostgreSQL worker lease recovery coverage",
    ) as (engine, _alembic_config, test_url):
        yield engine, build_session_factory(engine), test_url.render_as_string(hide_password=False)


def test_orphaned_job_is_recovered_after_lease_connection_dies(
    db: tuple[sa.engine.Engine, sa.orm.sessionmaker[sa.orm.Session], str],
) -> None:
    engine, session_factory, _database_url = db
    job_id = _seed_running_job(session_factory).id

    # "Worker A" takes the job's lease and then crashes -- `.invalidate()` (not `.close()`)
    # actually discards the underlying DBAPI connection, which is what makes Postgres release
    # the session-scoped advisory lock; `.close()` on a pooled connection would just return it
    # to the pool and keep the lock held, silently defeating this whole test.
    holder_connection = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    key = _advisory_lock_key(job_id)
    acquired = holder_connection.execute(
        sa.text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
    ).scalar_one()
    assert acquired is True
    holder_connection.invalidate()

    # "Worker B": a fresh, fully-composed production worker against the same database.
    worker = build_worker(session_factory=session_factory, config_root=CONFIG_ROOT)
    assert worker._reconciler is not None
    try:
        terminated = worker._reconciler.reconcile_once()
    finally:
        worker.dispose()

    assert terminated == 1
    with transaction_boundary(session_factory) as session:
        job = JobRepository(session).get(job_id)
        assert job is not None
        scenario = ScenarioSessionRepository(session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
    assert job.status is JobStatus.failed
    assert job.error_code == "worker_lease_lost"
    assert scenario is not None
    assert scenario.status.value == "failed"

    # The lock is free again -- reconciliation must not leak it.
    probe_connection = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        reacquired = probe_connection.execute(
            sa.text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
        ).scalar_one()
        assert reacquired is True
        probe_connection.execute(sa.text("SELECT pg_advisory_unlock(:key)"), {"key": key})
    finally:
        probe_connection.close()


def test_running_job_with_live_lease_is_never_touched_by_sweep(
    db: tuple[sa.engine.Engine, sa.orm.sessionmaker[sa.orm.Session], str],
) -> None:
    engine, session_factory, _database_url = db
    job_id = _seed_running_job(session_factory).id

    # "Worker A" is alive and still holds the lease -- the connection is deliberately kept
    # open for the whole test. There is no TTL to wait out: however long this job has been
    # `running`, the sweep must leave it alone as long as this lock is held.
    holder_connection = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    key = _advisory_lock_key(job_id)
    try:
        acquired = holder_connection.execute(
            sa.text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
        ).scalar_one()
        assert acquired is True

        worker = build_worker(session_factory=session_factory, config_root=CONFIG_ROOT)
        assert worker._reconciler is not None
        try:
            terminated = worker._reconciler.reconcile_once()
        finally:
            worker.dispose()

        assert terminated == 0
        with transaction_boundary(session_factory) as session:
            job = JobRepository(session).get(job_id)
        assert job is not None
        assert job.status is JobStatus.running
    finally:
        holder_connection.execute(sa.text("SELECT pg_advisory_unlock(:key)"), {"key": key})
        holder_connection.close()


_SUBPROCESS_WORKER_SCRIPT = """
import asyncio
import signal
import sys
from pathlib import Path

from anytoolai_platform_worker.composition import build_worker
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter

class SlowFakeProviderAdapter:
    def __init__(self, fixture_root):
        self._delegate = FakeProviderAdapter(fixture_root)

    async def complete(self, request):
        await asyncio.sleep(2.0)
        return await self._delegate.complete(request)

async def run():
    worker = build_worker(
        database_url={database_url!r},
        config_root=Path({config_root!r}),
        provider_adapters={{"fake": SlowFakeProviderAdapter(Path({fixture_root!r}))}},
        poll_interval_seconds=0.1,
    )
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, worker.request_shutdown)
    await worker.run_forever()

asyncio.run(run())
"""


@pytest.mark.skipif(os.name != "posix", reason="SIGTERM drain is POSIX-only")
def test_real_sigterm_drains_inflight_job_before_exiting(
    db: tuple[sa.engine.Engine, sa.orm.sessionmaker[sa.orm.Session], str],
) -> None:
    _engine, session_factory, database_url = db
    job = _seed_job(
        session_factory,
        input_payload={"source_text": "deadline budget deliverables"},
    )

    script = _SUBPROCESS_WORKER_SCRIPT.format(
        database_url=database_url,
        config_root=str(CONFIG_ROOT),
        fixture_root=str(FIXTURE_ROOT),
    )
    # The subprocess doesn't go through pytest's rootdir conftest.py, which is what
    # normally puts the editable `*/src` packages on sys.path -- so it needs its own
    # PYTHONPATH to see `anytoolai_platform_worker` et al.
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(_src_roots())}
    process = subprocess.Popen([sys.executable, "-c", script], env=env)
    try:
        _wait_for_job_status(session_factory, job.id, JobStatus.running, timeout_seconds=10)
        os.kill(process.pid, signal.SIGTERM)
        returncode = process.wait(timeout=15)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    assert returncode == 0
    with transaction_boundary(session_factory) as session:
        stored = JobRepository(session).get(job.id)
    assert stored is not None
    assert stored.status is JobStatus.succeeded


def _wait_for_job_status(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    job_id: str,
    status: JobStatus,
    *,
    timeout_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        with transaction_boundary(session_factory) as session:
            job = JobRepository(session).get(job_id)
        if job is not None and job.status is status:
            return
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not reach status {status} within {timeout_seconds}s")
