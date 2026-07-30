from __future__ import annotations

import asyncio
from http import HTTPStatus
from pathlib import Path
from typing import Any, Iterator

import httpx
import pytest
import sqlalchemy as sa
from anytoolai_platform_api.bootstrap import RuntimeStorageDependencies
from anytoolai_platform_api.main import create_app
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.storage.db import event_log_table, guest_quota_usage_table
from anytoolai_platform_core.storage.transactions import (
    SessionFactory,
    build_session_factory,
    transaction_boundary,
)
from tests.db_support import provision_database

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
pytestmark = [pytest.mark.postgresql, pytest.mark.slow]


@pytest.fixture
def session_factory() -> Iterator[SessionFactory]:
    with provision_database(
        database_name_prefix="anytoolai_identity_quota_api_test",
        skip_reason="PostgreSQL identity and quota API coverage",
    ) as (engine, _alembic_config, _database_url):
        yield build_session_factory(engine)


def _create_test_app(
    session_factory: SessionFactory,
):
    app = create_app(config_root=CONFIG_ROOT)
    app.state.runtime = app.state.runtime.__class__(
        loaded_bundles=app.state.runtime.loaded_bundles,
        config_registry=app.state.runtime.config_registry,
        storage=RuntimeStorageDependencies(session_factory=session_factory),
    )
    return app


async def _request(
    app,
    method: str,
    path: str,
    *,
    json: Any | None = None,
    request_id: str = "req_identity_quota_test",
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(
            method,
            path,
            json=json,
            headers={"X-Request-ID": request_id},
        )


def test_create_guest_identity_emits_event(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    response = asyncio.run(_request(app, "POST", "/v1/identity/guest"))

    assert response.status_code == HTTPStatus.OK
    guest_id = response.json()["guest_id"]
    assert guest_id.startswith("guest_")

    with transaction_boundary(session_factory) as session:
        event = (
            session.execute(
                sa.select(event_log_table).where(
                    event_log_table.c.event_type == "guest.created"
                )
            )
            .mappings()
            .one()
        )
        stored = EventLogRepository(session).get(event["event_id"])

    assert event["guest_id"] == guest_id
    assert stored is not None
    assert stored.guest_id == guest_id


def test_quota_check_endpoint_returns_current_state(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    guest_response = asyncio.run(_request(app, "POST", "/v1/identity/guest"))
    guest_id = guest_response.json()["guest_id"]
    response = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/products/kernel_demo/quota?guest_id={guest_id}",
            request_id="req_quota_check",
        )
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "guest_id": guest_id,
        "product_id": "kernel_demo",
        "quota_policy_id": "kernel_demo.guest_quota_v1",
        "quota_dimension": "product",
        "dimension_key": "kernel_demo",
        "scenario_id": None,
        "unit": "scenario_run",
        "period": "lifetime",
        "limit_count": 3,
        "used_count": 0,
        "remaining_count": 3,
        "exhausted": False,
    }

    with transaction_boundary(session_factory) as session:
        event_types = list(
            session.execute(
                sa.select(event_log_table.c.event_type).order_by(
                    event_log_table.c.timestamp,
                    event_log_table.c.event_id,
                )
            ).scalars()
        )
        usage_count = session.execute(
            sa.select(sa.func.count()).select_from(guest_quota_usage_table)
        ).scalar_one()

    assert event_types == ["guest.created"]
    assert usage_count == 0
    assert "quota.consumed" not in event_types


def test_quota_check_endpoint_returns_safe_404_for_unknown_guest(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    response = asyncio.run(
        _request(
            app,
            "GET",
            "/v1/products/kernel_demo/quota?guest_id=guest_missing",
            request_id="req_missing_guest",
        )
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {
        "error": {
            "code": "guest_identity_not_found",
            "message": "Guest identity not found.",
            "request_id": "req_missing_guest",
        }
    }


def test_openapi_contains_identity_and_quota_endpoints() -> None:
    app = create_app(config_root=CONFIG_ROOT)
    openapi = app.openapi()

    assert "/v1/identity/guest" in openapi["paths"]
    assert "/v1/products/{product_id}/quota" in openapi["paths"]
