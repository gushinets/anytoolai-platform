from __future__ import annotations

import asyncio
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path
from threading import Barrier
from typing import Any

import pytest
import sqlalchemy as sa
from anytoolai_platform_core.artifacts.models import ArtifactRecord, ArtifactStatus
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.providers.models import ProviderCallStatus
from anytoolai_platform_core.scenarios.checkpoints import (
    FAILED_CHECKPOINT_ID,
    PROCESSING_CHECKPOINT_ID,
    RESULT_READY_CHECKPOINT_ID,
)
from anytoolai_platform_core.scenarios.models import (
    ScenarioSessionRecord,
    ScenarioSessionStatus,
)
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.scenarios.service import ScenarioSessionService
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
from anytoolai_platform_worker.reconciliation import OrphanedRunningJobReconciler
from anytoolai_platform_worker.worker import Worker

from tests.db_support import provision_database

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "provider" / "fake_provider_outputs"
pytestmark = [pytest.mark.postgresql, pytest.mark.slow]


@pytest.fixture
def session_factory() -> Iterator[sa.orm.sessionmaker[sa.orm.Session]]:
    with provision_database(
        database_name_prefix="anytoolai_worker_boot_test",
        skip_reason="PostgreSQL worker boot coverage",
    ) as (engine, _alembic_config, _database_url):
        yield build_session_factory(engine)


def _scenario(
    *,
    guest_id: str | None = "guest_demo",
    user_id: str | None = "user_demo",
    scenario_chain_id: str | None = "scenario_chain_demo",
    **metadata: Any,
) -> ScenarioSessionRecord:
    return ScenarioSessionRecord(
        tenant_id="tenant_demo",
        region="eu-central",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_id="kernel_demo.single_action_smoke_v1",
        scenario_version=1,
        guest_id=guest_id,
        user_id=user_id,
        scenario_chain_id=scenario_chain_id,
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
    worker.dispose()


class RecordingRunner:
    def __init__(self, session: sa.orm.Session, *, fail: bool = False) -> None:
        self._session = session
        self._fail = fail
        self.calls: list[tuple[JobRecord, dict[str, Any], ExecutionContext]] = []
        self.observed_scenarios: list[ScenarioSessionRecord] = []

    async def run_claimed_job(
        self,
        job: JobRecord,
        input_payload: dict[str, Any],
        context: ExecutionContext,
    ) -> None:
        self.calls.append((job, input_payload, context))
        scenario = ScenarioSessionRepository(self._session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
        assert scenario is not None
        self.observed_scenarios.append(scenario)
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
            f"provider echoed prompt={request.prompt}; user_text=deadline budget deliverables"
        )


class FailOnSecondCallProviderAdapter:
    def __init__(self) -> None:
        self.call_count = 0
        self._delegate = FakeProviderAdapter(FIXTURE_ROOT)

    async def complete(self, request: Any) -> Any:
        self.call_count += 1
        if self.call_count == 2:
            raise RuntimeError(
                f"provider echoed prompt={request.prompt}; user_text=deadline budget deliverables"
            )
        return await self._delegate.complete(request)


class CancelledProviderAdapter:
    async def complete(self, request: Any) -> Any:
        del request
        raise asyncio.CancelledError()


def _seed_job(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    *,
    input_payload: Any = None,
    created_at: Any = None,
    workflow_id: str = "kernel_demo.single_action_extract_v1",
    guest_id: str | None = "guest_demo",
    user_id: str | None = "user_demo",
    scenario_chain_id: str | None = "scenario_chain_demo",
    job_metadata: dict[str, Any] | None = None,
) -> JobRecord:
    metadata = {} if input_payload is None else {"input": input_payload}
    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).create(
            _scenario(
                guest_id=guest_id,
                user_id=user_id,
                scenario_chain_id=scenario_chain_id,
                **metadata,
            )
        )
        job = replace(
            _job(scenario.id),
            workflow_id=workflow_id,
            metadata=dict(job_metadata or {}),
        )
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


def _event_rows_for_job(session: sa.orm.Session, job_id: str) -> list[dict[str, Any]]:
    return list(
        session.execute(
            sa.select(event_log_table)
            .where(event_log_table.c.job_id == job_id)
            .order_by(event_log_table.c.timestamp, event_log_table.c.event_id)
        ).mappings()
    )


def _assert_cancel_event_dimensions(
    event_row: dict[str, Any],
    *,
    job: JobRecord,
    scenario: ScenarioSessionRecord,
) -> None:
    assert event_row["event_type"] == "workflow.canceled"
    assert event_row["tenant_id"] == job.tenant_id
    assert event_row["region"] == job.region
    assert event_row["product_id"] == job.product_id
    assert event_row["frontend_id"] == job.frontend_id
    assert event_row["scenario_session_id"] == scenario.id
    assert event_row["scenario_chain_id"] == scenario.scenario_chain_id
    assert event_row["guest_id"] == scenario.guest_id
    assert event_row["user_id"] == scenario.user_id
    assert event_row["job_id"] == job.id
    assert event_row["workflow_id"] == job.workflow_id
    assert event_row["workflow_version"] == job.workflow_version
    assert event_row["result_status"] == JobStatus.canceled.value
    assert event_row["properties"]["workflow_version"] == job.workflow_version


def _seed_running_job(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> JobRecord:
    """Move a freshly-seeded job to `running` via the real claim path, without going
    through a lease -- for reconciler tests that only care about job status, not
    who (if anyone) holds the advisory lock."""
    job = _seed_job(
        session_factory,
        input_payload={"source_text": "deadline budget deliverables"},
    )
    with transaction_boundary(session_factory) as session:
        repository = JobRepository(session)
        emitter = EventEmitter(EventLogRepository(session))
        claimed = WorkflowJobService(repository, emitter).claim_created(job.id)
        assert claimed is not None
        scenario_repository = ScenarioSessionRepository(session)
        scenario = scenario_repository.get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
        assert scenario is not None
        ScenarioSessionService(scenario_repository, emitter).mark_running(scenario)
        return claimed


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
    assert runners[0].observed_scenarios[0].status is ScenarioSessionStatus.running
    assert runners[0].observed_scenarios[0].current_checkpoint_id == PROCESSING_CHECKPOINT_ID

    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
        scenario_completed = (
            session.execute(
                sa.select(event_log_table).where(
                    event_log_table.c.scenario_session_id == job.scenario_session_id,
                    event_log_table.c.event_type == "scenario.completed",
                )
            )
            .mappings()
            .one()
        )
    assert scenario is not None
    assert scenario.status is ScenarioSessionStatus.completed
    assert scenario.current_checkpoint_id == RESULT_READY_CHECKPOINT_ID
    assert scenario_completed["job_id"] == job.id
    assert scenario_completed["workflow_id"] == job.workflow_id


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
        event_row = (
            session.execute(
                sa.select(event_log_table).where(event_log_table.c.event_type == "workflow.failed")
            )
            .mappings()
            .one()
        )
        scenario_failed = (
            session.execute(
                sa.select(event_log_table).where(
                    event_log_table.c.scenario_session_id == job.scenario_session_id,
                    event_log_table.c.event_type == "scenario.failed",
                )
            )
            .mappings()
            .one()
        )
        scenario = ScenarioSessionRepository(session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
    assert event_row["job_id"] == job.id
    assert event_row["scenario_session_id"] == job.scenario_session_id
    assert event_row["error_code"] == "workflow_execution_failed"
    assert scenario is not None
    assert scenario.status is ScenarioSessionStatus.failed
    assert scenario.current_checkpoint_id == FAILED_CHECKPOINT_ID
    assert scenario_failed["job_id"] == job.id
    assert scenario_failed["workflow_id"] == job.workflow_id


def test_worker_failure_uses_persisted_job_error_code_for_scenario_failure(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    job = _seed_job(session_factory, input_payload={"source_text": "failure"})
    handler = RunWorkflowHandler(
        session_factory=session_factory,
        runner_factory=RecordingRunner,
    )

    with transaction_boundary(session_factory) as session:
        repository = JobRepository(session)
        emitter = EventEmitter(EventLogRepository(session))
        claimed = WorkflowJobService(repository, emitter).claim_created(job.id)
        assert claimed is not None
        scenario_repository = ScenarioSessionRepository(session)
        scenario = scenario_repository.get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
        assert scenario is not None
        ScenarioSessionService(scenario_repository, emitter).mark_running(scenario)
        WorkflowJobService(repository, emitter).mark_failed(
            replace(
                claimed,
                status=JobStatus.failed,
                error_code="provider_request_failed",
                error_message_safe="Provider request failed.",
                completed_at=utc_now(),
            ),
            error_code="provider_request_failed",
        )

    handler._persist_handler_failure(
        job.id,
        RuntimeError("outer handler failure should not overwrite persisted job error"),
    )

    result = handler._get(job.id)

    assert result is not None
    assert result.status is JobStatus.failed
    assert result.error_code == "provider_request_failed"

    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
        scenario_failed = (
            session.execute(
                sa.select(event_log_table)
                .where(
                    event_log_table.c.scenario_session_id == job.scenario_session_id,
                    event_log_table.c.event_type == "scenario.failed",
                )
                .order_by(event_log_table.c.timestamp.desc(), event_log_table.c.event_id.desc())
            )
            .mappings()
            .first()
        )

    assert scenario is not None
    assert scenario.status is ScenarioSessionStatus.failed
    assert scenario.current_checkpoint_id == FAILED_CHECKPOINT_ID
    assert scenario_failed is not None
    assert scenario_failed["job_id"] == job.id
    assert scenario_failed["workflow_id"] == job.workflow_id
    assert scenario_failed["properties"]["error_code"] == "provider_request_failed"


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
        scenario = ScenarioSessionRepository(session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
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
    assert scenario is not None
    assert scenario.status is ScenarioSessionStatus.failed
    assert scenario.current_checkpoint_id == FAILED_CHECKPOINT_ID
    assert event_types == [
        "workflow.started",
        "workflow.canceled",
        "scenario.checkpoint_reached",
        "scenario.failed",
    ]


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
    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
    assert scenario is not None
    assert scenario.status is ScenarioSessionStatus.failed
    assert scenario.current_checkpoint_id == FAILED_CHECKPOINT_ID


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
        scenario = ScenarioSessionRepository(session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
    assert stored is not None
    assert stored.status is JobStatus.created
    assert stored.started_at is None
    assert events == []
    assert scenario is not None
    assert scenario.status is ScenarioSessionStatus.started
    assert scenario.current_checkpoint_id is None


def test_cancel_created_job_preserves_guest_scenario_identity(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    job = _seed_job(
        session_factory,
        input_payload={"source_text": "cancel guest"},
        guest_id="guest_cancel",
        user_id=None,
        scenario_chain_id="scenario_chain_cancel_guest",
        job_metadata={"preexisting": "kept"},
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

    canceled = worker.cancel_job(job.id)

    assert canceled is not None
    assert canceled.status is JobStatus.canceled
    assert runners == []
    with transaction_boundary(session_factory) as session:
        stored = JobRepository(session).get(job.id)
        scenario = ScenarioSessionRepository(session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
        events = _event_rows_for_job(session, job.id)

    assert stored is not None
    assert scenario is not None
    assert stored.status is JobStatus.canceled
    assert stored.metadata["preexisting"] == "kept"
    assert stored.metadata["guest_id"] == "guest_cancel"
    assert stored.metadata["scenario_chain_id"] == "scenario_chain_cancel_guest"
    assert stored.metadata["user_id"] is None
    assert len(events) == 1
    _assert_cancel_event_dimensions(events[0], job=job, scenario=scenario)


def test_cancel_created_job_preserves_authenticated_scenario_identity(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    job = _seed_job(
        session_factory,
        input_payload={"source_text": "cancel authenticated"},
        guest_id=None,
        user_id="user_cancel",
        scenario_chain_id="scenario_chain_cancel_user",
        job_metadata={"preexisting": "kept"},
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

    canceled = worker.cancel_job(job.id)

    assert canceled is not None
    assert canceled.status is JobStatus.canceled
    assert runners == []
    with transaction_boundary(session_factory) as session:
        stored = JobRepository(session).get(job.id)
        scenario = ScenarioSessionRepository(session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
        events = _event_rows_for_job(session, job.id)

    assert stored is not None
    assert scenario is not None
    assert stored.metadata["preexisting"] == "kept"
    assert stored.metadata["user_id"] == "user_cancel"
    assert stored.metadata["scenario_chain_id"] == "scenario_chain_cancel_user"
    assert stored.metadata["guest_id"] is None
    assert len(events) == 1
    _assert_cancel_event_dimensions(events[0], job=job, scenario=scenario)


def test_cancel_created_job_terminalizes_missing_scenario_session_as_failed(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    job = _seed_raw_job(
        session_factory,
        replace(
            _job("scenario_session_missing"),
            metadata={"preexisting": "kept"},
        ),
    )
    worker = Worker(
        RunWorkflowHandler(
            session_factory=session_factory,
            runner_factory=RecordingRunner,
        )
    )

    result = worker.cancel_job(job.id)

    assert result is not None
    assert result.status is JobStatus.failed
    assert result.error_code == "job_scenario_session_invalid"

    with transaction_boundary(session_factory) as session:
        stored = JobRepository(session).get(job.id)
        events = _event_rows_for_job(session, job.id)

    assert stored is not None
    assert stored.status is JobStatus.failed
    assert stored.completed_at is not None
    assert stored.metadata == {"preexisting": "kept"}
    assert [event["event_type"] for event in events] == ["workflow.failed"]
    assert events[0]["error_code"] == "job_scenario_session_invalid"


def test_cancel_created_job_terminalizes_missing_scenario_session_linkage_as_failed(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    job = _seed_raw_job(
        session_factory,
        replace(
            _job(""),
            metadata={"preexisting": "kept"},
        ),
    )
    worker = Worker(
        RunWorkflowHandler(
            session_factory=session_factory,
            runner_factory=RecordingRunner,
        )
    )

    result = worker.cancel_job(job.id)

    assert result is not None
    assert result.status is JobStatus.failed
    assert result.error_code == "job_scenario_session_invalid"

    with transaction_boundary(session_factory) as session:
        stored = JobRepository(session).get(job.id)
        events = _event_rows_for_job(session, job.id)

    assert stored is not None
    assert stored.status is JobStatus.failed
    assert stored.completed_at is not None
    assert stored.metadata == {"preexisting": "kept"}
    assert [event["event_type"] for event in events] == ["workflow.failed"]
    assert events[0]["error_code"] == "job_scenario_session_invalid"


def test_cancel_created_job_terminalizes_mismatched_scenario_session_as_failed(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).create(_scenario(input={"source_text": "x"}))
    job = _seed_raw_job(
        session_factory,
        replace(
            _job(scenario.id),
            product_id="kernel_demo_other",
            metadata={"preexisting": "kept"},
        ),
    )
    worker = Worker(
        RunWorkflowHandler(
            session_factory=session_factory,
            runner_factory=RecordingRunner,
        )
    )

    result = worker.cancel_job(job.id)

    assert result is not None
    assert result.status is JobStatus.failed
    assert result.error_code == "job_scenario_session_invalid"

    with transaction_boundary(session_factory) as session:
        stored = JobRepository(session).get(job.id)
        events = _event_rows_for_job(session, job.id)

    assert stored is not None
    assert stored.status is JobStatus.failed
    assert stored.completed_at is not None
    assert stored.metadata == {"preexisting": "kept"}
    assert [event["event_type"] for event in events] == ["workflow.failed"]
    assert events[0]["error_code"] == "job_scenario_session_invalid"


@pytest.mark.parametrize(
    "status",
    [
        JobStatus.running,
        JobStatus.succeeded,
        JobStatus.failed,
        JobStatus.canceled,
    ],
)
def test_cancel_job_rejects_non_created_status_idempotently(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    status: JobStatus,
) -> None:
    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).create(_scenario(input={"source_text": "x"}))
    timestamp = utc_now()
    job = _seed_raw_job(
        session_factory,
        replace(
            _job(scenario.id),
            status=status,
            started_at=timestamp if status is not JobStatus.created else None,
            completed_at=(
                timestamp
                if status in {JobStatus.succeeded, JobStatus.failed, JobStatus.canceled}
                else None
            ),
            metadata={"preexisting": status.value},
        ),
    )
    worker = Worker(
        RunWorkflowHandler(
            session_factory=session_factory,
            runner_factory=RecordingRunner,
        )
    )

    result = worker.cancel_job(job.id)

    assert result is not None
    assert result.status is status
    with transaction_boundary(session_factory) as session:
        stored = JobRepository(session).get(job.id)
        events = _event_rows_for_job(session, job.id)

    assert stored is not None
    assert stored.status is status
    assert stored.metadata == {"preexisting": status.value}
    assert events == []


def test_cancel_created_job_rolls_back_when_event_persistence_fails(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = _seed_job(
        session_factory,
        input_payload={"source_text": "atomic cancel"},
        guest_id="guest_cancel",
        user_id=None,
        scenario_chain_id="scenario_chain_cancel",
        job_metadata={"preexisting": "kept"},
    )
    original_create = EventLogRepository.create

    def fail_workflow_canceled(
        repository: EventLogRepository,
        envelope: Any,
    ) -> Any:
        if envelope.event_type == "workflow.canceled":
            raise RuntimeError("event persistence failed")
        return original_create(repository, envelope)

    monkeypatch.setattr(EventLogRepository, "create", fail_workflow_canceled)
    worker = Worker(
        RunWorkflowHandler(
            session_factory=session_factory,
            runner_factory=RecordingRunner,
        )
    )

    with pytest.raises(RuntimeError, match="event persistence failed"):
        worker.cancel_job(job.id)

    with transaction_boundary(session_factory) as session:
        stored = JobRepository(session).get(job.id)
        events = _event_rows_for_job(session, job.id)

    assert stored is not None
    assert stored.status is JobStatus.created
    assert stored.completed_at is None
    assert stored.metadata == {"preexisting": "kept"}
    assert events == []


def test_cancel_and_claim_race_allows_only_one_created_transition(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    job = _seed_job(
        session_factory,
        input_payload={"source_text": "deadline budget deliverables"},
        guest_id="guest_race",
        user_id=None,
        scenario_chain_id="scenario_chain_race",
        job_metadata={"preexisting": "race"},
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
    barrier = Barrier(2)

    def process_job() -> JobRecord | None:
        barrier.wait()
        return asyncio.run(worker.process_job(job.id))

    def cancel_job() -> JobRecord | None:
        barrier.wait()
        return worker.cancel_job(job.id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        process_future = executor.submit(process_job)
        cancel_future = executor.submit(cancel_job)
        results = [process_future.result(), cancel_future.result()]

    assert all(result is not None for result in results)
    with transaction_boundary(session_factory) as session:
        stored = JobRepository(session).get(job.id)
        events = _event_rows_for_job(session, job.id)

    assert stored is not None
    assert stored.status in {JobStatus.succeeded, JobStatus.canceled}
    workflow_event_types = [
        event["event_type"]
        for event in events
        if event["event_type"].startswith("workflow.")
    ]
    assert workflow_event_types.count("workflow.canceled") <= 1
    assert workflow_event_types.count("workflow.started") <= 1
    assert not {"workflow.started", "workflow.canceled"}.issubset(
        workflow_event_types
    )
    if stored.status is JobStatus.canceled:
        assert runners == []
        assert workflow_event_types == ["workflow.canceled"]
    else:
        assert stored.status is JobStatus.succeeded
        assert len(runners) == 1
        assert workflow_event_types == ["workflow.started", "workflow.succeeded"]


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
        canceled_event = (
            session.execute(
                sa.select(event_log_table).where(
                    event_log_table.c.event_type == "workflow.canceled"
                )
            )
            .mappings()
            .one()
        )
        completed_scenario = ScenarioSessionRepository(session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
        canceled_scenario = ScenarioSessionRepository(session).get(
            cancelable.scenario_session_id,
            tenant_id=cancelable.tenant_id,
            region=cancelable.region,
            product_id=cancelable.product_id,
            frontend_id=cancelable.frontend_id,
        )
    assert canceled_event["job_id"] == cancelable.id
    assert canceled_event["scenario_session_id"] == cancelable.scenario_session_id
    assert canceled_event["result_status"] == JobStatus.canceled.value
    assert completed_scenario is not None
    assert completed_scenario.status is ScenarioSessionStatus.completed
    assert completed_scenario.current_checkpoint_id == RESULT_READY_CHECKPOINT_ID
    assert canceled_scenario is not None
    assert canceled_scenario.status is ScenarioSessionStatus.started
    assert canceled_scenario.current_checkpoint_id is None


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

        def dispose(self) -> None:
            pass

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
        handler,
        job_queue=StubQueue(),
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
    worker.dispose()

    assert result is not None
    assert result.id == job.id
    assert result.status is JobStatus.succeeded
    assert result.completed_at is not None
    assert result.result_artifact_id is not None

    with transaction_boundary(session_factory) as session:
        stored_job = (
            session.execute(sa.select(jobs_table).where(jobs_table.c.id == job.id)).mappings().one()
        )
        scenario = ScenarioSessionRepository(session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
        action_run = (
            session.execute(
                sa.select(action_runs_table).where(action_runs_table.c.job_id == job.id)
            )
            .mappings()
            .one()
        )
        provider_call = (
            session.execute(
                sa.select(provider_calls_table).where(provider_calls_table.c.job_id == job.id)
            )
            .mappings()
            .one()
        )
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
    assert scenario is not None
    assert scenario.status is ScenarioSessionStatus.completed
    assert scenario.current_checkpoint_id == RESULT_READY_CHECKPOINT_ID
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


def test_production_worker_recovers_scenario_completion_after_mark_completed_failure(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    monkeypatch: pytest.MonkeyPatch,
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

    original_mark_completed = ScenarioSessionService.mark_completed
    call_count = {"count": 0}

    def fail_first_mark_completed(
        self: ScenarioSessionService,
        record: ScenarioSessionRecord,
        *,
        context: Any = None,
    ) -> ScenarioSessionRecord:
        call_count["count"] += 1
        if call_count["count"] == 1:
            # Simulates a transient downstream failure (e.g. a concurrency race in
            # ScenarioSessionRepository.update) that fires after the workflow itself
            # already succeeded but before the outer handler transaction commits.
            raise RuntimeError("forced mark_completed failure after workflow success")
        return original_mark_completed(self, record, context=context)

    monkeypatch.setattr(ScenarioSessionService, "mark_completed", fail_first_mark_completed)

    result = asyncio.run(worker.process_next_job())
    worker.dispose()

    assert result is not None
    assert result.id == job.id
    assert result.status is JobStatus.succeeded
    assert result.result_artifact_id is not None
    assert call_count["count"] == 2

    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
        scenario_completed = (
            session.execute(
                sa.select(event_log_table).where(
                    event_log_table.c.scenario_session_id == job.scenario_session_id,
                    event_log_table.c.event_type == "scenario.completed",
                )
            )
            .mappings()
            .one()
        )

    assert scenario is not None
    assert scenario.status is ScenarioSessionStatus.completed
    assert scenario.current_checkpoint_id == RESULT_READY_CHECKPOINT_ID
    assert scenario_completed["job_id"] == job.id


def test_worker_reconciliation_does_not_clobber_independently_expired_scenario(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    job = _seed_job(session_factory, input_payload={"source_text": "deadline budget deliverables"})
    worker = Worker(
        RunWorkflowHandler(
            session_factory=session_factory,
            runner_factory=RecordingRunner,
        )
    )

    with transaction_boundary(session_factory) as session:
        repository = JobRepository(session)
        emitter = EventEmitter(EventLogRepository(session))
        claimed = WorkflowJobService(repository, emitter).claim_created(job.id)
        assert claimed is not None
        scenario_repository = ScenarioSessionRepository(session)
        scenario = scenario_repository.get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
        assert scenario is not None
        scenario = ScenarioSessionService(scenario_repository, emitter).mark_running(scenario)
        artifact = ArtifactRepository(session).create(
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
        WorkflowJobService(repository, emitter).mark_succeeded(
            replace(
                claimed,
                status=JobStatus.succeeded,
                result_artifact_id=artifact.id,
                completed_at=utc_now(),
            )
        )
        # Simulates an independent expiry sweep racing with this job's completion --
        # it moves the scenario on to `expired` before reconciliation gets to run.
        # Built from the post-mark_running snapshot so current_checkpoint_id/
        # last_event_at match what a real sweep would see, not the pre-running values.
        scenario_repository.update(
            replace(scenario, status=ScenarioSessionStatus.expired),
            tenant_id=scenario.tenant_id,
            region=scenario.region,
            product_id=scenario.product_id,
            frontend_id=scenario.frontend_id,
        )

    # Exercises the public job-processing entrypoint (not the private reconciliation
    # method directly): job is already succeeded, so _claim() returns None and
    # handle() falls into its claimed-is-None retry path.
    reconciled = asyncio.run(worker.process_job(job.id))
    assert reconciled is not None
    assert reconciled.status is JobStatus.succeeded

    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
        completed_events = list(
            session.execute(
                sa.select(event_log_table).where(
                    event_log_table.c.scenario_session_id == job.scenario_session_id,
                    event_log_table.c.event_type == "scenario.completed",
                )
            ).mappings()
        )

    assert scenario is not None
    assert scenario.status is ScenarioSessionStatus.expired
    assert completed_events == []


def test_production_worker_retries_scenario_reconciliation_on_subsequent_handle_call(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    monkeypatch: pytest.MonkeyPatch,
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

    original_mark_completed = ScenarioSessionService.mark_completed
    call_count = {"count": 0}

    def fail_first_two_mark_completed(
        self: ScenarioSessionService,
        record: ScenarioSessionRecord,
        *,
        context: Any = None,
    ) -> ScenarioSessionRecord:
        call_count["count"] += 1
        if call_count["count"] <= 2:
            # Simulates a persistent (not one-off) downstream failure: both the
            # happy-path completion and the first reconciliation attempt fail, so
            # handle() must not crash and the scenario must still be fixable later.
            raise RuntimeError("forced mark_completed failure after workflow success")
        return original_mark_completed(self, record, context=context)

    monkeypatch.setattr(ScenarioSessionService, "mark_completed", fail_first_two_mark_completed)

    first_result = asyncio.run(worker.process_next_job())

    assert first_result is not None
    assert first_result.status is JobStatus.succeeded
    assert call_count["count"] == 2

    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
    assert scenario is not None
    assert scenario.status is ScenarioSessionStatus.running

    second_result = asyncio.run(worker.process_job(job.id))
    worker.dispose()

    assert second_result is not None
    assert second_result.status is JobStatus.succeeded
    assert call_count["count"] == 3

    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
    assert scenario is not None
    assert scenario.status is ScenarioSessionStatus.completed
    assert scenario.current_checkpoint_id == RESULT_READY_CHECKPOINT_ID


def test_production_worker_cancellation_recovers_inflight_action_and_provider_ledger(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    job = _seed_job(
        session_factory,
        input_payload={"source_text": "deadline budget deliverables"},
    )
    worker = build_worker(
        session_factory=session_factory,
        config_root=CONFIG_ROOT,
        provider_adapters={"fake": CancelledProviderAdapter()},
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(worker.process_next_job())
    worker.dispose()

    with transaction_boundary(session_factory) as session:
        stored_job = (
            session.execute(sa.select(jobs_table).where(jobs_table.c.id == job.id)).mappings().one()
        )
        scenario = ScenarioSessionRepository(session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
        action_run = (
            session.execute(
                sa.select(action_runs_table).where(action_runs_table.c.job_id == job.id)
            )
            .mappings()
            .one()
        )
        provider_call = (
            session.execute(
                sa.select(provider_calls_table).where(provider_calls_table.c.job_id == job.id)
            )
            .mappings()
            .one()
        )
        events = list(
            session.execute(
                sa.select(event_log_table)
                .where(event_log_table.c.job_id == job.id)
                .order_by(event_log_table.c.timestamp, event_log_table.c.event_id)
            ).mappings()
        )

    assert stored_job["status"] is JobStatus.canceled
    assert stored_job["completed_at"] is not None
    assert scenario is not None
    assert scenario.status is ScenarioSessionStatus.failed
    assert scenario.current_checkpoint_id == FAILED_CHECKPOINT_ID
    workflow_state = stored_job["metadata"]["workflow_state"]
    assert workflow_state["steps"]["extract"]["status"] == "failed"
    assert workflow_state["steps"]["extract"]["error_code"] == "workflow_execution_cancelled"
    assert workflow_state["steps"]["extract"]["last_action_run_id"] == action_run["id"]

    assert action_run["status"].value == "failed"
    assert action_run["error_code"] == "action_execution_cancelled"
    assert provider_call["action_run_id"] == action_run["id"]
    assert provider_call["status"] == ProviderCallStatus.failed
    assert provider_call["error_code"] == "provider_request_cancelled"
    assert provider_call["failure_kind"] == "cancelled"

    event_types = [event_row["event_type"] for event_row in events]
    assert {
        "workflow.started",
        "workflow.step_started",
        "workflow.step_failed",
        "workflow.canceled",
        "action.started",
        "action.failed",
        "provider.request_started",
        "provider.request_failed",
    }.issubset(event_types)
    assert "workflow.failed" not in event_types

    workflow_step_failed = next(
        event_row for event_row in events if event_row["event_type"] == "workflow.step_failed"
    )
    action_failed = next(
        event_row for event_row in events if event_row["event_type"] == "action.failed"
    )
    provider_failed = next(
        event_row for event_row in events if event_row["event_type"] == "provider.request_failed"
    )
    workflow_canceled = next(
        event_row for event_row in events if event_row["event_type"] == "workflow.canceled"
    )
    assert workflow_step_failed["action_run_id"] == action_run["id"]
    assert workflow_step_failed["properties"]["error_code"] == "workflow_execution_cancelled"
    assert action_failed["action_run_id"] == action_run["id"]
    assert action_failed["properties"]["error_code"] == "action_execution_cancelled"
    assert provider_failed["provider_call_id"] == provider_call["id"]
    assert provider_failed["action_run_id"] == action_run["id"]
    assert provider_failed["properties"]["error_code"] == "provider_request_cancelled"
    assert workflow_canceled["job_id"] == job.id
    assert workflow_canceled["result_status"] == JobStatus.canceled.value


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
    worker.dispose()

    assert result is not None
    assert result.id == job.id
    assert result.status is JobStatus.failed
    assert result.error_code == "provider_request_failed"
    assert result.error_message_safe == "Provider request failed."

    with transaction_boundary(session_factory) as session:
        stored_job = (
            session.execute(sa.select(jobs_table).where(jobs_table.c.id == job.id)).mappings().one()
        )
        scenario = ScenarioSessionRepository(session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
        provider_call = (
            session.execute(
                sa.select(provider_calls_table).where(provider_calls_table.c.job_id == job.id)
            )
            .mappings()
            .one()
        )

    assert stored_job["error_message_safe"] == "Provider request failed."
    assert provider_call["error_message_safe"] == "Provider request failed."
    assert "deadline budget deliverables" not in stored_job["error_message_safe"]
    assert scenario is not None
    assert scenario.status is ScenarioSessionStatus.failed
    assert scenario.current_checkpoint_id == FAILED_CHECKPOINT_ID


def test_production_worker_provider_failure_preserves_claimed_job_recovery_state(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    adapter = FailOnSecondCallProviderAdapter()
    job = _seed_job(
        session_factory,
        input_payload={
            "source_text": "deadline budget deliverables",
            "taxonomy": ["timeline", "scope"],
        },
        workflow_id="kernel_demo.extract_detect_report_v1",
    )
    worker = build_worker(
        session_factory=session_factory,
        config_root=CONFIG_ROOT,
        provider_adapters={"fake": adapter},
    )

    result = asyncio.run(worker.process_next_job())
    worker.dispose()

    assert result is not None
    assert result.id == job.id
    assert result.status is JobStatus.failed
    assert result.error_code == "provider_request_failed"

    with transaction_boundary(session_factory) as session:
        stored_job = (
            session.execute(sa.select(jobs_table).where(jobs_table.c.id == job.id)).mappings().one()
        )
        scenario = ScenarioSessionRepository(session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
        action_runs = list(
            session.execute(
                sa.select(action_runs_table)
                .where(action_runs_table.c.job_id == job.id)
                .order_by(action_runs_table.c.created_at, action_runs_table.c.id)
            ).mappings()
        )
        provider_calls = list(
            session.execute(
                sa.select(provider_calls_table)
                .where(provider_calls_table.c.job_id == job.id)
                .order_by(provider_calls_table.c.created_at, provider_calls_table.c.id)
            ).mappings()
        )
        artifacts = list(
            session.execute(
                sa.select(artifacts_table)
                .where(artifacts_table.c.job_id == job.id)
                .order_by(artifacts_table.c.created_at, artifacts_table.c.id)
            ).mappings()
        )
        events = list(
            session.execute(
                sa.select(event_log_table)
                .where(event_log_table.c.job_id == job.id)
                .order_by(event_log_table.c.timestamp, event_log_table.c.event_id)
            ).mappings()
        )

    assert adapter.call_count == 2
    assert scenario is not None
    assert scenario.status is ScenarioSessionStatus.failed
    assert scenario.current_checkpoint_id == FAILED_CHECKPOINT_ID
    workflow_state = stored_job["metadata"]["workflow_state"]
    assert workflow_state["steps"]["extract"]["status"] == "succeeded"
    assert workflow_state["steps"]["detect_issues"]["status"] == "failed"
    assert workflow_state["steps"]["detect_issues"]["error_code"] == "provider_request_failed"
    assert [row["step_id"] for row in action_runs] == ["extract", "detect_issues"]
    assert [row["status"].value for row in action_runs] == ["succeeded", "failed"]
    assert len(provider_calls) == 2
    assert len(artifacts) == 1
    event_types = [event_row["event_type"] for event_row in events]
    assert event_types == [
        "workflow.started",
        "workflow.step_started",
        "action.started",
        "provider.request_started",
        "provider.request_succeeded",
        "artifact.created",
        "action.succeeded",
        "workflow.step_succeeded",
        "workflow.step_started",
        "action.started",
        "provider.request_started",
        "provider.request_failed",
        "action.failed",
        "workflow.step_failed",
        "workflow.failed",
        "scenario.checkpoint_reached",
        "scenario.failed",
    ]
    workflow_step_started_events = [
        event_row for event_row in events if event_row["event_type"] == "workflow.step_started"
    ]
    workflow_step_succeeded = next(
        event_row for event_row in events if event_row["event_type"] == "workflow.step_succeeded"
    )
    action_failed = next(
        event_row for event_row in events if event_row["event_type"] == "action.failed"
    )
    provider_failed = next(
        event_row for event_row in events if event_row["event_type"] == "provider.request_failed"
    )
    workflow_step_failed = next(
        event_row for event_row in events if event_row["event_type"] == "workflow.step_failed"
    )
    workflow_failed = next(
        event_row for event_row in events if event_row["event_type"] == "workflow.failed"
    )
    scenario_failed = next(
        event_row for event_row in events if event_row["event_type"] == "scenario.failed"
    )
    assert workflow_step_started_events[0]["job_id"] == job.id
    assert workflow_step_started_events[0]["properties"]["step_id"] == "extract"
    assert workflow_step_started_events[1]["properties"]["step_id"] == "detect_issues"
    assert workflow_step_succeeded["action_run_id"] == action_runs[0]["id"]
    assert workflow_step_succeeded["artifact_id"] == artifacts[0]["id"]
    assert workflow_step_failed["job_id"] == job.id
    assert workflow_step_failed["action_run_id"] == action_failed["action_run_id"]
    assert workflow_step_failed["properties"]["step_id"] == "detect_issues"
    assert workflow_step_failed["properties"]["error_code"] == "provider_request_failed"
    assert provider_failed["provider_call_id"] == provider_calls[1]["id"]
    assert provider_failed["action_run_id"] == action_runs[1]["id"]
    assert workflow_failed["job_id"] == job.id
    assert workflow_failed["properties"]["error_code"] == "provider_request_failed"
    assert scenario_failed["job_id"] == job.id
    assert scenario_failed["workflow_id"] == job.workflow_id


class FakeJobLease:
    """Records acquire/release calls; `probe_orphaned` always reports alive."""

    def __init__(self, *, acquire_result: bool = True) -> None:
        self.calls: list[tuple[str, str]] = []
        self._acquire_result = acquire_result

    def acquire(self, job_id: str) -> bool:
        self.calls.append(("acquire", job_id))
        return self._acquire_result

    def release(self, job_id: str) -> None:
        self.calls.append(("release", job_id))

    def probe_orphaned(self, job_id: str) -> bool:
        del job_id
        return False

    def probe_orphaned_batch(self, job_ids: list[str]) -> set[str]:
        del job_ids
        return set()


def test_lease_is_acquired_before_claim_and_released_after_success(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    job = _seed_job(
        session_factory,
        input_payload={"source_text": "deadline budget deliverables"},
    )
    lease = FakeJobLease()
    worker = Worker(
        RunWorkflowHandler(
            session_factory=session_factory,
            runner_factory=RecordingRunner,
            lease=lease,
        )
    )

    result = asyncio.run(worker.process_job(job.id))

    assert result is not None
    assert result.status is JobStatus.succeeded
    assert lease.calls == [("acquire", job.id), ("release", job.id)]


def test_lease_is_released_after_handler_failure(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    job = _seed_job(session_factory, input_payload={"source_text": "failure"})
    lease = FakeJobLease()
    worker = Worker(
        RunWorkflowHandler(
            session_factory=session_factory,
            runner_factory=lambda session: RecordingRunner(session, fail=True),
            lease=lease,
        )
    )

    result = asyncio.run(worker.process_job(job.id))

    assert result is not None
    assert result.status is JobStatus.failed
    assert lease.calls == [("acquire", job.id), ("release", job.id)]


def test_lease_is_released_after_cancellation(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    job = _seed_job(session_factory, input_payload={"source_text": "cancel"})
    lease = FakeJobLease()
    worker = Worker(
        RunWorkflowHandler(
            session_factory=session_factory,
            runner_factory=CancelledRunner,
            lease=lease,
        )
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(worker.process_job(job.id))

    assert lease.calls == [("acquire", job.id), ("release", job.id)]


def test_claim_is_skipped_without_error_when_lease_acquire_fails(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    """A failed acquire means another worker already owns this job -- not an error,
    just a job left untouched (still `created`) for its actual owner to run."""
    job = _seed_job(
        session_factory,
        input_payload={"source_text": "deadline budget deliverables"},
    )
    lease = FakeJobLease(acquire_result=False)
    runners: list[RecordingRunner] = []

    def runner_factory(session: sa.orm.Session) -> RecordingRunner:
        runner = RecordingRunner(session)
        runners.append(runner)
        return runner

    worker = Worker(
        RunWorkflowHandler(
            session_factory=session_factory,
            runner_factory=runner_factory,
            lease=lease,
        )
    )

    result = asyncio.run(worker.process_job(job.id))

    assert result is not None
    assert result.status is JobStatus.created
    assert lease.calls == [("acquire", job.id)]
    assert runners == []


def test_persist_handler_failure_logs_known_residual_race_after_lease_lost(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Known residual race (see docs/exec-plans/active/any-147-worker-lease-recovery.md): a
    sweep can terminate a job as
    `worker_lease_lost` while its original process is still alive and running --
    that process's own eventual outcome then collides with the already-committed
    `failed` state. Not auto-fixed; must at least be observable in the logs."""
    job = _seed_running_job(session_factory)
    handler = RunWorkflowHandler(session_factory=session_factory, runner_factory=RecordingRunner)

    # Simulates the sweep beating this job's own process to a terminal state.
    handler.terminate_orphaned_job(job.id)

    with caplog.at_level("WARNING"):
        handler._persist_handler_failure(job.id, RuntimeError("late outcome after lease loss"))

    assert "worker.job_completed_after_lease_lost" in caplog.text
    result = handler._get(job.id)
    assert result is not None
    assert result.status is JobStatus.failed
    assert result.error_code == "worker_lease_lost"


class FakeReconcilerLease:
    def __init__(self, orphaned_ids: set[str]) -> None:
        self._orphaned_ids = orphaned_ids
        self.probed: list[str] = []

    def probe_orphaned_batch(self, job_ids: list[str]) -> set[str]:
        self.probed.extend(job_ids)
        return set(job_ids) & self._orphaned_ids


class FakeTerminator:
    def __init__(self) -> None:
        self.terminated: list[str] = []

    def terminate_orphaned_job(self, job_id: str) -> None:
        self.terminated.append(job_id)


def test_reconciler_terminates_only_orphaned_running_jobs(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    running_jobs = [_seed_running_job(session_factory) for _ in range(3)]
    created_job = _seed_job(session_factory, input_payload={"source_text": "not running"})

    orphaned_ids = {running_jobs[0].id, running_jobs[2].id}
    lease = FakeReconcilerLease(orphaned_ids)
    terminator = FakeTerminator()
    reconciler = OrphanedRunningJobReconciler(
        session_factory=session_factory,
        lease=lease,
        terminator=terminator,
        limit=10,
    )

    terminated = reconciler.reconcile_once()

    assert terminated == 2
    assert set(terminator.terminated) == orphaned_ids
    assert set(lease.probed) == {job.id for job in running_jobs}
    assert created_job.id not in lease.probed


def test_reconciler_respects_sweep_limit(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    running_jobs = [_seed_running_job(session_factory) for _ in range(3)]
    lease = FakeReconcilerLease({job.id for job in running_jobs})
    terminator = FakeTerminator()
    reconciler = OrphanedRunningJobReconciler(
        session_factory=session_factory,
        lease=lease,
        terminator=terminator,
        limit=2,
    )

    terminated = reconciler.reconcile_once()

    assert terminated == 2
    assert len(terminator.terminated) == 2


def test_run_forever_finishes_inflight_job_then_drains_on_request_shutdown() -> None:
    worker_holder: dict[str, Worker] = {}

    class ShutdownDuringFirstJobHandler:
        def __init__(self) -> None:
            self.handled: list[str] = []

        async def handle(self, job_id: str) -> Any:
            self.handled.append(job_id)
            # Simulates a SIGTERM arriving while this job is still in flight: the
            # flag is only consulted between iterations, so this job must still be
            # allowed to finish -- and no further job may be taken after it.
            worker_holder["worker"].request_shutdown()
            return None

        def cancel(self, job_id: str) -> None:
            del job_id

        def dispose(self) -> None:
            pass

    class TwoJobQueue:
        def __init__(self) -> None:
            self._messages = [
                WorkflowJobMessage(job_id="job_a"),
                WorkflowJobMessage(job_id="job_b"),
            ]

        def next_message(self) -> WorkflowJobMessage | None:
            if not self._messages:
                return None
            return self._messages.pop(0)

    handler = ShutdownDuringFirstJobHandler()
    worker = Worker(
        handler,
        job_queue=TwoJobQueue(),
        poll_interval_seconds=0,
    )
    worker_holder["worker"] = worker

    asyncio.run(worker.run_forever())

    assert handler.handled == ["job_a"]


def test_run_forever_sweeps_before_loop_and_on_idle_iteration() -> None:
    worker_holder: dict[str, Worker] = {}
    calls = {"count": 0}

    class StoppingReconciler:
        def reconcile_once(self) -> int:
            calls["count"] += 1
            # Stop after the pre-loop sweep and exactly one idle-iteration sweep --
            # deterministic, unlike racing against wall-clock sleeps.
            if calls["count"] >= 2:
                worker_holder["worker"].request_shutdown()
            return 0

    class EmptyQueue:
        def next_message(self) -> WorkflowJobMessage | None:
            return None

    class NoopHandler:
        async def handle(self, job_id: str) -> Any:
            del job_id
            return None

        def cancel(self, job_id: str) -> None:
            del job_id

        def dispose(self) -> None:
            pass

    worker = Worker(
        NoopHandler(),
        job_queue=EmptyQueue(),
        poll_interval_seconds=0,
        reconciler=StoppingReconciler(),
    )
    worker_holder["worker"] = worker

    asyncio.run(worker.run_forever())

    assert calls["count"] == 2


def test_run_forever_backs_off_when_claim_race_is_lost_instead_of_hot_looping() -> None:
    """`_claim()` losing a race for a `created` job (another worker's advisory-lock
    `acquire()` won first) returns that job's still-`created` `JobRecord`, not `None` --
    `next_message()` has no `FOR UPDATE`, so both workers can pick the same candidate.
    Before this fix, `run_forever()` only treated a `None` result as "idle" (sweep +
    sleep); a non-`None`-but-still-`created` result took the "made progress" branch
    instead, so a lost claim race re-polled the same losing candidate immediately, with
    no backoff at all, spinning the loop hot."""
    worker_holder: dict[str, Worker] = {}
    calls = {"count": 0}
    lost_race_job = _job("scenario_lost_race")

    class StoppingReconciler:
        def reconcile_once(self) -> int:
            calls["count"] += 1
            # Stop after the pre-loop sweep and exactly one idle-iteration sweep --
            # deterministic, unlike racing against wall-clock sleeps. If the backoff
            # branch were skipped (the bug), this reconciler would never be called a
            # second time and the loop would spin until this test's own timeout.
            if calls["count"] >= 2:
                worker_holder["worker"].request_shutdown()
            return 0

    class AlwaysSameCandidateQueue:
        def next_message(self) -> WorkflowJobMessage | None:
            return WorkflowJobMessage(job_id=lost_race_job.id)

    class LostRaceHandler:
        async def handle(self, job_id: str) -> Any:
            del job_id
            return lost_race_job

        def cancel(self, job_id: str) -> None:
            del job_id

        def dispose(self) -> None:
            pass

    worker = Worker(
        LostRaceHandler(),
        job_queue=AlwaysSameCandidateQueue(),
        poll_interval_seconds=0,
        reconciler=StoppingReconciler(),
    )
    worker_holder["worker"] = worker

    asyncio.run(asyncio.wait_for(worker.run_forever(), timeout=5))

    assert calls["count"] == 2


def test_sweep_orphaned_jobs_survives_reconciler_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class ExplodingReconciler:
        def reconcile_once(self) -> int:
            raise RuntimeError("boom")

    worker = Worker(
        None,  # type: ignore[arg-type]  # _sweep_orphaned_jobs() never touches this
        reconciler=ExplodingReconciler(),
    )

    worker._sweep_orphaned_jobs()

    assert "worker.reconciliation_sweep_failed" in caplog.text
