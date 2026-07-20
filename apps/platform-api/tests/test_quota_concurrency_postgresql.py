from __future__ import annotations

import asyncio
import os
from http import HTTPStatus
from uuid import uuid4

import httpx
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from anytoolai_platform_core.storage.db import (
    event_log_table,
    guest_quota_usage_table,
    jobs_table,
    scenario_sessions_table,
)
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)
from sqlalchemy.engine import URL, make_url
from test_scenario_runtime_api import (
    CONFIG_ROOT,
    REPO_ROOT,
    _create_test_app,
    _start_payload,
)

POSTGRES_TEST_DATABASE_URL_ENV = "ANYTOOLAI_POSTGRES_TEST_DATABASE_URL"


@pytest.mark.postgresql
@pytest.mark.slow
def test_postgresql_parallel_scenario_starts_consume_quota_exactly_once() -> None:
    """Production-semantics quota check for PostgreSQL row locks and conditional updates.

    Set ANYTOOLAI_POSTGRES_TEST_DATABASE_URL to a PostgreSQL maintenance database URL. The test
    creates and drops its own disposable database, then runs the real Alembic migration chain.
    """

    maintenance_url = _require_postgres_test_url()
    database_name = f"anytoolai_a13_quota_test_{uuid4().hex[:12]}"
    test_url = maintenance_url.set(database=database_name)
    _create_database(maintenance_url, database_name)
    engine = sa.create_engine(test_url, future=True)
    try:
        _upgrade_database(engine, test_url)
        session_factory = build_session_factory(engine)
        app = _create_test_app(session_factory)
        request_count = 16

        async def start_many() -> list[httpx.Response]:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await asyncio.gather(
                    *[
                        client.post(
                            "/v1/products/kernel_demo/scenarios/"
                            "kernel_demo.single_action_smoke_v1/start",
                            json=_start_payload(),
                            headers={
                                "X-Request-ID": f"req_pg_quota_parallel_{index}"
                            },
                        )
                        for index in range(request_count)
                    ]
                )

        responses = asyncio.run(start_many())
        status_codes = [response.status_code for response in responses]

        assert status_codes.count(HTTPStatus.OK) == 3
        assert status_codes.count(HTTPStatus.TOO_MANY_REQUESTS) == request_count - 3
        assert all(
            response.json()["error"]["code"] == "quota_exhausted"
            for response in responses
            if response.status_code == HTTPStatus.TOO_MANY_REQUESTS
        )

        with transaction_boundary(session_factory) as session:
            scenario_count = session.execute(
                sa.select(sa.func.count()).select_from(scenario_sessions_table)
            ).scalar_one()
            job_count = session.execute(
                sa.select(sa.func.count()).select_from(jobs_table)
            ).scalar_one()
            usage = session.execute(sa.select(guest_quota_usage_table)).mappings().one()
            event_types = list(
                session.execute(sa.select(event_log_table.c.event_type)).scalars()
            )

        assert scenario_count == 3
        assert job_count == 3
        assert usage["used_count"] == 3
        assert usage["limit_count"] == 3
        assert event_types.count("quota.consumed") == 3
        assert event_types.count("quota.exhausted") == request_count - 3
    finally:
        engine.dispose()
        _drop_database(maintenance_url, database_name)


def _require_postgres_test_url() -> URL:
    raw_url = os.getenv(POSTGRES_TEST_DATABASE_URL_ENV)
    if not raw_url:
        pytest.skip(
            f"set {POSTGRES_TEST_DATABASE_URL_ENV} to run PostgreSQL quota concurrency coverage"
        )
    url = make_url(raw_url)
    if not url.drivername.startswith("postgresql"):
        pytest.fail(f"{POSTGRES_TEST_DATABASE_URL_ENV} must use a PostgreSQL dialect")
    if not url.database:
        pytest.fail(f"{POSTGRES_TEST_DATABASE_URL_ENV} must name a maintenance database")
    return url


def _upgrade_database(engine: sa.Engine, database_url: URL) -> None:
    alembic_config = Config()
    alembic_config.set_main_option(
        "script_location",
        str(REPO_ROOT / "migrations" / "platform"),
    )
    alembic_config.set_main_option(
        "sqlalchemy.url",
        database_url.render_as_string(hide_password=False),
    )
    with engine.begin() as connection:
        alembic_config.attributes["connection"] = connection
        command.upgrade(alembic_config, "head")


def _create_database(maintenance_url: URL, database_name: str) -> None:
    engine = sa.create_engine(
        maintenance_url,
        future=True,
        isolation_level="AUTOCOMMIT",
    )
    try:
        with engine.connect() as connection:
            connection.execute(sa.text(f"CREATE DATABASE {_quote_identifier(database_name)}"))
    except sa.exc.OperationalError as exc:
        pytest.fail(f"could not connect to PostgreSQL test database: {exc}")
    finally:
        engine.dispose()


def _drop_database(maintenance_url: URL, database_name: str) -> None:
    engine = sa.create_engine(
        maintenance_url,
        future=True,
        isolation_level="AUTOCOMMIT",
    )
    try:
        with engine.connect() as connection:
            connection.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.execute(
                sa.text(f"DROP DATABASE IF EXISTS {_quote_identifier(database_name)}")
            )
    finally:
        engine.dispose()


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'
