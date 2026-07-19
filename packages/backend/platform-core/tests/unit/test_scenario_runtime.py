from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from anytoolai_platform_core.artifacts.models import ArtifactRecord, ArtifactStatus
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.scenarios.checkpoints import (
    FAILED_CHECKPOINT_ID,
    PROCESSING_CHECKPOINT_ID,
    RESULT_READY_CHECKPOINT_ID,
    resolve_checkpoint_state,
    resolve_effective_status,
)
from anytoolai_platform_core.scenarios.models import (
    ScenarioSessionRecord,
    ScenarioSessionStatus,
)
from anytoolai_platform_core.scenarios.next_actions import (
    ScenarioCheckpointConflictError,
    ScenarioCheckpointNotActionableError,
    ScenarioNextActionNotAllowedError,
)
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.scenarios.service import (
    ScenarioNotFoundError,
    ScenarioRuntimeService,
    ScenarioSessionService,
)
from anytoolai_platform_core.storage.db import event_log_table
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from sqlalchemy import event

REPO_ROOT = Path(__file__).resolve().parents[5]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"


def _sqlite_url(database_path: Path) -> str:
    return f"sqlite+pysqlite:///{database_path.resolve().as_posix()}"


@pytest.fixture
def runtime_engine(tmp_path: Path) -> sa.Engine:
    main_db = tmp_path / "scenario-runtime-main.sqlite3"
    platform_db = tmp_path / "scenario-runtime-platform.sqlite3"
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

    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(runtime_engine: sa.Engine) -> sa.orm.sessionmaker[sa.orm.Session]:
    return build_session_factory(runtime_engine)


@pytest.fixture
def config_registry():
    return build_config_registry(CONFIG_ROOT)


def _runtime_service(
    session: sa.orm.Session,
    *,
    config_registry,
) -> ScenarioRuntimeService:
    event_emitter = EventEmitter(EventLogRepository(session))
    session_repository = ScenarioSessionRepository(session)
    return ScenarioRuntimeService(
        config_registry=config_registry,
        session_repository=session_repository,
        session_service=ScenarioSessionService(session_repository, event_emitter),
        job_repository=JobRepository(session),
        event_emitter=event_emitter,
    )


def test_start_session_creates_linked_session_and_job(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
) -> None:
    with transaction_boundary(session_factory) as session:
        service = _runtime_service(session, config_registry=config_registry)

        snapshot = service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
            guest_id="guest_demo",
        )

        scenario_session = ScenarioSessionRepository(session).get_in_scope(
            snapshot.scenario_session_id,
            tenant_id="anytoolai",
            region="default",
        )
        job = JobRepository(session).get(snapshot.job_id)

    assert snapshot.status is ScenarioSessionStatus.started
    assert snapshot.current_checkpoint_id == PROCESSING_CHECKPOINT_ID
    assert snapshot.allowed_next_actions == ()
    assert scenario_session is not None
    assert scenario_session.metadata["input"] == {
        "source_text": "deadline budget deliverables"
    }
    assert scenario_session.current_checkpoint_id == PROCESSING_CHECKPOINT_ID
    assert scenario_session.scenario_chain_id == scenario_session.id
    assert job is not None
    assert job.scenario_session_id == scenario_session.id
    assert job.product_id == scenario_session.product_id
    assert job.frontend_id == scenario_session.frontend_id
    assert job.metadata["guest_id"] == "guest_demo"
    assert job.metadata["scenario_chain_id"] == scenario_session.scenario_chain_id


def test_get_session_snapshot_returns_result_ready_checkpoint_and_artifact(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
) -> None:
    with transaction_boundary(session_factory) as session:
        service = _runtime_service(session, config_registry=config_registry)
        session_service = ScenarioSessionService(
            ScenarioSessionRepository(session),
            EventEmitter(EventLogRepository(session)),
        )
        started = service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
        )

        scenario_session = ScenarioSessionRepository(session).get_in_scope(
            started.scenario_session_id,
            tenant_id="anytoolai",
            region="default",
        )
        assert scenario_session is not None
        claimed_job = JobRepository(session).claim_created(started.job_id)
        assert claimed_job is not None
        scenario_session = session_service.mark_running(scenario_session)
        job = JobRepository(session).get(started.job_id)
        assert job is not None

        result_artifact = ArtifactRepository(session).create(
            ArtifactRecord(
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
        succeeded_job = JobRepository(session).mark_succeeded(
            replace(
                job,
                status=JobStatus.succeeded,
                result_artifact_id=result_artifact.id,
                completed_at=result_artifact.created_at,
            )
        )
        session_service.mark_completed(
            replace(
                scenario_session,
                completed_at=succeeded_job.completed_at,
            )
        )

        snapshot = service.get_session_snapshot(
            started.scenario_session_id,
            tenant_id="anytoolai",
            region="default",
        )

    assert snapshot.status is ScenarioSessionStatus.completed
    assert snapshot.current_checkpoint_id == RESULT_READY_CHECKPOINT_ID
    assert snapshot.result_artifact_id == result_artifact.id
    assert snapshot.allowed_next_actions == ("copy_result", "create_handoff")


def test_record_next_action_emits_event_and_validates_checkpoint(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
) -> None:
    with transaction_boundary(session_factory) as session:
        service = _runtime_service(session, config_registry=config_registry)
        session_service = ScenarioSessionService(
            ScenarioSessionRepository(session),
            EventEmitter(EventLogRepository(session)),
        )
        started = service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
        )
        scenario_session = ScenarioSessionRepository(session).get_in_scope(
            started.scenario_session_id,
            tenant_id="anytoolai",
            region="default",
        )
        assert scenario_session is not None
        claimed_job = JobRepository(session).claim_created(started.job_id)
        assert claimed_job is not None
        scenario_session = session_service.mark_running(scenario_session)
        job = JobRepository(session).get(started.job_id)
        assert job is not None
        result_artifact = ArtifactRepository(session).create(
            ArtifactRecord(
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
        succeeded_job = JobRepository(session).mark_succeeded(
            replace(
                job,
                status=JobStatus.succeeded,
                result_artifact_id=result_artifact.id,
                completed_at=result_artifact.created_at,
            )
        )
        session_service.mark_completed(
            replace(scenario_session, completed_at=succeeded_job.completed_at)
        )

        snapshot = service.record_next_action(
            started.scenario_session_id,
            tenant_id="anytoolai",
            region="default",
            next_action_id="copy_result",
            checkpoint_id=RESULT_READY_CHECKPOINT_ID,
        )

        event_row = session.execute(
            sa.select(event_log_table).where(
                event_log_table.c.event_type == "client.next_action_clicked"
            )
        ).mappings().one()

        with pytest.raises(ScenarioCheckpointConflictError):
            service.record_next_action(
                started.scenario_session_id,
                tenant_id="anytoolai",
                region="default",
                next_action_id="copy_result",
                checkpoint_id=FAILED_CHECKPOINT_ID,
            )

        with pytest.raises(ScenarioNextActionNotAllowedError):
            service.record_next_action(
                started.scenario_session_id,
                tenant_id="anytoolai",
                region="default",
                next_action_id="view_paywall",
                checkpoint_id=RESULT_READY_CHECKPOINT_ID,
            )

    assert snapshot.current_checkpoint_id == RESULT_READY_CHECKPOINT_ID
    assert event_row["scenario_session_id"] == started.scenario_session_id
    assert event_row["job_id"] == started.job_id
    assert event_row["properties"]["checkpoint_id"] == RESULT_READY_CHECKPOINT_ID
    assert event_row["properties"]["next_action_id"] == "copy_result"


def test_record_next_action_rejects_non_actionable_processing_checkpoint(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
) -> None:
    with transaction_boundary(session_factory) as session:
        service = _runtime_service(session, config_registry=config_registry)
        started = service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
        )

        with pytest.raises(ScenarioCheckpointNotActionableError):
            service.record_next_action(
                started.scenario_session_id,
                tenant_id="anytoolai",
                region="default",
                next_action_id="copy_result",
                checkpoint_id=PROCESSING_CHECKPOINT_ID,
            )


def test_get_session_snapshot_rejects_persisted_scenario_version_mismatch(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
) -> None:
    with transaction_boundary(session_factory) as session:
        service = _runtime_service(session, config_registry=config_registry)
        started = service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
        )
        scenario_session = ScenarioSessionRepository(session).get_in_scope(
            started.scenario_session_id,
            tenant_id="anytoolai",
            region="default",
        )
        assert scenario_session is not None
        ScenarioSessionRepository(session).update(
            replace(scenario_session, scenario_version=scenario_session.scenario_version + 1),
            tenant_id=scenario_session.tenant_id,
            region=scenario_session.region,
            product_id=scenario_session.product_id,
            frontend_id=scenario_session.frontend_id,
        )

        with pytest.raises(ScenarioNotFoundError):
            service.get_session_snapshot(
                started.scenario_session_id,
                tenant_id="anytoolai",
                region="default",
            )


def test_record_next_action_rejects_persisted_scenario_version_mismatch(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
) -> None:
    with transaction_boundary(session_factory) as session:
        service = _runtime_service(session, config_registry=config_registry)
        started = service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
        )
        scenario_session = ScenarioSessionRepository(session).get_in_scope(
            started.scenario_session_id,
            tenant_id="anytoolai",
            region="default",
        )
        assert scenario_session is not None
        ScenarioSessionRepository(session).update(
            replace(scenario_session, scenario_version=scenario_session.scenario_version + 1),
            tenant_id=scenario_session.tenant_id,
            region=scenario_session.region,
            product_id=scenario_session.product_id,
            frontend_id=scenario_session.frontend_id,
        )

        with pytest.raises(ScenarioNotFoundError):
            service.record_next_action(
                started.scenario_session_id,
                tenant_id="anytoolai",
                region="default",
                next_action_id="copy_result",
                checkpoint_id=PROCESSING_CHECKPOINT_ID,
            )


def test_checkpoint_resolution_falls_back_to_job_state(config_registry) -> None:
    scenario = config_registry.get_scenario("kernel_demo.single_action_smoke_v1")
    assert scenario is not None

    session = ScenarioSessionRecord(
        tenant_id="anytoolai",
        region="default",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_id=scenario.scenario_id,
        scenario_version=scenario.version,
        status=ScenarioSessionStatus.running,
        current_checkpoint_id=None,
    )
    succeeded_job = JobRecord(
        tenant_id="anytoolai",
        region="default",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_session_id=session.id,
        workflow_id=scenario.workflow_id,
        workflow_version=1,
        status=JobStatus.succeeded,
        result_artifact_id="artifact_result",
    )
    failed_job = replace(
        succeeded_job,
        status=JobStatus.failed,
        result_artifact_id=None,
    )

    succeeded_state = resolve_checkpoint_state(
        scenario=scenario,
        session=session,
        job=succeeded_job,
    )
    failed_state = resolve_checkpoint_state(
        scenario=scenario,
        session=session,
        job=failed_job,
    )

    assert resolve_effective_status(session=session, job=succeeded_job) is ScenarioSessionStatus.completed
    assert succeeded_state.checkpoint_id == RESULT_READY_CHECKPOINT_ID
    assert succeeded_state.allowed_next_actions == ("copy_result", "create_handoff")

    assert resolve_effective_status(session=session, job=failed_job) is ScenarioSessionStatus.failed
    assert failed_state.checkpoint_id == FAILED_CHECKPOINT_ID
    assert failed_state.allowed_next_actions == ()


def test_processing_checkpoint_does_not_override_terminal_canceled_job(config_registry) -> None:
    scenario = config_registry.get_scenario("kernel_demo.single_action_smoke_v1")
    assert scenario is not None

    session = ScenarioSessionRecord(
        tenant_id="anytoolai",
        region="default",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_id=scenario.scenario_id,
        scenario_version=scenario.version,
        status=ScenarioSessionStatus.started,
        current_checkpoint_id=PROCESSING_CHECKPOINT_ID,
    )
    canceled_job = JobRecord(
        tenant_id="anytoolai",
        region="default",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_session_id=session.id,
        workflow_id=scenario.workflow_id,
        workflow_version=1,
        status=JobStatus.canceled,
    )

    checkpoint_state = resolve_checkpoint_state(
        scenario=scenario,
        session=session,
        job=canceled_job,
    )

    assert resolve_effective_status(session=session, job=canceled_job) is ScenarioSessionStatus.failed
    assert checkpoint_state.checkpoint_id == FAILED_CHECKPOINT_ID
    assert checkpoint_state.allowed_next_actions == ()
