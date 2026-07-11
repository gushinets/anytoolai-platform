from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
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
        repository = JobRepository(self._session)
        emitter = EventEmitter(EventLogRepository(self._session))
        WorkflowJobService(repository, emitter).mark_succeeded(
            replace(
                job,
                status=JobStatus.succeeded,
                result_artifact_id="artifact_result",
                completed_at=utc_now(),
            )
        )


def _seed_job(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    *,
    input_payload: Any = None,
) -> JobRecord:
    metadata = {} if input_payload is None else {"input": input_payload}
    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).create(_scenario(**metadata))
        return JobRepository(session).create(_job(scenario.id))


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
        event_types = list(
            session.execute(
                sa.select(event_log_table.c.event_type).where(
                    event_log_table.c.job_id == job.id
                )
            ).scalars()
        )

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
