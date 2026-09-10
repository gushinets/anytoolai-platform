from __future__ import annotations

import asyncio
import uuid as uuid_module
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

# event_id/web_session_id must be canonical-form UUIDs (ANY-17 human review #1, finding 1) -- ce-kit
# always generates one via generateIdempotencyKey(), so these fixed values stand in for that.
DEFAULT_EVENT_ID = "11111111-1111-4111-8111-111111111111"
DEFAULT_WEB_SESSION_ID = "22222222-2222-4222-8222-222222222222"


def _new_uuid() -> str:
    return str(uuid_module.uuid4())


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
                scenario_chain_id="scenario_chain_demo",
            )
        )
        ScenarioSessionRepository(session).create(
            ScenarioSessionRecord(
                id="scenario_session_owned_by_user_demo",
                tenant_id="anytoolai",
                region="default",
                product_id="kernel_demo",
                frontend_id="web_mirror",
                scenario_id="kernel_demo.single_action_smoke_v1",
                scenario_version=1,
                user_id="user_demo",
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
        "event_id": DEFAULT_EVENT_ID,
        "event_type": "web.product_viewed",
        "product_id": "kernel_demo",
        "frontend_id": "web_mirror",
        "web_session_id": DEFAULT_WEB_SESSION_ID,
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
    assert body == {"event_id": DEFAULT_EVENT_ID, "event_type": "web.product_viewed"}

    rows = _stored_events(session_factory, DEFAULT_EVENT_ID)
    assert len(rows) == 1
    assert rows[0]["product_id"] == "kernel_demo"
    assert rows[0]["frontend_id"] == "web_mirror"
    assert rows[0]["tenant_id"] == "anytoolai"
    assert rows[0]["region"] == "default"
    assert rows[0]["properties"]["web_session_id"] == DEFAULT_WEB_SESSION_ID
    assert rows[0]["properties"]["mode"] == "one_run"
    assert rows[0]["properties"]["field_count"] == 3
    assert rows[0]["properties"]["gap_category"] == "budget"


def test_client_event_rejects_a_non_uuid_event_id(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)

    # event_id/web_session_id are opaque client-minted ids, not arbitrary text (ANY-17 human
    # review #1, finding 1) -- ce-kit always generates a UUID for both.
    response = _post_client_event(app, event_id="web_evt_demo_1")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_id_invalid"


def test_client_event_rejects_a_non_canonical_uuid_event_id(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)

    # A valid UUID under a loose parse, but uppercase -- not the canonical lowercase form ce-kit
    # actually produces; two differently-cased strings for "the same" UUID must not be treated as
    # interchangeable for storage/lookup. (DEFAULT_EVENT_ID has no hex letters in it, so its own
    # .upper() would be a no-op -- this uses a UUID with real a-f digits instead.)
    response = _post_client_event(app, event_id="a1b2c3d4-1234-4abc-8def-1234567890ab".upper())

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_id_invalid"


def test_client_event_rejects_an_event_id_in_the_backend_replay_namespace(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    # A client must never be able to impersonate the backend's own reserved id namespace (see
    # events/replay.py's is_replay_owned_event_id()) -- requiring UUID shape rejects this
    # structurally, not via an explicit prefix blocklist.
    response = _post_client_event(app, event_id="event_replay_010_deadbeef")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_id_invalid"


def test_client_event_rejects_a_non_uuid_web_session_id(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(app, web_session_id="web_session_demo")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_web_session_id_invalid"


def test_client_event_accepts_a_uuid_event_id_with_surrounding_whitespace_trimmed(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(app, event_id=f"  {DEFAULT_EVENT_ID}  ")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["event_id"] == DEFAULT_EVENT_ID


def test_client_event_rejects_free_text_gap_category(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)

    # gap_category (and mode) are short categorical labels, not free text -- a length cap alone
    # doesn't stop prompt/result fragments from being smuggled in under an allowlisted key (ANY-17
    # human review #1, finding 3). Free-form prose structurally can't match the categorical shape.
    response = _post_client_event(
        app, properties={"gap_category": "Please rewrite this for a $50k budget by next week"}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_property_invalid"


def test_client_event_rejects_uppercase_mode_value(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(app, properties={"mode": "One_Run"})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_property_invalid"


def test_client_event_accepts_a_property_value_at_the_length_boundary_without_a_false_conflict(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    # Exactly the categorical-value length cap (64) -- accepted, and well below the sanitizer's
    # separate 1024-char truncation threshold, so it round-trips through emit() unchanged. The
    # very first, successful write of this event_id must not be mistaken for a content conflict
    # against itself.
    boundary_mode = "m" * 64
    response = _post_client_event(app, properties={"mode": boundary_mode})

    assert response.status_code == HTTPStatus.OK
    rows = _stored_events(session_factory, DEFAULT_EVENT_ID)
    assert len(rows) == 1
    assert rows[0]["properties"]["mode"] == boundary_mode


def test_client_event_rejects_property_value_over_the_length_cap(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(app, properties={"mode": "m" * 65})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_property_invalid"


def test_client_event_duplicate_delivery_is_idempotent(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)

    first = _post_client_event(app, properties={"mode": "one_run"})
    duplicate = _post_client_event(app, properties={"mode": "one_run"})

    assert first.status_code == HTTPStatus.OK
    assert duplicate.status_code == HTTPStatus.OK
    assert duplicate.json() == first.json()

    rows = _stored_events(session_factory, DEFAULT_EVENT_ID)
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
    rows = _stored_events(session_factory, DEFAULT_EVENT_ID)
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


def test_client_event_rejects_field_count_above_the_bound(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(app, properties={"field_count": 10**9})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_property_invalid"


def test_client_event_rejects_negative_field_count(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(app, properties={"field_count": -1})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_property_invalid"


def test_client_event_rejects_oversized_user_id_instead_of_500ing(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    # event_log.user_id is a bounded String(128) column. Before this was validated, a value this
    # long reached the INSERT unchecked and raised an uncaught sa.exc.DataError (not a
    # sa.exc.IntegrityError, so EventLogRepository.create()'s own except clause didn't catch it) --
    # a raw 500 instead of this endpoint's normal 422 contract. Correlated with a real session so
    # this specifically exercises the length check, not the (separate) standalone-user_id rule.
    response = _post_client_event(
        app,
        event_type="web.result_viewed",
        user_id="u" * 129,
        scenario_session_id="scenario_session_owned_by_user_demo",
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_user_id_invalid"


def test_client_event_rejects_empty_user_id(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(
        app,
        event_type="web.result_viewed",
        user_id="   ",
        scenario_session_id="scenario_session_owned_by_user_demo",
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_user_id_invalid"


def test_client_event_rejects_standalone_user_id_without_a_scenario_session(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    # MVP-A has no authenticated-user lookup, so a bare user_id claim with nothing to verify it
    # against must not be trusted at all (ANY-17 human review #1, finding 2) -- unlike guest_id,
    # which is at least checked for existence against a real minted identity.
    response = _post_client_event(app, user_id="real_user_123")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_user_id_requires_scenario_session"


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

    unknown = _post_client_event(app, event_id=_new_uuid(), guest_id="guest_unknown")
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
        event_id=_new_uuid(),
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


def test_client_event_derives_identity_and_scenario_chain_id_from_the_resolved_session(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    # ANY-17 human review #1, finding 2: once a session resolves, it becomes the source of truth
    # for identity/correlation -- the client doesn't need to (and, per the tests above, need not
    # even be able to) re-assert guest_id, and scenario_chain_id (which a standalone client
    # request has no way to know) is populated from the session instead of dropped.
    response = _post_client_event(
        app,
        event_type="web.result_viewed",
        scenario_session_id="scenario_session_owned_by_guest_demo",
    )

    assert response.status_code == HTTPStatus.OK
    rows = _stored_events(session_factory, DEFAULT_EVENT_ID)
    assert rows[0]["guest_id"] == "guest_demo"
    assert rows[0]["scenario_chain_id"] == "scenario_chain_demo"


def test_client_event_rejects_an_anonymous_session_claimed_by_a_real_guest(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    # Regression: an earlier version of the owner check only fired when the *session* had a
    # guest_id, so an anonymous session (guest_id=None) could be silently claimed by any real
    # guest_id the caller happened to supply.
    response = _post_client_event(
        app,
        event_type="web.result_viewed",
        guest_id="guest_other",
        scenario_session_id="scenario_session_demo",
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "scenario_session_not_found"


def test_client_event_rejects_a_user_owned_session_claimed_by_a_different_user(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    # An explicitly contradictory user_id claim against a user-owned session is still rejected --
    # unlike simply omitting it, which the session's own identity now resolves (see the
    # derives_identity test above).
    response = _post_client_event(
        app,
        event_type="web.result_viewed",
        user_id="someone_else",
        scenario_session_id="scenario_session_owned_by_user_demo",
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "scenario_session_not_found"


def test_client_event_accepts_scenario_session_owned_by_the_matching_user(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(
        app,
        event_type="web.result_viewed",
        user_id="user_demo",
        scenario_session_id="scenario_session_owned_by_user_demo",
    )

    assert response.status_code == HTTPStatus.OK


def test_client_event_accepts_a_guest_owned_session_when_guest_id_is_omitted(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    # The session is authoritative for identity once resolved: a caller correlating to a
    # guest-owned session doesn't need to redundantly resend its guest_id, and the event is
    # correctly attributed to that guest rather than being rejected or recorded unattributed.
    response = _post_client_event(
        app,
        event_type="web.result_viewed",
        scenario_session_id="scenario_session_owned_by_guest_demo",
    )

    assert response.status_code == HTTPStatus.OK
    rows = _stored_events(session_factory, DEFAULT_EVENT_ID)
    assert rows[0]["guest_id"] == "guest_demo"


def test_client_event_trims_guest_id_before_lookup(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(app, guest_id="  guest_demo  ")

    assert response.status_code == HTTPStatus.OK


def test_client_event_trims_scenario_session_id_before_lookup(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(
        app,
        event_type="web.result_viewed",
        scenario_session_id="  scenario_session_demo  ",
    )

    assert response.status_code == HTTPStatus.OK


def test_client_event_rejects_empty_guest_id_as_invalid_not_not_found(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(app, guest_id="   ")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_guest_id_invalid"


def test_client_event_rejects_empty_scenario_session_id_as_invalid_not_not_found(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(app, scenario_session_id="")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "client_event_scenario_session_id_invalid"


def test_client_event_trims_web_session_id_before_storing(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)

    response = _post_client_event(app, web_session_id=f"  {DEFAULT_WEB_SESSION_ID}  ")

    assert response.status_code == HTTPStatus.OK
    rows = _stored_events(session_factory, DEFAULT_EVENT_ID)
    assert rows[0]["properties"]["web_session_id"] == DEFAULT_WEB_SESSION_ID


def test_client_event_truncates_a_huge_property_key_in_the_error_message(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)

    huge_key = "x" * 5000
    response = _post_client_event(app, properties={huge_key: "value"})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    message = response.json()["error"]["message"]
    # The full 5000-char key must never be reflected back into the response.
    assert huge_key not in message
    assert len(message) < 500
