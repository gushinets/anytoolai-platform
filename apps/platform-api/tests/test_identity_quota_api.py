from __future__ import annotations

import asyncio
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from anytoolai_platform_api.bootstrap import RuntimeStorageDependencies
from anytoolai_platform_api.main import create_app
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.storage.db import event_log_table
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)
from sqlalchemy import event

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"


def _sqlite_url(database_path: Path) -> str:
    return f"sqlite+pysqlite:///{database_path.resolve().as_posix()}"


def _build_session_factory(tmp_path: Path) -> sa.orm.sessionmaker[sa.orm.Session]:
    main_db = tmp_path / "identity-quota-main.sqlite3"
    platform_db = tmp_path / "identity-quota-platform.sqlite3"
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

    return build_session_factory(engine)


def _create_test_app(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
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


def test_create_guest_identity_emits_event(tmp_path: Path) -> None:
    session_factory = _build_session_factory(tmp_path)
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


def test_quota_check_endpoint_returns_current_state(tmp_path: Path) -> None:
    session_factory = _build_session_factory(tmp_path)
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

    assert "quota.checked" in event_types
    assert "quota.consumed" not in event_types


def test_quota_check_endpoint_returns_safe_404_for_unknown_guest(tmp_path: Path) -> None:
    session_factory = _build_session_factory(tmp_path)
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
