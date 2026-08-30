from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path

import httpx
import pytest
import sqlalchemy as sa
from anytoolai_platform_api.bootstrap import RuntimeStorageDependencies
from anytoolai_platform_api.main import create_app
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.db import (
    guest_identities_table,
    jobs_table,
    scenario_sessions_table,
)
from anytoolai_platform_core.storage.transactions import (
    SessionFactory,
    build_session_factory,
    transaction_boundary,
)

from tests.db_support import provision_database

pytestmark = [pytest.mark.postgresql, pytest.mark.slow]

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
ACCESS_CODE = "stakeholder-code"
PARALLEL_REQUEST_COUNT = 4


@pytest.fixture
def session_factory() -> Iterator[SessionFactory]:
    with provision_database(
        database_name_prefix="anytoolai_demo_api_test",
        skip_reason="PostgreSQL stakeholder demo gate coverage",
    ) as (engine, _alembic_config, _database_url):
        yield build_session_factory(engine)


@pytest.fixture
def app(session_factory: SessionFactory, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANYTOOLAI_DEMO_ACCESS_CODE", ACCESS_CODE)
    monkeypatch.setenv("ANYTOOLAI_LIVE_CANARY_TOKEN", "server-live-token")
    application = create_app(config_root=CONFIG_ROOT)
    application.state.runtime = replace(
        application.state.runtime,
        storage=RuntimeStorageDependencies(session_factory=session_factory),
    )
    return application


async def _start(app, index: int) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        return await client.post(
            "/v1/demo/runs",
            json={"demo_id": "analyze", "source_text": f"Текст {index}"},
            headers={
                "X-Demo-Access-Code": ACCESS_CODE,
                "X-Request-ID": f"req_demo_pg_{index}",
            },
        )


def test_postgresql_demo_process_gate_accepts_only_one_parallel_start(
    app,
    session_factory: SessionFactory,
) -> None:
    async def start_parallel() -> list[httpx.Response]:
        return list(
            await asyncio.gather(*(_start(app, index) for index in range(PARALLEL_REQUEST_COUNT)))
        )

    responses = asyncio.run(start_parallel())

    assert [response.status_code for response in responses].count(HTTPStatus.OK) == 1
    assert [response.status_code for response in responses].count(HTTPStatus.CONFLICT) == (
        PARALLEL_REQUEST_COUNT - 1
    )
    with transaction_boundary(session_factory) as session:
        counts = [
            session.execute(sa.select(sa.func.count()).select_from(table)).scalar_one()
            for table in (guest_identities_table, scenario_sessions_table, jobs_table)
        ]
    assert counts == [1, 1, 1]


def test_postgresql_demo_daily_gate_rejects_fifty_first_utc_run(
    app,
    session_factory: SessionFactory,
) -> None:
    with transaction_boundary(session_factory) as session:
        repository = ScenarioSessionRepository(session)
        for index in range(50):
            repository.create(
                ScenarioSessionRecord(
                    id=f"scenario_session_demo_pg_daily_{index}",
                    tenant_id="anytoolai",
                    region="default",
                    product_id="kernel_demo",
                    frontend_id="web_mirror",
                    scenario_id="kernel_demo.composite_evaluate_match_live_smoke_v1",
                    scenario_version=1,
                    created_at=datetime.now(UTC),
                )
            )

    response = asyncio.run(_start(app, 51))

    assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert response.json()["error"]["code"] == "demo_daily_limit_exhausted"
