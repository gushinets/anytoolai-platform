from __future__ import annotations

import asyncio
from dataclasses import replace
from http import HTTPStatus
from pathlib import Path
from typing import Any, Iterator

import httpx
import pytest
import sqlalchemy as sa
from anytoolai_platform_api.bootstrap import RuntimeStorageDependencies
from anytoolai_platform_api.main import create_app
from anytoolai_platform_core.identity.models import GuestIdentityRecord
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.db import event_log_table
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
        database_name_prefix="anytoolai_client_events_api_test",
        skip_reason="PostgreSQL client-events API coverage",
    ) as (engine, _alembic_config, _database_url):
        yield build_session_factory(engine)


def _create_test_app(session_factory: SessionFactory):
    with transaction_boundary(session_factory) as session:
        guest_repository = GuestIdentityRepository(session)
        guest_repository.create(
            GuestIdentityRecord(id="guest_demo", tenant_id="anytoolai", region="default")
        )
        guest_repository.create(
            GuestIdentityRecord(id="guest_other", tenant_id="anytoolai", region="default")
        )
        ScenarioSessionRepository(session).create(
            ScenarioSessionRecord(
                id="scenario_session_demo",
                tenant_id="anytoolai",
                region="default",
                product_id="kernel_demo",
                frontend_id="web_mirror",
                scenario_id="kernel_demo.single_action_smoke_v1",
                scenario_version=1,
            )
        )
        ScenarioSessionRepository(session).create(
            ScenarioSessionRecord(
                id="scenario_session_owned_by_guest_demo",
                tenant_id="anytoolai",
                region="default",
                product_id="kernel_demo",
                frontend_id="web_mirror",
                scenario_id="kernel_demo.single_action_smoke_v1",
                scenario_version=1,
                guest_id="guest_demo",
            )
        )
    app = create_app(config_root=CONFIG_ROOT)
    app.state.runtime = replace(
        app.state.runtime,
        storage=RuntimeStorageDependencies(session_factory=session_factory),
    )
    return app


async def _request(
    app,
    method: str,
    path: str,
    *,
    json: Any | None = None,
    request_id: str = "req_client_events_test",
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(
            method,
            path,
            json=json,
            headers={"X-Request-ID": request_id},
        )


def _payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "event_id": "web_evt_demo_1",
        "event_type": "web.product_viewed",
        "product_id": "kernel_demo",
        "frontend_id": "web_mirror",
        "web_session_id": "web_session_demo",
    }
    payload.update(overrides)
    return payload


def _post_client_event(app, **overrides: Any) -> httpx.Response:
    return asyncio.run(_request(app, "POST", "/v1/client-events", json=_payload(**overrides)))


def _stored_events(session_factory: SessionFactory, event_id: str) -> list[dict[str, Any]]:
    with transaction_boundary(session_factory) as session:
        rows = session.execute(
            sa.select(event_log_table).where(event_log_table.c.event_id == event_id)
        ).mappings()
        return [dict(row) for row in rows]


def test_client_event_is_recorded(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(
        app,
        properties={"mode": "one_run", "field_count": 3, "gap_category": "budget"},
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body == {"event_id": "web_evt_demo_1", "event_type": "web.product_viewed"}

    rows = _stored_events(session_factory, "web_evt_demo_1")
    assert len(rows) == 1
    assert rows[0]["product_id"] == "kernel_demo"
    assert rows[0]["frontend_id"] == "web_mirror"
    assert rows[0]["tenant_id"] == "anytoolai"
    assert rows[0]["region"] == "default"
    assert rows[0]["properties"]["web_session_id"] == "web_session_demo"
    assert rows[0]["properties"]["mode"] == "one_run"
    assert rows[0]["properties"]["field_count"] == 3
    assert rows[0]["properties"]["gap_category"] == "budget"


def test_client_event_accepts_a_long_property_value_without_a_false_conflict(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    # Longer than the sanitizer's 1024-char truncation threshold. The very first, successful
    # write of this event_id must not be mistaken for a content conflict against itself just
    # because emit() truncates the stored copy.
    long_mode = "m" * 1100
    response = _post_client_event(app, properties={"mode": long_mode})

    assert response.status_code == HTTPStatus.OK
    rows = _stored_events(session_factory, "web_evt_demo_1")
    assert len(rows) == 1
    assert rows[0]["properties"]["mode"] != long_mode
    assert rows[0]["properties"]["mode"].startswith("m" * 100)


def test_client_event_duplicate_delivery_is_idempotent(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)

    first = _post_client_event(app, properties={"mode": "one_run"})
    duplicate = _post_client_event(app, properties={"mode": "one_run"})

    assert first.status_code == HTTPStatus.OK
    assert duplicate.status_code == HTTPStatus.OK
    assert duplicate.json() == first.json()

    rows = _stored_events(session_factory, "web_evt_demo_1")
    assert len(rows) == 1
    assert rows[0]["properties"]["mode"] == "one_run"


def test_client_event_rejects_colliding_event_id_used_for_different_content(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    first = _post_client_event(app, properties={"mode": "one_run"})
    conflicting = _post_client_event(app, properties={"mode": "different_on_retry"})

    assert first.status_code == HTTPStatus.OK
    assert conflicting.status_code == HTTPStatus.CONFLICT
    assert conflicting.json()["error"]["code"] == "client_event_id_conflict"

    # The original event is untouched by the rejected conflicting attempt.
    rows = _stored_events(session_factory, "web_evt_demo_1")
    assert len(rows) == 1
    assert rows[0]["properties"]["mode"] == "one_run"


def test_client_event_rejects_unknown_event_type(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(app, event_type="web.does_not_exist")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "request_validation_failed"


def test_client_event_rejects_platform_event_outside_web_allowlist(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    # A real platform event type, just not one of the 8 in the v1 web-event allowlist -- the
    # generated ClientEventRequest.event_type enum rejects it before it ever reaches
    # ClientEventService, the same way it rejects a made-up string.
    response = _post_client_event(app, event_type="client.result_copied")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "request_validation_failed"


def test_client_event_rejects_unknown_product(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(app, product_id="does_not_exist")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_product_invalid"


def test_client_event_rejects_frontend_not_enabled_for_product(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(app, frontend_id="does_not_exist")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_frontend_invalid"


def test_client_event_rejects_missing_web_session_id(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(app, web_session_id="")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_web_session_id_invalid"


def test_client_event_rejects_property_key_not_on_allowlist(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(app, properties={"prompt_text": "sensitive source text"})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_property_invalid"


def test_client_event_rejects_non_scalar_property_value(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(app, properties={"mode": {"nested": True}})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_property_invalid"


def test_client_event_rejects_property_value_of_the_wrong_expected_type(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    # field_count is defined as an int; a string that merely looks numeric must still be rejected,
    # not silently accepted as-is under a loose "any scalar" check.
    response = _post_client_event(app, properties={"field_count": "three"})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_property_invalid"


def test_client_event_rejects_bool_for_an_int_property(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)

    # bool is a subclass of int in Python; field_count=True must not silently pass as 1.
    response = _post_client_event(app, properties={"field_count": True})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_property_invalid"


def test_client_event_rejects_server_owned_dimensions_in_payload(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(app, tenant_id="attacker_tenant")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "request_validation_failed"


def test_client_event_accepts_known_guest_and_rejects_unknown_guest(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    known = _post_client_event(app, guest_id="guest_demo")
    assert known.status_code == HTTPStatus.OK

    unknown = _post_client_event(
        app, event_id="web_evt_demo_2", guest_id="guest_unknown"
    )
    assert unknown.status_code == HTTPStatus.NOT_FOUND
    assert unknown.json()["error"]["code"] == "guest_identity_not_found"


def test_client_event_accepts_known_scenario_session_and_rejects_unknown(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    known = _post_client_event(
        app,
        event_type="web.result_viewed",
        scenario_session_id="scenario_session_demo",
    )
    assert known.status_code == HTTPStatus.OK

    unknown = _post_client_event(
        app,
        event_id="web_evt_demo_2",
        event_type="web.result_viewed",
        scenario_session_id="scenario_session_unknown",
    )
    assert unknown.status_code == HTTPStatus.NOT_FOUND
    assert unknown.json()["error"]["code"] == "scenario_session_not_found"


def test_client_event_rejects_scenario_session_owned_by_a_different_guest(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    # scenario_session_owned_by_guest_demo really exists and really belongs to a real guest
    # (guest_demo) -- but not to guest_other, the guest_id on this request. Both identifiers are
    # individually valid; the combination must still be rejected as if the session did not exist,
    # rather than silently correlating the event to someone else's session.
    response = _post_client_event(
        app,
        event_type="web.result_viewed",
        guest_id="guest_other",
        scenario_session_id="scenario_session_owned_by_guest_demo",
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "scenario_session_not_found"


def test_client_event_accepts_scenario_session_owned_by_the_matching_guest(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(
        app,
        event_type="web.result_viewed",
        guest_id="guest_demo",
        scenario_session_id="scenario_session_owned_by_guest_demo",
    )

    assert response.status_code == HTTPStatus.OK


def test_client_event_rejects_a_guest_owned_session_when_guest_id_is_omitted(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    # Regression: an earlier version of the owner check only compared guest_id against the
    # session's owner *when guest_id was supplied* -- omitting guest_id entirely bypassed the
    # check completely, letting anyone correlate an event to any known guest-owned session.
    response = _post_client_event(
        app,
        event_type="web.result_viewed",
        scenario_session_id="scenario_session_owned_by_guest_demo",
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "scenario_session_not_found"
