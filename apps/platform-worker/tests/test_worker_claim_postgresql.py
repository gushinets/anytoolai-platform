from __future__ import annotations

import asyncio
import threading
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory
from anytoolai_platform_core.actions.models import ActionRunStatus
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.providers.models import (
    ProviderCallStatus,
    ProviderResponse,
    ResolvedProviderRequest,
)
from anytoolai_platform_core.scenarios.checkpoints import (
    FAILED_CHECKPOINT_ID,
    RESULT_READY_CHECKPOINT_ID,
)
from anytoolai_platform_core.scenarios.models import (
    ScenarioSessionRecord,
    ScenarioSessionStatus,
)
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.db import (
    PLATFORM_SCHEMA,
    action_runs_table,
    artifacts_table,
    create_sync_engine,
    event_log_table,
    jobs_table,
    provider_calls_table,
    runtime_tables,
)
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from anytoolai_platform_core.workflows.runner import SequentialWorkflowRunner
from anytoolai_platform_worker.composition import build_worker
from anytoolai_platform_worker.queues import DatabaseJobQueue
from anytoolai_platform_worker.worker import Worker
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker
from tests.db_support import provision_database

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "provider" / "fake_provider_outputs"
_UNSAFE_PROVIDER_TEXT = "unsafe internal provider text secret_token=should-not-persist"

pytestmark = [pytest.mark.postgresql, pytest.mark.slow]


@dataclass(frozen=True)
class PollAttempt:
    worker_name: str
    job_id: str | None


@dataclass(frozen=True)
class ClaimAttempt:
    worker_name: str
    backend_pid: int
    claimed: bool
    returned_status: JobStatus | None


@dataclass(frozen=True)
class RunnerInvocation:
    worker_name: str
    job_id: str


@dataclass(frozen=True)
class ProviderInvocation:
    worker_name: str
    job_id: str
    action_run_id: str


class RecordingProviderAdapter:
    def __init__(self) -> None:
        self._delegate = FakeProviderAdapter(FIXTURE_ROOT)
        self._lock = threading.Lock()
        self.calls: list[ProviderInvocation] = []

    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse:
        with self._lock:
            self.calls.append(
                ProviderInvocation(
                    worker_name=threading.current_thread().name,
                    job_id=request.job_id,
                    action_run_id=request.action_run_id,
                )
            )
        return await self._delegate.complete(request)


class FailingProviderAdapter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.calls: list[ProviderInvocation] = []

    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse:
        with self._lock:
            self.calls.append(
                ProviderInvocation(
                    worker_name=threading.current_thread().name,
                    job_id=request.job_id,
                    action_run_id=request.action_run_id,
                )
            )
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider=request.provider,
            model=request.model,
            output_text=_UNSAFE_PROVIDER_TEXT,
            status=ProviderCallStatus.failed,
            error_code="provider_request_failed",
            error_type="TestProviderFailure",
            error_message_safe=_UNSAFE_PROVIDER_TEXT,
            failure_kind="response_failure",
        )


def _scenario(**metadata: Any) -> ScenarioSessionRecord:
    return ScenarioSessionRecord(
        tenant_id="tenant_demo",
        region="eu-central",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_id="kernel_demo.single_action_smoke_v1",
        scenario_version=1,
        guest_id="guest_demo",
        user_id="user_demo",
        scenario_chain_id="scenario_chain_demo",
        metadata=metadata,
    )


def _job(scenario_session_id: str) -> JobRecord:
    return JobRecord(
        tenant_id="tenant_demo",
        region="eu-central",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_session_id=scenario_session_id,
        workflow_id="kernel_demo.single_action_extract_v1",
        workflow_version=1,
    )


def _seed_job(
    session_factory: sessionmaker[Session],
    *,
    input_payload: Mapping[str, Any],
) -> JobRecord:
    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).create(
            _scenario(input=dict(input_payload))
        )
        return JobRepository(session).create(_job(scenario.id))


def _assert_migrations_applied(engine: sa.Engine, alembic_config: Config) -> None:
    expected_head = ScriptDirectory.from_config(alembic_config).get_current_head()
    required_tables = {
        "scenario_sessions",
        "jobs",
        "action_runs",
        "provider_calls",
        "artifacts",
        "event_log",
    }

    with engine.connect() as connection:
        version = connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        table_names = set(sa.inspect(connection).get_table_names(schema=PLATFORM_SCHEMA))

    assert version == expected_head
    assert required_tables.issubset(table_names)
    assert required_tables.issubset(runtime_tables.keys())


def _install_contention_spies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    job_id: str,
) -> tuple[list[PollAttempt], list[ClaimAttempt], list[RunnerInvocation]]:
    lock = threading.Lock()
    barrier = threading.Barrier(2, timeout=20)
    poll_attempts: list[PollAttempt] = []
    claim_attempts: list[ClaimAttempt] = []
    runner_invocations: list[RunnerInvocation] = []

    original_next_message = DatabaseJobQueue.next_message
    original_claim_created = JobRepository.claim_created
    original_run_claimed_job = SequentialWorkflowRunner.run_claimed_job

    def next_message_with_recording(self: DatabaseJobQueue) -> Any:
        message = original_next_message(self)
        with lock:
            poll_attempts.append(
                PollAttempt(
                    worker_name=threading.current_thread().name,
                    job_id=None if message is None else message.job_id,
                )
            )
        return message

    def claim_created_with_barrier(
        self: JobRepository,
        claimed_job_id: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> JobRecord | None:
        if claimed_job_id != job_id:
            return original_claim_created(self, claimed_job_id, metadata=metadata)

        backend_pid = self._session.execute(sa.text("SELECT pg_backend_pid()")).scalar_one()
        barrier.wait()
        claimed = original_claim_created(self, claimed_job_id, metadata=metadata)
        with lock:
            claim_attempts.append(
                ClaimAttempt(
                    worker_name=threading.current_thread().name,
                    backend_pid=backend_pid,
                    claimed=claimed is not None,
                    returned_status=None if claimed is None else claimed.status,
                )
            )
        return claimed

    async def run_claimed_job_with_recording(
        self: SequentialWorkflowRunner,
        job: JobRecord,
        input_payload: Mapping[str, Any],
        context: Any,
    ) -> Any:
        with lock:
            runner_invocations.append(
                RunnerInvocation(
                    worker_name=threading.current_thread().name,
                    job_id=job.id,
                )
            )
        return await original_run_claimed_job(self, job, input_payload, context)

    monkeypatch.setattr(DatabaseJobQueue, "next_message", next_message_with_recording)
    monkeypatch.setattr(JobRepository, "claim_created", claim_created_with_barrier)
    monkeypatch.setattr(
        SequentialWorkflowRunner,
        "run_claimed_job",
        run_claimed_job_with_recording,
    )
    return poll_attempts, claim_attempts, runner_invocations


def _build_independent_workers(
    database_url: URL,
    provider_adapter: Any,
) -> tuple[sa.Engine, sa.Engine, Worker, Worker]:
    rendered_url = database_url.render_as_string(hide_password=False)
    engine_a = create_sync_engine(rendered_url, pool_size=1, max_overflow=0)
    engine_b = create_sync_engine(rendered_url, pool_size=1, max_overflow=0)
    registry = build_config_registry(CONFIG_ROOT)
    worker_a = build_worker(
        session_factory=build_session_factory(engine_a),
        config_registry=registry,
        provider_adapters={"fake": provider_adapter},
        poll_interval_seconds=0.01,
    )
    worker_b = build_worker(
        session_factory=build_session_factory(engine_b),
        config_registry=registry,
        provider_adapters={"fake": provider_adapter},
        poll_interval_seconds=0.01,
    )
    return engine_a, engine_b, worker_a, worker_b


def _process_workers_concurrently(worker_a: Worker, worker_b: Worker) -> dict[str, JobRecord | None]:
    results: dict[str, JobRecord | None] = {}
    errors: dict[str, BaseException] = {}
    lock = threading.Lock()

    def run_worker(worker: Worker) -> None:
        worker_name = threading.current_thread().name
        try:
            result = asyncio.run(worker.process_next_job())
        except BaseException as exc:  # noqa: BLE001 - preserve worker-thread failures for pytest.
            with lock:
                errors[worker_name] = exc
        else:
            with lock:
                results[worker_name] = result

    threads = [
        threading.Thread(target=run_worker, args=(worker_a,), name="worker-a"),
        threading.Thread(target=run_worker, args=(worker_b,), name="worker-b"),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    alive = [thread.name for thread in threads if thread.is_alive()]
    if alive:
        pytest.fail(f"worker contention smoke hung: {alive}")
    if errors:
        error_lines = ", ".join(f"{name}: {error!r}" for name, error in errors.items())
        pytest.fail(f"worker contention smoke raised in thread: {error_lines}")

    assert set(results) == {"worker-a", "worker-b"}
    return results


def _runtime_rows(
    session_factory: sessionmaker[Session],
    *,
    job_id: str,
) -> dict[str, Any]:
    with transaction_boundary(session_factory) as session:
        stored_job = dict(
            session.execute(sa.select(jobs_table).where(jobs_table.c.id == job_id))
            .mappings()
            .one()
        )
        scenario = ScenarioSessionRepository(session).get(
            stored_job["scenario_session_id"],
            tenant_id=stored_job["tenant_id"],
            region=stored_job["region"],
            product_id=stored_job["product_id"],
            frontend_id=stored_job["frontend_id"],
        )
        action_runs = [
            dict(row)
            for row in session.execute(
                sa.select(action_runs_table).where(action_runs_table.c.job_id == job_id)
            ).mappings()
        ]
        provider_calls = [
            dict(row)
            for row in session.execute(
                sa.select(provider_calls_table).where(provider_calls_table.c.job_id == job_id)
            ).mappings()
        ]
        artifacts = [
            dict(row)
            for row in session.execute(
                sa.select(artifacts_table).where(artifacts_table.c.job_id == job_id)
            ).mappings()
        ]
        events = [
            dict(row)
            for row in session.execute(
                sa.select(event_log_table)
                .where(event_log_table.c.job_id == job_id)
                .order_by(event_log_table.c.timestamp, event_log_table.c.event_id)
            ).mappings()
        ]

    assert scenario is not None
    return {
        "job": stored_job,
        "scenario": scenario,
        "action_runs": action_runs,
        "provider_calls": provider_calls,
        "artifacts": artifacts,
        "events": events,
    }


def _assert_single_claim_execution(
    *,
    job: JobRecord,
    poll_attempts: list[PollAttempt],
    claim_attempts: list[ClaimAttempt],
    runner_invocations: list[RunnerInvocation],
    provider_calls: list[ProviderInvocation],
) -> str:
    assert len(poll_attempts) == 2
    assert {attempt.worker_name for attempt in poll_attempts} == {"worker-a", "worker-b"}
    assert [attempt.job_id for attempt in poll_attempts].count(job.id) == 2

    assert len(claim_attempts) == 2
    assert {attempt.worker_name for attempt in claim_attempts} == {"worker-a", "worker-b"}
    assert len({attempt.backend_pid for attempt in claim_attempts}) == 2
    assert sum(1 for attempt in claim_attempts if attempt.claimed) == 1
    assert sum(1 for attempt in claim_attempts if not attempt.claimed) == 1

    winner = next(attempt.worker_name for attempt in claim_attempts if attempt.claimed)
    loser = next(attempt.worker_name for attempt in claim_attempts if not attempt.claimed)
    claimed_attempt = next(attempt for attempt in claim_attempts if attempt.claimed)
    assert claimed_attempt.returned_status is JobStatus.running
    assert next(attempt for attempt in claim_attempts if not attempt.claimed).returned_status is None

    assert len(runner_invocations) == 1
    assert runner_invocations[0].worker_name == winner
    assert runner_invocations[0].job_id == job.id
    assert runner_invocations[0].worker_name != loser

    assert len(provider_calls) == 1
    assert provider_calls[0].worker_name == winner
    assert provider_calls[0].job_id == job.id
    return winner


def test_two_postgresql_workers_claim_one_job_success_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with provision_database(
        database_name_prefix="anytoolai_worker_claim_test",
        skip_reason="PostgreSQL worker claim concurrency smoke",
    ) as (seed_engine, alembic_config, database_url):
        _assert_migrations_applied(seed_engine, alembic_config)
        seed_factory = build_session_factory(seed_engine)
        job = _seed_job(
            seed_factory,
            input_payload={"source_text": "deadline budget deliverables"},
        )
        poll_attempts, claim_attempts, runner_invocations = _install_contention_spies(
            monkeypatch,
            job_id=job.id,
        )
        adapter = RecordingProviderAdapter()
        engine_a, engine_b, worker_a, worker_b = _build_independent_workers(
            database_url,
            adapter,
        )

        try:
            _process_workers_concurrently(worker_a, worker_b)
            winner = _assert_single_claim_execution(
                job=job,
                poll_attempts=poll_attempts,
                claim_attempts=claim_attempts,
                runner_invocations=runner_invocations,
                provider_calls=adapter.calls,
            )
            rows = _runtime_rows(seed_factory, job_id=job.id)
        finally:
            engine_a.dispose()
            engine_b.dispose()

    stored_job = rows["job"]
    scenario = rows["scenario"]
    action_runs = rows["action_runs"]
    provider_calls = rows["provider_calls"]
    artifacts = rows["artifacts"]
    event_counts = Counter(row["event_type"] for row in rows["events"])

    assert stored_job["status"] is JobStatus.succeeded
    assert stored_job["completed_at"] is not None
    assert stored_job["result_artifact_id"] is not None
    assert stored_job["error_code"] is None
    assert stored_job["error_message_safe"] is None
    assert scenario.status is ScenarioSessionStatus.completed
    assert scenario.current_checkpoint_id == RESULT_READY_CHECKPOINT_ID

    assert len(action_runs) == 1
    assert action_runs[0]["status"] is ActionRunStatus.succeeded
    assert action_runs[0]["scenario_session_id"] == job.scenario_session_id
    assert len(provider_calls) == 1
    assert provider_calls[0]["status"] is ProviderCallStatus.succeeded
    assert provider_calls[0]["action_run_id"] == action_runs[0]["id"]
    assert provider_calls[0]["scenario_session_id"] == job.scenario_session_id

    assert len(artifacts) == 2
    assert {artifact["scenario_session_id"] for artifact in artifacts} == {
        job.scenario_session_id
    }
    assert {artifact["job_id"] for artifact in artifacts} == {job.id}
    final_artifacts = [
        artifact for artifact in artifacts if artifact["id"] == stored_job["result_artifact_id"]
    ]
    assert len(final_artifacts) == 1
    assert final_artifacts[0]["action_run_id"] is None
    action_artifacts = [
        artifact for artifact in artifacts if artifact["action_run_id"] == action_runs[0]["id"]
    ]
    assert len(action_artifacts) == 1

    assert event_counts["workflow.started"] == 1
    assert event_counts["workflow.succeeded"] == 1
    assert event_counts["workflow.failed"] == 0
    assert event_counts["action.started"] == 1
    assert event_counts["action.succeeded"] == 1
    assert event_counts["action.failed"] == 0
    assert event_counts["provider.request_started"] == 1
    assert event_counts["provider.request_succeeded"] == 1
    assert event_counts["provider.request_failed"] == 0
    assert event_counts["artifact.created"] == len(artifacts)
    assert event_counts["scenario.completed"] == 1

    assert adapter.calls[0].worker_name == winner


def test_two_postgresql_workers_claim_one_job_failure_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with provision_database(
        database_name_prefix="anytoolai_worker_claim_failure_test",
        skip_reason="PostgreSQL worker claim failure concurrency smoke",
    ) as (seed_engine, alembic_config, database_url):
        _assert_migrations_applied(seed_engine, alembic_config)
        seed_factory = build_session_factory(seed_engine)
        job = _seed_job(
            seed_factory,
            input_payload={"source_text": "deadline budget deliverables"},
        )
        poll_attempts, claim_attempts, runner_invocations = _install_contention_spies(
            monkeypatch,
            job_id=job.id,
        )
        adapter = FailingProviderAdapter()
        engine_a, engine_b, worker_a, worker_b = _build_independent_workers(
            database_url,
            adapter,
        )

        try:
            _process_workers_concurrently(worker_a, worker_b)
            winner = _assert_single_claim_execution(
                job=job,
                poll_attempts=poll_attempts,
                claim_attempts=claim_attempts,
                runner_invocations=runner_invocations,
                provider_calls=adapter.calls,
            )
            rows = _runtime_rows(seed_factory, job_id=job.id)
        finally:
            engine_a.dispose()
            engine_b.dispose()

    stored_job = rows["job"]
    scenario = rows["scenario"]
    action_runs = rows["action_runs"]
    provider_calls = rows["provider_calls"]
    artifacts = rows["artifacts"]
    event_counts = Counter(row["event_type"] for row in rows["events"])

    assert stored_job["status"] is JobStatus.failed
    assert stored_job["completed_at"] is not None
    assert stored_job["result_artifact_id"] is None
    assert stored_job["error_code"] == "provider_request_failed"
    assert stored_job["error_message_safe"] == "Provider request failed."
    assert _UNSAFE_PROVIDER_TEXT not in stored_job["error_message_safe"]
    assert "secret_token" not in stored_job["error_message_safe"]
    assert scenario.status is ScenarioSessionStatus.failed
    assert scenario.current_checkpoint_id == FAILED_CHECKPOINT_ID

    assert len(action_runs) == 1
    assert action_runs[0]["status"] is ActionRunStatus.failed
    assert action_runs[0]["error_code"] == "provider_request_failed"
    assert action_runs[0]["scenario_session_id"] == job.scenario_session_id
    assert len(provider_calls) == 1
    assert provider_calls[0]["status"] is ProviderCallStatus.failed
    assert provider_calls[0]["error_code"] == "provider_request_failed"
    assert provider_calls[0]["error_message_safe"] == "Provider request failed."
    assert provider_calls[0]["failure_kind"] == "response_failure"
    assert provider_calls[0]["action_run_id"] == action_runs[0]["id"]
    assert provider_calls[0]["scenario_session_id"] == job.scenario_session_id
    assert _UNSAFE_PROVIDER_TEXT not in provider_calls[0]["error_message_safe"]
    assert len(artifacts) == 0

    workflow_state = stored_job["metadata"]["workflow_state"]
    assert workflow_state["steps"]["extract"]["status"] == "failed"
    assert workflow_state["steps"]["extract"]["error_code"] == "provider_request_failed"
    assert workflow_state["steps"]["extract"]["last_action_run_id"] == action_runs[0]["id"]

    assert event_counts["workflow.started"] == 1
    assert event_counts["workflow.failed"] == 1
    assert event_counts["workflow.succeeded"] == 0
    assert event_counts["workflow.step_started"] == 1
    assert event_counts["workflow.step_failed"] == 1
    assert event_counts["action.started"] == 1
    assert event_counts["action.failed"] == 1
    assert event_counts["action.succeeded"] == 0
    assert event_counts["provider.request_started"] == 1
    assert event_counts["provider.request_failed"] == 1
    assert event_counts["provider.request_succeeded"] == 0
    assert event_counts["artifact.created"] == 0
    assert event_counts["scenario.failed"] == 1

    assert adapter.calls[0].worker_name == winner
