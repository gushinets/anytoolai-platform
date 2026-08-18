from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import URL, make_url

from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.db import (
    action_runs_table,
    artifacts_table,
    event_log_table,
    provider_calls_table,
)
from anytoolai_platform_core.storage.transactions import SessionFactory, transaction_boundary
from anytoolai_platform_core.workflows.repository import JobRepository

REPO_ROOT = Path(__file__).resolve().parents[1]
POSTGRES_TEST_DATABASE_URL_ENV = "ANYTOOLAI_POSTGRES_TEST_DATABASE_URL"
PLACEHOLDER_POSTGRESQL_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"
MIGRATIONS_SCRIPT_LOCATION = REPO_ROOT / "migrations" / "platform"


def require_postgres_test_url(skip_reason: str) -> URL:
    raw_url = os.getenv(POSTGRES_TEST_DATABASE_URL_ENV)
    if not raw_url:
        pytest.skip(f"set {POSTGRES_TEST_DATABASE_URL_ENV} to run {skip_reason}")

    url = make_url(raw_url)
    if not url.drivername.startswith("postgresql"):
        pytest.fail(f"{POSTGRES_TEST_DATABASE_URL_ENV} must use a PostgreSQL dialect")
    if not url.database:
        pytest.fail(f"{POSTGRES_TEST_DATABASE_URL_ENV} must name a maintenance database")
    return url


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def build_alembic_config(database_url: str) -> Config:
    alembic_config = Config()
    alembic_config.set_main_option("script_location", str(MIGRATIONS_SCRIPT_LOCATION))
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    return alembic_config


def create_database(maintenance_url: URL, database_name: str) -> None:
    engine = sa.create_engine(maintenance_url, future=True, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.execute(sa.text(f"CREATE DATABASE {quote_identifier(database_name)}"))
    except sa.exc.OperationalError as exc:
        raise RuntimeError(f"could not create PostgreSQL test database: {exc}") from exc
    finally:
        engine.dispose()


def drop_database(maintenance_url: URL, database_name: str) -> None:
    engine = sa.create_engine(maintenance_url, future=True, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.execute(
                sa.text(
                    f"DROP DATABASE IF EXISTS {quote_identifier(database_name)} WITH (FORCE)"
                )
            )
    finally:
        engine.dispose()


@contextmanager
def provision_database(
    *,
    database_name_prefix: str,
    upgrade_target: str | None = "head",
    skip_reason: str,
) -> Iterator[tuple[sa.Engine, Config, URL]]:
    maintenance_url = require_postgres_test_url(skip_reason)
    database_name = f"{database_name_prefix}_{uuid4().hex[:12]}"
    test_url = maintenance_url.set(database=database_name)
    engine: sa.Engine | None = None
    setup_error: BaseException | None = None
    try:
        create_database(maintenance_url, database_name)
        engine = sa.create_engine(test_url, future=True)
        alembic_config = build_alembic_config(
            test_url.render_as_string(hide_password=False)
        )
        if upgrade_target is not None:
            with engine.begin() as connection:
                alembic_config.attributes["connection"] = connection
                command.upgrade(alembic_config, upgrade_target)
        yield engine, alembic_config, test_url
    except BaseException as exc:
        setup_error = exc
        raise
    finally:
        if engine is not None:
            engine.dispose()
        try:
            drop_database(maintenance_url, database_name)
        except Exception:
            if setup_error is None:
                raise


def assert_scenario_runtime_correlation(
    session_factory: SessionFactory,
    *,
    scenario_session_id: str,
    job_id: str,
    result_artifact_id: str,
    action_type: str,
    action_config_id: str,
    expected_event_types: set[str],
) -> None:
    """Asserts the full DB correlation a completed scenario run must leave behind: scenario
    session status, job linkage, and that action_run/provider_call/artifact all scope back to
    the same scenario_session_id/job_id, plus that expected_event_types is a subset of what was
    logged. Shared by every test that drives a scenario through the real API -> worker -> DB
    path and wants to assert this same shape, instead of each test re-querying the same six
    tables by hand.
    """
    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).get_in_scope(
            scenario_session_id,
            tenant_id="anytoolai",
            region="default",
        )
        job = JobRepository(session).get(job_id)
        action_run = (
            session.execute(sa.select(action_runs_table).where(action_runs_table.c.job_id == job_id))
            .mappings()
            .one()
        )
        provider_call = (
            session.execute(
                sa.select(provider_calls_table).where(provider_calls_table.c.job_id == job_id)
            )
            .mappings()
            .one()
        )
        artifacts = list(
            session.execute(
                sa.select(artifacts_table).where(artifacts_table.c.job_id == job_id)
            ).mappings()
        )
        events = list(
            session.execute(
                sa.select(event_log_table).where(
                    event_log_table.c.scenario_session_id == scenario_session_id
                )
            ).mappings()
        )

    assert scenario is not None
    assert scenario.status.value == "completed"
    assert job is not None
    assert job.scenario_session_id == scenario_session_id
    assert job.result_artifact_id == result_artifact_id

    assert action_run["scenario_session_id"] == scenario_session_id
    assert action_run["action_type"] == action_type
    assert action_run["action_config_id"] == action_config_id
    assert provider_call["scenario_session_id"] == scenario_session_id
    assert provider_call["job_id"] == job_id
    assert provider_call["action_run_id"] == action_run["id"]
    assert any(artifact["id"] == result_artifact_id for artifact in artifacts)
    result_artifact = next(
        artifact for artifact in artifacts if artifact["id"] == result_artifact_id
    )
    assert result_artifact["job_id"] == job_id
    assert result_artifact["scenario_session_id"] == scenario_session_id

    event_types = {event_row["event_type"] for event_row in events}
    assert expected_event_types.issubset(event_types)
    for event_row in events:
        if event_row["job_id"] is not None:
            assert event_row["job_id"] == job_id
