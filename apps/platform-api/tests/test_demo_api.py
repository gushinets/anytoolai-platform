from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx
import pytest
import sqlalchemy as sa
from anytoolai_platform_api.bootstrap import RuntimeStorageDependencies
from anytoolai_platform_api.main import create_app
from anytoolai_platform_api.routers.demo import _access_codes_match
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.db import (
    guest_identities_table,
    jobs_table,
    runtime_metadata,
    scenario_sessions_table,
)
from anytoolai_platform_core.storage.transactions import (
    SessionFactory,
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.workflows.models import JobRecord
from anytoolai_platform_core.workflows.repository import JobRepository

from tests.support.sqlite_harness import build_sqlite_runtime_engine

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
ACCESS_CODE = "stakeholder-code"
LIVE_TOKEN = "server-live-token"

ANALYZE_FIELDS = [
    {
        "name": "deadline",
        "type": "string",
        "description": "Project deadline mentioned in the text.",
        "required": True,
    },
    {
        "name": "budget",
        "type": "string",
        "description": "Budget mentioned in the text.",
        "required": False,
    },
    {
        "name": "deliverables",
        "type": "array_of_strings",
        "description": "Deliverables mentioned in the text.",
        "required": False,
    },
]

EXPECTED_DEMOS = {
    "analyze": (
        "kernel_demo.composite_analyze_and_clarify_live_smoke_v1",
        {"source_text": "Проверяем реальную цепочку", "fields": ANALYZE_FIELDS, "strict": False},
    ),
    "evaluate": (
        "kernel_demo.composite_evaluate_match_live_smoke_v1",
        {"source_text": "Проверяем реальную цепочку"},
    ),
    "write": (
        "kernel_demo.composite_shape_and_write_live_smoke_v1",
        {"source_text": "Проверяем реальную цепочку"},
    ),
}


@pytest.fixture
def session_factory(tmp_path: Path) -> Iterator[SessionFactory]:
    engine = build_sqlite_runtime_engine(
        tmp_path / "main.sqlite3",
        tmp_path / "platform.sqlite3",
    )
    runtime_metadata.create_all(engine)
    try:
        yield build_session_factory(engine)
    finally:
        engine.dispose()


@pytest.fixture
def app(session_factory: SessionFactory, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANYTOOLAI_DEMO_ACCESS_CODE", ACCESS_CODE)
    monkeypatch.setenv("ANYTOOLAI_LIVE_CANARY_TOKEN", LIVE_TOKEN)
    application = create_app(config_root=CONFIG_ROOT)
    application.state.runtime = replace(
        application.state.runtime,
        storage=RuntimeStorageDependencies(session_factory=session_factory),
    )
    return application


async def _request(
    app,
    *,
    payload: dict[str, Any] | None = None,
    access_code: str | None = ACCESS_CODE,
    request_id: str = "req_demo_test",
) -> httpx.Response:
    headers = {"X-Request-ID": request_id}
    if access_code is not None:
        headers["X-Demo-Access-Code"] = access_code
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(
            "/v1/demo/runs",
            json=(
                payload
                if payload is not None
                else {"demo_id": "analyze", "source_text": "Тестовый текст"}
            ),
            headers=headers,
        )


def _row_counts(session_factory: SessionFactory) -> tuple[int, int, int]:
    with transaction_boundary(session_factory) as session:
        return tuple(
            session.execute(sa.select(sa.func.count()).select_from(table)).scalar_one()
            for table in (guest_identities_table, scenario_sessions_table, jobs_table)
        )


@pytest.mark.parametrize("access_code", [None, "wrong-code"])
def test_demo_rejects_missing_or_wrong_access_code_without_writes(
    app,
    session_factory: SessionFactory,
    access_code: str | None,
) -> None:
    response = asyncio.run(_request(app, access_code=access_code, request_id="req_denied"))

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {
        "error": {
            "code": "demo_access_denied",
            "message": "Demo access denied.",
            "request_id": "req_denied",
        }
    }
    assert ACCESS_CODE not in response.text
    assert _row_counts(session_factory) == (0, 0, 0)


def test_demo_compares_unicode_access_codes_without_server_error(
    app,
    session_factory: SessionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANYTOOLAI_DEMO_ACCESS_CODE", "код-доступа")

    denied = asyncio.run(_request(app, access_code="wrong-code", request_id="req_unicode"))

    assert denied.status_code == HTTPStatus.UNAUTHORIZED
    assert denied.json()["error"]["code"] == "demo_access_denied"
    assert _access_codes_match("код-доступа", "код-доступа") is True
    assert _access_codes_match("другой-код", "код-доступа") is False
    assert _row_counts(session_factory) == (0, 0, 0)


@pytest.mark.parametrize(
    "missing_env",
    ["ANYTOOLAI_DEMO_ACCESS_CODE", "ANYTOOLAI_LIVE_CANARY_TOKEN"],
)
def test_demo_fails_closed_when_server_secret_is_missing(
    app,
    session_factory: SessionFactory,
    monkeypatch: pytest.MonkeyPatch,
    missing_env: str,
) -> None:
    monkeypatch.delenv(missing_env)

    response = asyncio.run(_request(app, request_id="req_unavailable"))

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json() == {
        "error": {
            "code": "demo_unavailable",
            "message": "Demo is unavailable.",
            "request_id": "req_unavailable",
        }
    }
    assert _row_counts(session_factory) == (0, 0, 0)


@pytest.mark.parametrize(
    "payload",
    [
        {"demo_id": "unknown", "source_text": "Текст"},
        {"demo_id": "analyze", "source_text": "   "},
        {"demo_id": "analyze", "source_text": "я" * 4001},
    ],
)
def test_demo_rejects_invalid_semantic_input_without_writes(
    app,
    session_factory: SessionFactory,
    payload: dict[str, Any],
) -> None:
    response = asyncio.run(_request(app, payload=payload, request_id="req_invalid"))

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json() == {
        "error": {
            "code": "demo_input_invalid",
            "message": "Demo input is invalid.",
            "request_id": "req_invalid",
        }
    }
    assert _row_counts(session_factory) == (0, 0, 0)


def test_demo_request_forbids_unknown_fields(app, session_factory: SessionFactory) -> None:
    response = asyncio.run(
        _request(
            app,
            payload={"demo_id": "analyze", "source_text": "Текст", "scenario_id": "unsafe"},
            request_id="req_extra",
        )
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "request_validation_failed"
    assert _row_counts(session_factory) == (0, 0, 0)


@pytest.mark.parametrize(("demo_id", "expected"), EXPECTED_DEMOS.items())
def test_demo_maps_public_key_to_fixed_live_scenario_and_input(
    app,
    session_factory: SessionFactory,
    demo_id: str,
    expected: tuple[str, dict[str, Any]],
) -> None:
    expected_scenario_id, expected_input = expected

    response = asyncio.run(
        _request(
            app,
            payload={"demo_id": demo_id, "source_text": "  Проверяем реальную цепочку  "},
        )
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body == {
        "scenario_session_id": body["scenario_session_id"],
        "job_id": body["job_id"],
        "status": "started",
        "allowed_next_actions": [],
        "result_artifact_id": None,
    }
    with transaction_boundary(session_factory) as session:
        stored = ScenarioSessionRepository(session).get_in_scope(
            body["scenario_session_id"],
            tenant_id="anytoolai",
            region="default",
        )
        guest_count = session.execute(
            sa.select(sa.func.count()).select_from(guest_identities_table)
        ).scalar_one()

    assert stored is not None
    assert stored.product_id == "kernel_demo"
    assert stored.frontend_id == "web_mirror"
    assert stored.scenario_id == expected_scenario_id
    assert stored.metadata["input"] == expected_input
    assert stored.guest_id is not None
    assert guest_count == 1


def test_demo_rejects_second_start_while_allowlisted_job_is_active(
    app,
    session_factory: SessionFactory,
) -> None:
    first = asyncio.run(_request(app, payload={"demo_id": "write", "source_text": "Первый"}))
    second = asyncio.run(
        _request(
            app,
            payload={"demo_id": "evaluate", "source_text": "Второй"},
            request_id="req_busy",
        )
    )

    assert first.status_code == HTTPStatus.OK
    assert second.status_code == HTTPStatus.CONFLICT
    assert second.json()["error"] == {
        "code": "demo_busy",
        "message": "Another demo run is already active.",
        "request_id": "req_busy",
    }
    assert _row_counts(session_factory) == (1, 1, 1)


def test_demo_process_lock_allows_only_one_of_two_concurrent_starts(
    app,
    session_factory: SessionFactory,
) -> None:
    async def start_both() -> tuple[httpx.Response, httpx.Response]:
        return await asyncio.gather(
            _request(app, payload={"demo_id": "analyze", "source_text": "Первый"}),
            _request(
                app,
                payload={"demo_id": "write", "source_text": "Второй"},
                request_id="req_concurrent",
            ),
        )

    responses = asyncio.run(start_both())

    assert sorted(response.status_code for response in responses) == [
        HTTPStatus.OK,
        HTTPStatus.CONFLICT,
    ]
    assert _row_counts(session_factory) == (1, 1, 1)


def test_demo_rejects_start_after_fifty_accepted_utc_day_sessions(
    app,
    session_factory: SessionFactory,
) -> None:
    with transaction_boundary(session_factory) as session:
        repository = ScenarioSessionRepository(session)
        for index in range(50):
            repository.create(
                ScenarioSessionRecord(
                    id=f"scenario_session_daily_{index}",
                    tenant_id="anytoolai",
                    region="default",
                    product_id="kernel_demo",
                    frontend_id="web_mirror",
                    scenario_id="kernel_demo.composite_evaluate_match_live_smoke_v1",
                    scenario_version=1,
                    created_at=datetime.now(UTC),
                )
            )

    response = asyncio.run(_request(app, request_id="req_limit"))

    assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert response.json()["error"] == {
        "code": "demo_daily_limit_exhausted",
        "message": "Demo daily limit exhausted.",
        "request_id": "req_limit",
    }
    assert _row_counts(session_factory) == (0, 50, 0)


def test_demo_gate_ignores_other_frontends_even_for_allowlisted_scenarios(
    app,
    session_factory: SessionFactory,
) -> None:
    with transaction_boundary(session_factory) as session:
        repository = ScenarioSessionRepository(session)
        for index in range(50):
            stored = repository.create(
                ScenarioSessionRecord(
                    id=f"scenario_session_other_frontend_{index}",
                    tenant_id="anytoolai",
                    region="default",
                    product_id="kernel_demo",
                    frontend_id="kernel_demo_ce",
                    scenario_id="kernel_demo.composite_evaluate_match_live_smoke_v1",
                    scenario_version=1,
                    created_at=datetime.now(UTC),
                )
            )
            if index == 0:
                JobRepository(session).create(
                    JobRecord(
                        tenant_id=stored.tenant_id,
                        region=stored.region,
                        product_id=stored.product_id,
                        frontend_id=stored.frontend_id,
                        scenario_session_id=stored.id,
                        workflow_id="kernel_demo.composite_evaluate_match_live_v1",
                        workflow_version=1,
                    )
                )

    response = asyncio.run(_request(app))

    assert response.status_code == HTTPStatus.OK
    assert _row_counts(session_factory) == (1, 51, 2)


def test_demo_returns_stable_unavailable_error_without_runtime_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANYTOOLAI_DEMO_ACCESS_CODE", ACCESS_CODE)
    monkeypatch.setenv("ANYTOOLAI_LIVE_CANARY_TOKEN", LIVE_TOKEN)
    app = create_app(config_root=CONFIG_ROOT)

    response = asyncio.run(_request(app, request_id="req_no_storage"))

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()["error"] == {
        "code": "demo_unavailable",
        "message": "Demo is unavailable.",
        "request_id": "req_no_storage",
    }


def test_openapi_contains_demo_start_but_not_page_asset_routes(app) -> None:
    paths = app.openapi()["paths"]

    assert "/v1/demo/runs" in paths
    assert "/demo" not in paths
    assert "/demo/demo.css" not in paths
    assert "/demo/demo.js" not in paths
