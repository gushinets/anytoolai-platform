from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from anytoolai_platform_core.artifacts.models import ArtifactRecord, ArtifactStatus
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.db import (
    action_runs_table,
    artifacts_table,
    event_log_table,
    jobs_table,
    provider_calls_table,
)
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from anytoolai_platform_core.workflows.runner import WorkflowJobService
from anytoolai_platform_worker.composition import build_worker
from anytoolai_platform_worker.handlers.run_workflow import RunWorkflowHandler
from anytoolai_platform_worker.queues import DatabaseJobQueue, WorkflowJobMessage
from anytoolai_platform_worker.worker import Worker
from sqlalchemy import event

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "provider" / "fake_provider_outputs"


def _sqlite_url(database_path: Path) -> str:
    return f"sqlite+pysqlite:///{database_path.resolve().as_posix()}"


@pytest.fixture
def session_factory(tmp_path: Path) -> sa.orm.sessionmaker[sa.orm.Session]:
    main_db = tmp_path / "worker-main.sqlite3"
    platform_db = tmp_path / "worker-platform.sqlite3"
    engine = sa.create_engine(_sqlite_url(main_db), future=True)

    @event.listens_for(engine, "connect")
    def attach_platform_schema(dbapi_connection: Any, connection_record: Any) -> None:
        del connection_record
        dbapi_connection.execute(
            f"ATTACH DATABASE '{platform_db.resolve().as_posix()}' AS platform"
        )

    alembic_config = Config()
    alembic_config.set_main_option(
        "script_location", str(REPO_ROOT / "migrations" / "platform")
    )
    alembic_config.set_main_option("sqlalchemy.url", _sqlite_url(main_db))
    with engine.begin() as connection:
        alembic_config.attributes["connection"] = connection
        command.upgrade(alembic_config, "head")

    factory = build_session_factory(engine)
    yield factory
    engine.dispose()


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


def test_production_composition_accepts_configured_psycopg_database_url() -> None:
    worker = build_worker(
        database_url="postgresql+psycopg://anytoolai:anytoolai@postgres:5432/anytoolai",
        config_root=CONFIG_ROOT,
        provider_adapters={"fake": FakeProviderAdapter(FIXTURE_ROOT)},
    )

    assert isinstance(worker, Worker)


class RecordingRunner:
    def __init__(self, session: sa.orm.Session, *, fail: bool = False) -> None:
        self._session = session
        self._fail = fail
        self.calls: list[tuple[JobRecord, dict[str, Any], ExecutionContext]] = []

    async def run_claimed_job(
        self,
        job: JobRecord,
        input_payload: dict[str, Any],
        context: ExecutionContext,
    ) -> None:
        self.calls.append((job, input_payload, context))
        if self._fail:
            raise RuntimeError("raw provider output secret_token=should-not-leak")
        artifact = ArtifactRepository(self._session).create(
            ArtifactRecord(
                id="artifact_result",
                tenant_id=job.tenant_id,
                region=job.region,
                product_id=job.product_id,
                frontend_id=job.frontend_id,
                scenario_session_id=job.scenario_session_id,
                job_id=job.id,
                artifact_type="structured_output",
                status=ArtifactStatus.stored,
                content_json={"ok": True},
            )
        )
        repository = JobRepository(self._session)
        emitter = EventEmitter(EventLogRepository(self._session))
        WorkflowJobService(repository, emitter).mark_succeeded(
            replace(
                job,
                status=JobStatus.succeeded,
                result_artifact_id=artifact.id,
                completed_at=utc_now(),
            )
        )


class CancelledRunner:
    def __init__(self, session: sa.orm.Session) -> None:
        del session

    async def run_claimed_job(
        self,
        job: JobRecord,
        input_payload: dict[str, Any],
        context: ExecutionContext,
    ) -> None:
        del job, input_payload, context
        raise asyncio.CancelledError()


class UnsafeRawTextProviderAdapter:
    async def complete(self, request: Any) -> Any:
        raise RuntimeError(
            "provider echoed prompt="
            f"{request.prompt}; user_text=deadline budget deliverables"
        )


def _seed_job(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    *,
    input_payload: Any = None,
    created_at: Any = None,
) -> JobRecord:
    metadata = {} if input_payload is None else {"input": input_payload}
    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).create(_scenario(**metadata))
        job = _job(scenario.id)
        if created_at is not None:
            job = replace(job, created_at=created_at)
        return JobRepository(session).create(job)


def _seed_raw_job(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    record: JobRecord,
) -> JobRecord:
    with transaction_boundary(session_factory) as session:
        session.execute(sa.insert(jobs_table).values(asdict(record)))
        session.flush()
    return record


def test_worker_boot_processes_a_claimed_job_from_scenario_session_input(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    job = _seed_job(
        session_factory,
        input_payload={"source_text": "deadline budget deliverables"},
    )
    runners: list[RecordingRunner] = []

    def runner_factory(session: sa.orm.Session) -> RecordingRunner:
        runner = RecordingRunner(session)
        runners.append(runner)
        return runner

    worker = Worker(
        RunWorkflowHandler(
            session_factory=session_factory,
            runner_factory=runner_factory,
        )
    )
    result = asyncio.run(worker.process_job(job.id))

    assert result is not None
    assert result.status is JobStatus.succeeded
    assert result.result_artifact_id == "artifact_result"
    assert len(runners) == 1
    called_job, input_payload, context = runners[0].calls[0]
    assert called_job.id == job.id
    assert called_job.status is JobStatus.running
    assert input_payload == {"source_text": "deadline budget deliverables"}
    assert context.scenario_session_id == job.scenario_session_id
    assert context.job_id == job.id


def test_worker_failure_is_safe_and_emits_correlated_workflow_failed_event(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    job = _seed_job(session_factory, input_payload={"source_text": "failure"})
    runner = RecordingRunner

    worker = Worker(
        RunWorkflowHandler(
            session_factory=session_factory,
            runner_factory=lambda session: runner(session, fail=True),
        )
    )
    result = asyncio.run(worker.process_job(job.id))

    assert result is not None
    assert result.status is JobStatus.failed
    assert result.error_code == "workflow_execution_failed"
    assert result.error_message_safe == "Workflow execution failed."
    assert result.completed_at is not None
    assert "secret_token" not in (result.error_message_safe or "")

    with transaction_boundary(session_factory) as session:
        event_row = session.execute(
            sa.select(event_log_table).where(event_log_table.c.event_type == "workflow.failed")
        ).mappings().one()
    assert event_row["job_id"] == job.id
    assert event_row["scenario_session_id"] == job.scenario_session_id
    assert event_row["error_code"] == "workflow_execution_failed"


def test_worker_cancellation_marks_claimed_job_canceled_and_reraises(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    job = _seed_job(session_factory, input_payload={"source_text": "cancel"})
    worker = Worker(
        RunWorkflowHandler(
            session_factory=session_factory,
            runner_factory=CancelledRunner,
        )
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(worker.process_job(job.id))

    with transaction_boundary(session_factory) as session:
        stored = JobRepository(session).get(job.id)
        event_types = list(
            session.execute(
                sa.select(event_log_table.c.event_type)
                .where(event_log_table.c.job_id == job.id)
                .order_by(event_log_table.c.timestamp, event_log_table.c.event_id)
            ).scalars()
        )

    assert stored is not None
    assert stored.status is JobStatus.canceled
    assert stored.completed_at is not None
    assert event_types == ["workflow.started", "workflow.canceled"]


def test_worker_started_and_failed_events_keep_scenario_identity_for_invalid_input(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    job = _seed_job(session_factory, input_payload=None)
    worker = Worker(
        RunWorkflowHandler(
            session_factory=session_factory,
            runner_factory=RecordingRunner,
        )
    )

    result = asyncio.run(worker.process_job(job.id))

    assert result is not None
    assert result.status is JobStatus.failed
    with transaction_boundary(session_factory) as session:
        events = list(
            session.execute(
                sa.select(event_log_table)
                .where(
                    event_log_table.c.job_id == job.id,
                    event_log_table.c.event_type.in_(("workflow.started", "workflow.failed")),
                )
                .order_by(event_log_table.c.timestamp, event_log_table.c.event_id)
            ).mappings()
        )

    assert [event_row["event_type"] for event_row in events] == [
        "workflow.started",
        "workflow.failed",
    ]
    for event_row in events:
        assert event_row["guest_id"] == "guest_demo"
        assert event_row["user_id"] == "user_demo"
        assert event_row["scenario_chain_id"] == "scenario_chain_demo"


def test_claim_and_workflow_started_roll_back_together_when_event_persistence_fails(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = _seed_job(session_factory, input_payload={"source_text": "atomic"})
    original_create = EventLogRepository.create

    def fail_workflow_started(
        repository: EventLogRepository,
        envelope: Any,
    ) -> Any:
        if envelope.event_type == "workflow.started":
            raise RuntimeError("event persistence failed")
        return original_create(repository, envelope)

    monkeypatch.setattr(EventLogRepository, "create", fail_workflow_started)
    worker = Worker(
        RunWorkflowHandler(
            session_factory=session_factory,
            runner_factory=RecordingRunner,
        )
    )

    with pytest.raises(RuntimeError, match="event persistence failed"):
        asyncio.run(worker.process_job(job.id))

    with transaction_boundary(session_factory) as session:
        stored = JobRepository(session).get(job.id)
        events = list(session.execute(sa.select(event_log_table)).mappings())
    assert stored is not None
    assert stored.status is JobStatus.created
    assert stored.started_at is None
    assert events == []


def test_worker_claim_is_idempotent_and_cancel_is_preclaim_only(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    job = _seed_job(session_factory, input_payload={"source_text": "once"})
    runners: list[RecordingRunner] = []

    def runner_factory(session: sa.orm.Session) -> RecordingRunner:
        runner = RecordingRunner(session)
        runners.append(runner)
        return runner

    worker = Worker(
        RunWorkflowHandler(
            session_factory=session_factory,
            runner_factory=runner_factory,
        )
    )
    first = asyncio.run(worker.process_job(job.id))
    second = asyncio.run(worker.process_job(job.id))

    assert first is not None and first.status is JobStatus.succeeded
    assert second is not None and second.status is JobStatus.succeeded
    assert len(runners) == 1

    cancelable = _seed_job(session_factory, input_payload={"source_text": "cancel"})
    canceled = worker.cancel_job(cancelable.id)
    assert canceled is not None
    assert canceled.status is JobStatus.canceled
    assert asyncio.run(worker.process_job(cancelable.id)) is not None
    assert asyncio.run(worker.process_job(cancelable.id)).status is JobStatus.canceled

    with transaction_boundary(session_factory) as session:
        canceled_event = session.execute(
            sa.select(event_log_table).where(
                event_log_table.c.event_type == "workflow.canceled"
            )
        ).mappings().one()
    assert canceled_event["job_id"] == cancelable.id
    assert canceled_event["scenario_session_id"] == cancelable.scenario_session_id
    assert canceled_event["result_status"] == JobStatus.canceled.value


@pytest.mark.parametrize("poison_case", ["missing", "mismatched"])
def test_worker_terminalizes_poison_created_job_and_advances_queue(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    poison_case: str,
) -> None:
    now = utc_now()
    if poison_case == "missing":
        poison_job = _seed_raw_job(
            session_factory,
            replace(
                _job("scenario_session_missing"),
                created_at=now,
            ),
        )
    else:
        with transaction_boundary(session_factory) as session:
            scenario = ScenarioSessionRepository(session).create(_scenario())
        poison_job = _seed_raw_job(
            session_factory,
            replace(
                _job(scenario.id),
                product_id="kernel_demo_other",
                created_at=now,
            ),
        )
    valid_job = _seed_job(
        session_factory,
        input_payload={"source_text": "deadline budget deliverables"},
        created_at=now + timedelta(microseconds=1),
    )

    runners: list[RecordingRunner] = []

    def runner_factory(session: sa.orm.Session) -> RecordingRunner:
        runner = RecordingRunner(session)
        runners.append(runner)
        return runner

    worker = Worker(
        RunWorkflowHandler(
            session_factory=session_factory,
            runner_factory=runner_factory,
        ),
        job_queue=DatabaseJobQueue(session_factory),
    )

    first = asyncio.run(worker.process_next_job())
    second = asyncio.run(worker.process_next_job())

    assert first is not None
    assert first.id == poison_job.id
    assert first.status is JobStatus.failed
    assert first.error_code == "job_scenario_session_invalid"
    assert first.error_message_safe == "Job scenario session linkage is invalid."
    assert second is not None
    assert second.id == valid_job.id
    assert second.status is JobStatus.succeeded
    assert len(runners) == 1

    with transaction_boundary(session_factory) as session:
        poison_events = list(
            session.execute(
                sa.select(event_log_table)
                .where(event_log_table.c.job_id == poison_job.id)
                .order_by(event_log_table.c.timestamp, event_log_table.c.event_id)
            ).mappings()
        )

    assert [event_row["event_type"] for event_row in poison_events] == ["workflow.failed"]
    assert poison_events[0]["error_code"] == "job_scenario_session_invalid"


def test_worker_run_forever_continues_after_unexpected_iteration_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class StubHandler:
        def __init__(self) -> None:
            self.calls = 0

        async def handle(self, job_id: str) -> Any:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError(f"boom for {job_id}")
            raise asyncio.CancelledError()

        def cancel(self, job_id: str) -> None:
            del job_id
            return None

    class StubQueue:
        def __init__(self) -> None:
            self.messages = [
                WorkflowJobMessage(job_id="job_boom"),
                WorkflowJobMessage(job_id="job_stop"),
            ]

        def next_message(self) -> WorkflowJobMessage | None:
            if not self.messages:
                return None
            return self.messages.pop(0)

    handler = StubHandler()
    worker = Worker(
        handler,  # type: ignore[arg-type]
        job_queue=StubQueue(),  # type: ignore[arg-type]
        poll_interval_seconds=0,
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(worker.run_forever())

    assert handler.calls == 2
    assert "worker loop iteration failed" in caplog.text


def test_production_composed_worker_processes_real_runtime_path_end_to_end(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    job = _seed_job(
        session_factory,
        input_payload={"source_text": "deadline budget deliverables"},
    )
    worker = build_worker(
        session_factory=session_factory,
        config_root=CONFIG_ROOT,
        provider_adapters={"fake": FakeProviderAdapter(FIXTURE_ROOT)},
    )

    result = asyncio.run(worker.process_next_job())

    assert result is not None
    assert result.id == job.id
    assert result.status is JobStatus.succeeded
    assert result.completed_at is not None
    assert result.result_artifact_id is not None

    with transaction_boundary(session_factory) as session:
        stored_job = session.execute(
            sa.select(jobs_table).where(jobs_table.c.id == job.id)
        ).mappings().one()
        action_run = session.execute(
            sa.select(action_runs_table).where(action_runs_table.c.job_id == job.id)
        ).mappings().one()
        provider_call = session.execute(
            sa.select(provider_calls_table).where(provider_calls_table.c.job_id == job.id)
        ).mappings().one()
        artifacts = list(
            session.execute(
                sa.select(artifacts_table).where(artifacts_table.c.job_id == job.id)
            ).mappings()
        )
        events = list(
            session.execute(
                sa.select(event_log_table)
                .where(event_log_table.c.job_id == job.id)
                .order_by(event_log_table.c.timestamp, event_log_table.c.event_id)
            ).mappings()
        )

    event_types = [event_row["event_type"] for event_row in events]

    assert stored_job["result_artifact_id"] == result.result_artifact_id
    assert action_run["scenario_session_id"] == job.scenario_session_id
    assert provider_call["action_run_id"] == action_run["id"]
    assert provider_call["scenario_session_id"] == job.scenario_session_id
    assert all(artifact["scenario_session_id"] == job.scenario_session_id for artifact in artifacts)
    assert any(artifact["id"] == result.result_artifact_id for artifact in artifacts)
    assert {
        "workflow.started",
        "action.started",
        "provider.request_started",
        "provider.request_succeeded",
        "artifact.created",
        "action.succeeded",
        "workflow.succeeded",
    }.issubset(event_types)
    assert event_types.count("workflow.started") == 1
    for event_row in events:
        if event_row["event_type"] in {
            "workflow.started",
            "action.started",
            "provider.request_started",
            "provider.request_succeeded",
            "workflow.succeeded",
        }:
            assert event_row["guest_id"] == "guest_demo", event_row["event_type"]
            assert event_row["user_id"] == "user_demo", event_row["event_type"]
            assert event_row["scenario_chain_id"] == "scenario_chain_demo", event_row["event_type"]


def test_production_worker_provider_failure_uses_generic_safe_message(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    job = _seed_job(
        session_factory,
        input_payload={"source_text": "deadline budget deliverables"},
    )
    worker = build_worker(
        session_factory=session_factory,
        config_root=CONFIG_ROOT,
        provider_adapters={"fake": UnsafeRawTextProviderAdapter()},
    )

    result = asyncio.run(worker.process_next_job())

    assert result is not None
    assert result.id == job.id
    assert result.status is JobStatus.failed
    assert result.error_code == "provider_request_failed"
    assert result.error_message_safe == "Provider request failed."

    with transaction_boundary(session_factory) as session:
        stored_job = session.execute(
            sa.select(jobs_table).where(jobs_table.c.id == job.id)
        ).mappings().one()
        provider_call = session.execute(
            sa.select(provider_calls_table).where(provider_calls_table.c.job_id == job.id)
        ).mappings().one()

    assert stored_job["error_message_safe"] == "Provider request failed."
    assert provider_call["error_message_safe"] == "Provider request failed."
    assert "deadline budget deliverables" not in stored_job["error_message_safe"]


def test_production_worker_provider_failure_preserves_claimed_job_recovery_state(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    job = _seed_job(
        session_factory,
        input_payload={"source_text": "deadline budget deliverables"},
    )
    worker = build_worker(
        session_factory=session_factory,
        config_root=CONFIG_ROOT,
        provider_adapters={"fake": UnsafeRawTextProviderAdapter()},
    )

    result = asyncio.run(worker.process_next_job())

    assert result is not None
    assert result.id == job.id
    assert result.status is JobStatus.failed
    assert result.error_code == "provider_request_failed"

    with transaction_boundary(session_factory) as session:
        stored_job = session.execute(
            sa.select(jobs_table).where(jobs_table.c.id == job.id)
        ).mappings().one()
        events = list(
            session.execute(
                sa.select(event_log_table)
                .where(event_log_table.c.job_id == job.id)
                .order_by(event_log_table.c.timestamp, event_log_table.c.event_id)
            ).mappings()
        )

    workflow_state = stored_job["metadata"]["workflow_state"]
    assert workflow_state["steps"]["extract"]["status"] == "failed"
    assert workflow_state["steps"]["extract"]["error_code"] == "provider_request_failed"
    event_types = [event_row["event_type"] for event_row in events]
    assert {
        "workflow.started",
        "action.started",
        "provider.request_started",
        "provider.request_failed",
        "action.failed",
        "workflow.step_started",
        "workflow.step_failed",
        "workflow.failed",
    }.issubset(event_types)
    assert event_types.count("workflow.started") == 1
    assert event_types.index("workflow.step_started") < event_types.index("workflow.step_failed")
    assert event_types.index("workflow.step_failed") < event_types.index("workflow.failed")
