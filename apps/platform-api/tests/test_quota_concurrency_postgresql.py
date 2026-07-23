from __future__ import annotations

import asyncio
import os
from dataclasses import replace
from http import HTTPStatus
from uuid import uuid4

import httpx
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from anytoolai_platform_api.routers.handoffs import _service as _handoff_service
from anytoolai_platform_core.handoffs.models import AcceptHandoffCommand
from anytoolai_platform_core.handoffs.service import HandoffAcceptanceExecutionError
from anytoolai_platform_core.storage.db import (
    event_log_table,
    guest_quota_usage_table,
    jobs_table,
    product_handoffs_table,
    scenario_sessions_table,
)
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)
from sqlalchemy.engine import URL, make_url
from test_handoffs_api import _create as _create_handoff
from test_handoffs_api import _seed_source as _seed_handoff_source
from test_scenario_runtime_api import (
    REPO_ROOT,
    _create_test_app,
    _start_payload,
)

POSTGRES_TEST_DATABASE_URL_ENV = "ANYTOOLAI_POSTGRES_TEST_DATABASE_URL"
SCENARIO_START_QUOTA_LIMIT = 3


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
                            headers={"X-Request-ID": f"req_pg_quota_parallel_{index}"},
                        )
                        for index in range(request_count)
                    ]
                )

        responses = asyncio.run(start_many())
        status_codes = [response.status_code for response in responses]

        assert status_codes.count(HTTPStatus.OK) == SCENARIO_START_QUOTA_LIMIT
        assert (
            status_codes.count(HTTPStatus.TOO_MANY_REQUESTS)
            == request_count - SCENARIO_START_QUOTA_LIMIT
        )
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
            event_types = list(session.execute(sa.select(event_log_table.c.event_type)).scalars())

        assert scenario_count == SCENARIO_START_QUOTA_LIMIT
        assert job_count == SCENARIO_START_QUOTA_LIMIT
        assert usage["used_count"] == SCENARIO_START_QUOTA_LIMIT
        assert usage["limit_count"] == SCENARIO_START_QUOTA_LIMIT
        assert event_types.count("quota.consumed") == SCENARIO_START_QUOTA_LIMIT
        assert event_types.count("quota.exhausted") == request_count - SCENARIO_START_QUOTA_LIMIT
    finally:
        engine.dispose()
        _drop_database(maintenance_url, database_name)


@pytest.mark.postgresql
@pytest.mark.slow
def test_postgresql_parallel_handoff_accept_creates_one_target() -> None:
    maintenance_url = _require_postgres_test_url()
    database_name = f"anytoolai_a17_handoff_test_{uuid4().hex[:12]}"
    test_url = maintenance_url.set(database=database_name)
    _create_database(maintenance_url, database_name)
    engine = sa.create_engine(test_url, future=True)
    try:
        _upgrade_database(engine, test_url)
        session_factory = build_session_factory(engine)
        app = _create_test_app(session_factory)
        with transaction_boundary(session_factory) as session:
            source_session_id, artifact_id = _seed_handoff_source(session)
        created = _create_handoff(app, source_session_id, artifact_id).json()

        async def accept_twice() -> list[httpx.Response]:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                path = f"/v1/handoffs/{created['handoff_token']}/accept"
                return await asyncio.gather(
                    client.post(path, json={}, headers={"X-Request-ID": "req_pg_handoff_1"}),
                    client.post(path, json={}, headers={"X-Request-ID": "req_pg_handoff_2"}),
                )

        responses = asyncio.run(accept_twice())
        assert sorted(response.status_code for response in responses) == [200, 409]
        with transaction_boundary(session_factory) as session:
            handoff = (
                session.execute(
                    sa.select(product_handoffs_table).where(
                        product_handoffs_table.c.id == created["handoff_id"]
                    )
                )
                .mappings()
                .one()
            )
            target_session_count = session.execute(
                sa.select(sa.func.count())
                .select_from(scenario_sessions_table)
                .where(scenario_sessions_table.c.parent_scenario_session_id == source_session_id)
            ).scalar_one()
            target_job_count = session.execute(
                sa.select(sa.func.count())
                .select_from(jobs_table)
                .where(jobs_table.c.scenario_session_id == handoff["target_scenario_session_id"])
            ).scalar_one()
            accepted_events = session.execute(
                sa.select(sa.func.count())
                .select_from(event_log_table)
                .where(
                    event_log_table.c.event_type == "handoff.accepted",
                    event_log_table.c.handoff_id == created["handoff_id"],
                )
            ).scalar_one()
        assert handoff["status"] == "consumed"
        assert target_session_count == 1
        assert target_job_count == 1
        assert accepted_events == 1
    finally:
        engine.dispose()
        _drop_database(maintenance_url, database_name)


@pytest.mark.postgresql
@pytest.mark.slow
def test_postgresql_parallel_exhausted_handoff_accept_recovers_quota_once() -> None:
    maintenance_url = _require_postgres_test_url()
    database_name = f"anytoolai_a17_handoff_exhausted_test_{uuid4().hex[:12]}"
    test_url = maintenance_url.set(database=database_name)
    _create_database(maintenance_url, database_name)
    engine = sa.create_engine(test_url, future=True)
    try:
        _upgrade_database(engine, test_url)
        session_factory = build_session_factory(engine)
        app = _create_test_app(session_factory)
        registry = app.state.runtime.config_registry
        policy = registry.get_quota_policy("kernel_demo.guest_quota_v1")
        assert policy is not None
        app.state.runtime = replace(
            app.state.runtime,
            config_registry=replace(
                registry,
                quotas={
                    **dict(registry.quotas),
                    policy.quota_policy_id: replace(policy, limit_count=0),
                },
            ),
        )
        with transaction_boundary(session_factory) as session:
            source_session_id, artifact_id = _seed_handoff_source(session)
        created = _create_handoff(app, source_session_id, artifact_id).json()
        request_count = 8

        async def accept_many() -> list[httpx.Response]:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                path = f"/v1/handoffs/{created['handoff_token']}/accept"
                return await asyncio.gather(
                    *[
                        client.post(
                            path,
                            json={},
                            headers={"X-Request-ID": f"req_pg_handoff_exhausted_{index}"},
                        )
                        for index in range(request_count)
                    ]
                )

        responses = asyncio.run(accept_many())
        assert any(
            response.status_code == HTTPStatus.TOO_MANY_REQUESTS
            and response.json()["error"]["code"] == "quota_exhausted"
            for response in responses
        )
        assert all(
            response.status_code in {HTTPStatus.CONFLICT, HTTPStatus.TOO_MANY_REQUESTS}
            for response in responses
        )

        with transaction_boundary(session_factory) as session:
            handoff = (
                session.execute(
                    sa.select(product_handoffs_table).where(
                        product_handoffs_table.c.id == created["handoff_id"]
                    )
                )
                .mappings()
                .one()
            )
            quota_event_types = list(
                session.execute(
                    sa.select(event_log_table.c.event_type).where(
                        event_log_table.c.handoff_id == created["handoff_id"],
                        event_log_table.c.event_type.in_(["quota.checked", "quota.exhausted"]),
                    )
                ).scalars()
            )
            handoff_failed_count = session.execute(
                sa.select(sa.func.count())
                .select_from(event_log_table)
                .where(
                    event_log_table.c.handoff_id == created["handoff_id"],
                    event_log_table.c.event_type == "handoff.failed",
                )
            ).scalar_one()
            target_session_count = session.execute(
                sa.select(sa.func.count())
                .select_from(scenario_sessions_table)
                .where(scenario_sessions_table.c.parent_scenario_session_id == source_session_id)
            ).scalar_one()
            usage = session.execute(sa.select(guest_quota_usage_table)).mappings().one()

        assert handoff["status"] == "failed"
        assert handoff["error_code"] == "quota_exhausted"
        assert quota_event_types.count("quota.checked") == 1
        assert quota_event_types.count("quota.exhausted") == 1
        assert handoff_failed_count == 1
        assert target_session_count == 0
        assert usage["limit_count"] == 0
        assert usage["used_count"] == 0
    finally:
        engine.dispose()
        _drop_database(maintenance_url, database_name)


@pytest.mark.postgresql
@pytest.mark.slow
def test_postgresql_quota_recovery_finalizes_without_router_transaction() -> None:
    maintenance_url = _require_postgres_test_url()
    database_name = f"anytoolai_a17_handoff_reservation_test_{uuid4().hex[:12]}"
    test_url = maintenance_url.set(database=database_name)
    _create_database(maintenance_url, database_name)
    engine = sa.create_engine(test_url, future=True)
    try:
        _upgrade_database(engine, test_url)
        session_factory = build_session_factory(engine)
        app = _create_test_app(session_factory)
        registry = app.state.runtime.config_registry
        policy = registry.get_quota_policy("kernel_demo.guest_quota_v1")
        assert policy is not None
        app.state.runtime = replace(
            app.state.runtime,
            config_registry=replace(
                registry,
                quotas={
                    **dict(registry.quotas),
                    policy.quota_policy_id: replace(policy, limit_count=0),
                },
            ),
        )
        with transaction_boundary(session_factory) as session:
            source_session_id, artifact_id = _seed_handoff_source(session)
        created = _create_handoff(app, source_session_id, artifact_id).json()

        with (
            pytest.raises(HandoffAcceptanceExecutionError) as acceptance_error,
            transaction_boundary(session_factory) as session,
        ):
            _handoff_service(
                session,
                app.state.runtime.config_registry,
            ).accept(
                created["handoff_token"],
                AcceptHandoffCommand(
                    tenant_id="anytoolai",
                    region="default",
                ),
            )
        assert acceptance_error.value.error_code == "quota_exhausted"

        with transaction_boundary(session_factory) as session:
            handoff = (
                session.execute(
                    sa.select(product_handoffs_table).where(
                        product_handoffs_table.c.id == created["handoff_id"]
                    )
                )
                .mappings()
                .one()
            )
            event_types = list(
                session.execute(
                    sa.select(event_log_table.c.event_type).where(
                        event_log_table.c.handoff_id == created["handoff_id"]
                    )
                ).scalars()
            )

        assert handoff["status"] == "failed"
        assert handoff["error_code"] == "quota_exhausted"
        assert event_types.count("handoff.failed") == 1
        assert event_types.count("quota.checked") == 1
        assert event_types.count("quota.exhausted") == 1

        with transaction_boundary(session_factory) as session:
            repeated = _handoff_service(
                session,
                app.state.runtime.config_registry,
            ).mark_failed(
                created["handoff_id"],
                tenant_id="anytoolai",
                region="default",
                error_code="quota_exhausted",
            )
            handoff_failed_count = session.execute(
                sa.select(sa.func.count())
                .select_from(event_log_table)
                .where(
                    event_log_table.c.handoff_id == created["handoff_id"],
                    event_log_table.c.event_type == "handoff.failed",
                )
            ).scalar_one()

        assert repeated.status.value == "failed"
        assert handoff_failed_count == 1
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
