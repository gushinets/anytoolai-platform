from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from anytoolai_platform_core.actions.models import ActionRunRecord, ActionRunStatus
from anytoolai_platform_core.actions.repository import ActionRunRepository
from anytoolai_platform_core.artifacts.models import ArtifactRecord, ArtifactStatus
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.providers.models import ProviderCallRecord, ProviderCallStatus
from anytoolai_platform_core.providers.repository import ProviderCallRepository
from anytoolai_platform_core.scenarios.models import (
    ScenarioSessionRecord,
    ScenarioSessionStatus,
)
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.db import (
    action_runs_table,
    artifacts_table,
    jobs_table,
    provider_calls_table,
    scenario_sessions_table,
)
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

PROVIDER_INPUT_TOKENS = 128
PROVIDER_OUTPUT_TOKENS = 64
PROVIDER_LATENCY_MS = 950


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _sqlite_url(database_path: Path) -> str:
    return f"sqlite+pysqlite:///{database_path.resolve().as_posix()}"


@pytest.fixture
def runtime_engine(tmp_path: Path) -> sa.Engine:
    main_db = tmp_path / "runtime-main.sqlite3"
    platform_db = tmp_path / "runtime-platform.sqlite3"

    engine = sa.create_engine(_sqlite_url(main_db), future=True)

    @event.listens_for(engine, "connect")
    def attach_platform_schema(dbapi_connection: Any, connection_record: Any) -> None:
        dbapi_connection.execute(
            f"ATTACH DATABASE '{platform_db.resolve().as_posix()}' AS platform"
        )

    alembic_config = Config()
    alembic_config.set_main_option(
        "script_location", str(_repo_root() / "migrations" / "platform")
    )
    alembic_config.set_main_option("sqlalchemy.url", _sqlite_url(main_db))

    with engine.begin() as connection:
        alembic_config.attributes["connection"] = connection
        command.upgrade(alembic_config, "0001")

    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(runtime_engine: sa.Engine) -> sa.orm.sessionmaker[sa.orm.Session]:
    return build_session_factory(runtime_engine)


def make_scenario_session(**overrides: Any) -> ScenarioSessionRecord:
    values = {
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_id": "smoke_start",
        "scenario_version": 1,
    }
    values.update(overrides)
    return ScenarioSessionRecord(**values)


def make_job(scenario_session_id: str, **overrides: Any) -> JobRecord:
    values = {
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_session_id": scenario_session_id,
        "workflow_id": "wf_smoke",
        "workflow_version": 1,
    }
    values.update(overrides)
    return JobRecord(**values)


def make_action_run(scenario_session_id: str, job_id: str, **overrides: Any) -> ActionRunRecord:
    values = {
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_session_id": scenario_session_id,
        "job_id": job_id,
        "workflow_id": "wf_smoke",
        "step_id": "step_1",
        "action_type": "text.extract_structured_fields",
        "action_config_id": "cfg_extract",
    }
    values.update(overrides)
    return ActionRunRecord(**values)


def make_provider_call(
    scenario_session_id: str, job_id: str, action_run_id: str, **overrides: Any
) -> ProviderCallRecord:
    values = {
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_session_id": scenario_session_id,
        "job_id": job_id,
        "action_run_id": action_run_id,
        "workflow_id": "wf_smoke",
        "step_id": "step_1",
        "action_type": "text.extract_structured_fields",
        "action_config_id": "cfg_extract",
        "provider_policy_id": "policy_primary",
        "provider": "openai",
        "model": "gpt-5-mini",
    }
    values.update(overrides)
    return ProviderCallRecord(**values)


def make_artifact(scenario_session_id: str, **overrides: Any) -> ArtifactRecord:
    values = {
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_session_id": scenario_session_id,
        "artifact_type": "structured_output",
    }
    values.update(overrides)
    return ArtifactRecord(**values)


def seed_runtime_chain(
    session: sa.orm.Session,
) -> tuple[ScenarioSessionRecord, JobRecord, ActionRunRecord]:
    scenario_session = ScenarioSessionRepository(session).create(make_scenario_session())
    job = JobRepository(session).create(make_job(scenario_session.id))
    action_run = ActionRunRepository(session).create(make_action_run(scenario_session.id, job.id))
    return scenario_session, job, action_run


def scenario_session_scope(record: ScenarioSessionRecord) -> dict[str, str]:
    return {
        "tenant_id": record.tenant_id,
        "region": record.region,
        "product_id": record.product_id,
        "frontend_id": record.frontend_id,
    }


ROUND_TRIP_REPOSITORY_CASES = [
    pytest.param(
        ScenarioSessionRepository,
        make_scenario_session,
        lambda record: replace(record, status=ScenarioSessionStatus.running),
        id="scenario_session",
    ),
    pytest.param(
        JobRepository,
        lambda: make_job("scenario_session_demo"),
        lambda record: replace(record, status=JobStatus.running),
        id="job",
    ),
    pytest.param(
        ActionRunRepository,
        lambda: make_action_run("scenario_session_demo", "job_demo"),
        lambda record: replace(record, status=ActionRunStatus.running),
        id="action_run",
    ),
    pytest.param(
        ProviderCallRepository,
        lambda: make_provider_call("scenario_session_demo", "job_demo", "action_run_demo"),
        lambda record: replace(record, status=ProviderCallStatus.running),
        id="provider_call",
    ),
    pytest.param(
        ArtifactRepository,
        lambda: make_artifact("scenario_session_demo"),
        lambda record: replace(record, status=ArtifactStatus.stored),
        id="artifact",
    ),
]


def test_runtime_table_enums_create_check_constraints() -> None:
    status_columns = [
        scenario_sessions_table.c.status,
        jobs_table.c.status,
        action_runs_table.c.status,
        provider_calls_table.c.status,
        artifacts_table.c.status,
    ]

    for column in status_columns:
        assert isinstance(column.type, sa.Enum)
        assert column.type.create_constraint is True


def test_runtime_migration_applies_on_a_clean_database(runtime_engine: sa.Engine) -> None:
    with runtime_engine.connect() as connection:
        table_names = set(
            connection.execute(
                sa.text("SELECT name FROM platform.sqlite_master WHERE type = 'table'")
            ).scalars()
        )
        index_names = set(
            connection.execute(
                sa.text("SELECT name FROM platform.sqlite_master WHERE type = 'index'")
            ).scalars()
        )

    assert {
        "scenario_sessions",
        "jobs",
        "action_runs",
        "provider_calls",
        "artifacts",
    }.issubset(table_names)
    assert {
        "ix_jobs_scenario_session_id",
        "ix_action_runs_job_id",
        "ix_provider_calls_job_id",
        "ix_artifacts_job_id",
        "ix_jobs_status",
    }.issubset(index_names)


def test_repositories_respect_explicit_transaction_boundary(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    pending_record = make_scenario_session()

    write_session = session_factory()
    try:
        created = ScenarioSessionRepository(write_session).create(pending_record)

        read_session = session_factory()
        try:
            assert (
                ScenarioSessionRepository(read_session).get(
                    created.id,
                    **scenario_session_scope(created),
                )
                is None
            )
        finally:
            read_session.close()

        write_session.commit()

        committed_session = session_factory()
        try:
            assert (
                ScenarioSessionRepository(committed_session).get(
                    created.id,
                    **scenario_session_scope(created),
                )
                == created
            )
        finally:
            committed_session.close()
    finally:
        write_session.close()


@pytest.mark.parametrize(
    ("repository_type", "record_factory", "update_factory"),
    ROUND_TRIP_REPOSITORY_CASES,
)
def test_repositories_raise_explicit_error_when_round_trip_read_missing_on_create(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    monkeypatch: pytest.MonkeyPatch,
    repository_type: type[
        ScenarioSessionRepository
        | JobRepository
        | ActionRunRepository
        | ProviderCallRepository
        | ArtifactRepository
    ],
    record_factory: Any,
    update_factory: Any,
) -> None:
    del update_factory
    session = session_factory()
    try:
        repository = repository_type(session)
        monkeypatch.setattr(repository, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(RuntimeError, match="round-trip failed after create"):
            repository.create(record_factory())
    finally:
        session.rollback()
        session.close()


@pytest.mark.parametrize(
    ("repository_type", "record_factory", "update_factory"),
    ROUND_TRIP_REPOSITORY_CASES,
)
def test_repositories_raise_explicit_error_when_round_trip_read_missing_on_update(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    monkeypatch: pytest.MonkeyPatch,
    repository_type: type[
        ScenarioSessionRepository
        | JobRepository
        | ActionRunRepository
        | ProviderCallRepository
        | ArtifactRepository
    ],
    record_factory: Any,
    update_factory: Any,
) -> None:
    session = session_factory()
    try:
        repository = repository_type(session)
        created = repository.create(record_factory())

        with pytest.raises(RuntimeError, match="round-trip failed after update"):
            if isinstance(repository, ScenarioSessionRepository):
                get_results = iter([created, None])
                monkeypatch.setattr(
                    repository,
                    "get",
                    lambda *_args, **_kwargs: next(get_results),
                )
                repository.update(
                    update_factory(created),
                    **scenario_session_scope(created),
                )
            else:
                monkeypatch.setattr(repository, "get", lambda *_args, **_kwargs: None)
                repository.update(update_factory(created))
    finally:
        session.rollback()
        session.close()


def test_scenario_session_repository_create_read_update(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        repository = ScenarioSessionRepository(session)
        created = repository.create(make_scenario_session())

        assert created.id.startswith("scenario_session_")
        assert created.status is ScenarioSessionStatus.started
        assert created.started_at.tzinfo is not None

        stored = repository.get(created.id, **scenario_session_scope(created))
        assert stored == created

        completed = repository.update(
            replace(
                created,
                status=ScenarioSessionStatus.completed,
                completed_at=utc_now(),
                current_step="done",
            ),
            **scenario_session_scope(created),
        )

        assert completed.status is ScenarioSessionStatus.completed
        assert completed.current_step == "done"
        assert completed.completed_at is not None


def test_scenario_session_repository_get_is_scope_bound(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        repository = ScenarioSessionRepository(session)
        created = repository.create(make_scenario_session())

        assert repository.get(created.id, **scenario_session_scope(created)) == created
        assert (
            repository.get(
                created.id,
                tenant_id="tenant_other",
                region=created.region,
                product_id=created.product_id,
                frontend_id=created.frontend_id,
            )
            is None
        )


def test_scenario_session_repository_update_does_not_mutate_scope_columns(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        repository = ScenarioSessionRepository(session)
        created = repository.create(make_scenario_session())

        updated = repository.update(
            replace(
                created,
                tenant_id="tenant_other",
                region="us-west",
                product_id="product_other",
                frontend_id="frontend_other",
                current_step="done",
            ),
            **scenario_session_scope(created),
        )

        assert updated.tenant_id == created.tenant_id
        assert updated.region == created.region
        assert updated.product_id == created.product_id
        assert updated.frontend_id == created.frontend_id
        assert updated.current_step == "done"


def test_scenario_session_repository_required_fields(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    broken = make_scenario_session(tenant_id=None)  # type: ignore[arg-type]
    session = session_factory()
    try:
        with pytest.raises(IntegrityError):
            ScenarioSessionRepository(session).create(broken)
    finally:
        session.rollback()
        session.close()


def test_job_repository_create_read_update(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        scenario_session = ScenarioSessionRepository(session).create(make_scenario_session())
        repository = JobRepository(session)
        created = repository.create(make_job(scenario_session.id))

        assert created.id.startswith("job_")
        assert created.status is JobStatus.created
        assert repository.get(created.id) == created

        updated = repository.update(
            replace(
                created,
                status=JobStatus.succeeded,
                started_at=utc_now(),
                completed_at=utc_now(),
                result_artifact_id="artifact_result",
            )
        )

        assert updated.status is JobStatus.succeeded
        assert updated.result_artifact_id == "artifact_result"
        assert updated.completed_at is not None


def test_job_repository_required_fields(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    broken = make_job(scenario_session_id=None)  # type: ignore[arg-type]
    session = session_factory()
    try:
        with pytest.raises(IntegrityError):
            JobRepository(session).create(broken)
    finally:
        session.rollback()
        session.close()


def test_action_run_repository_create_read_update(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        scenario_session, job, _ = seed_runtime_chain(session)
        repository = ActionRunRepository(session)
        created = repository.create(
            make_action_run(
                scenario_session.id,
                job.id,
                step_id="step_2",
                action_config_id="cfg_validate",
            )
        )

        assert created.id.startswith("action_run_")
        assert created.status is ActionRunStatus.created
        assert repository.get(created.id) == created

        updated = repository.update(
            replace(
                created,
                status=ActionRunStatus.succeeded,
                started_at=utc_now(),
                completed_at=utc_now(),
                output_artifact_id="artifact_output",
            )
        )

        assert updated.status is ActionRunStatus.succeeded
        assert updated.output_artifact_id == "artifact_output"


def test_action_run_repository_required_fields(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    broken = make_action_run("session_demo", None)  # type: ignore[arg-type]
    session = session_factory()
    try:
        with pytest.raises(IntegrityError):
            ActionRunRepository(session).create(broken)
    finally:
        session.rollback()
        session.close()


def test_provider_call_repository_create_read_update(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        scenario_session, job, action_run = seed_runtime_chain(session)
        repository = ProviderCallRepository(session)
        created = repository.create(
            make_provider_call(scenario_session.id, job.id, action_run.id)
        )

        assert created.id.startswith("provider_call_")
        assert created.status is ProviderCallStatus.created
        assert repository.get(created.id) == created

        updated = repository.update(
            replace(
                created,
                status=ProviderCallStatus.succeeded,
                started_at=utc_now(),
                completed_at=utc_now(),
                input_tokens=PROVIDER_INPUT_TOKENS,
                output_tokens=PROVIDER_OUTPUT_TOKENS,
                latency_ms=PROVIDER_LATENCY_MS,
                estimated_cost=0.014,
            )
        )

        assert updated.status is ProviderCallStatus.succeeded
        assert updated.input_tokens == PROVIDER_INPUT_TOKENS
        assert updated.output_tokens == PROVIDER_OUTPUT_TOKENS
        assert updated.latency_ms == PROVIDER_LATENCY_MS


def test_provider_call_repository_required_fields(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    broken = make_provider_call("session_demo", "job_demo", "action_demo", provider=None)  # type: ignore[arg-type]
    session = session_factory()
    try:
        with pytest.raises(IntegrityError):
            ProviderCallRepository(session).create(broken)
    finally:
        session.rollback()
        session.close()


def test_artifact_repository_text_storage_and_status_transition(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        scenario_session, job, action_run = seed_runtime_chain(session)
        repository = ArtifactRepository(session)
        created = repository.create(
            make_artifact(
                scenario_session.id,
                job_id=job.id,
                action_run_id=action_run.id,
            )
        )

        assert created.id.startswith("artifact_")
        assert created.status is ArtifactStatus.created

        stored = repository.update(
            replace(
                created,
                status=ArtifactStatus.stored,
                content_text="rendered text artifact",
            )
        )

        assert repository.get(created.id) == stored
        assert stored.status is ArtifactStatus.stored
        assert stored.content_text == "rendered text artifact"
        assert stored.content_json is None
        assert (
            session.execute(
                sa.select(artifacts_table.c.content_json.is_(None)).where(
                    artifacts_table.c.id == created.id
                )
            ).scalar_one()
            is True
        )


def test_artifact_repository_json_storage(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        scenario_session, job, action_run = seed_runtime_chain(session)
        repository = ArtifactRepository(session)
        stored = repository.create(
            make_artifact(
                scenario_session.id,
                job_id=job.id,
                action_run_id=action_run.id,
                status=ArtifactStatus.stored,
                content_json={"summary": "ok", "score": 0.98},
            )
        )

        assert stored.status is ArtifactStatus.stored
        assert stored.content_json == {"summary": "ok", "score": 0.98}
        assert stored.content_text is None


def test_artifact_repository_required_fields(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    broken = make_artifact("session_demo", artifact_type=None)  # type: ignore[arg-type]
    session = session_factory()
    try:
        with pytest.raises(IntegrityError):
            ArtifactRepository(session).create(broken)
    finally:
        session.rollback()
        session.close()
