"""Paid events are observational and use reservation/deferred ownership, never body identity."""

import io
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from unittest.mock import Mock
from urllib.error import HTTPError, URLError
from uuid import uuid4

import pytest
import sqlalchemy as sa
from anytoolai_platform_api import paid_access
from anytoolai_platform_api.bootstrap import RuntimeStorageDependencies
from anytoolai_platform_api.errors import ApiError
from anytoolai_platform_api.main import create_app
from anytoolai_platform_api.paid_access import (
    AccessSnapshot,
    AccessSnapshotClient,
    optional_portal_user,
)
from anytoolai_platform_api.portal_session import PortalUserPrincipal, get_portal_session_client
from anytoolai_platform_api.routers.access_invalidations import AccessInvalidation
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.quotas.models import ExecutionOwner, ExecutionOwnerKind
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.db import (
    event_log_table,
    execution_reservations_table,
    jobs_table,
)
from anytoolai_platform_core.storage.transactions import transaction_boundary
from fastapi.testclient import TestClient
from pydantic import ValidationError

OWNER = ExecutionOwner(
    "anytoolai", "ru", ExecutionOwnerKind.portal_user, "00000000-0000-4000-8000-000000000001"
)


@pytest.fixture
def paid_app(session_factory):
    app = create_app(config_root=Path(__file__).resolve().parents[3] / "configs/kernel")
    app.state.runtime = replace(
        app.state.runtime, storage=RuntimeStorageDependencies(session_factory=session_factory)
    )
    app.dependency_overrides[optional_portal_user] = lambda: PortalUserPrincipal(
        OWNER, datetime.now(UTC) + timedelta(minutes=20)
    )
    with transaction_boundary(session_factory) as session:
        ScenarioSessionRepository(session).create(
            ScenarioSessionRecord(
                id="paid-session",
                tenant_id="anytoolai",
                region="ru",
                product_id="kernel_demo",
                frontend_id="web_mirror",
                scenario_id="kernel_demo.single_action_smoke_v1",
                scenario_version=1,
                user_id=OWNER.owner_id,
                metadata={"execution_owner": asdict(OWNER)},
            )
        )
        ScenarioSessionRepository(session).create(
            ScenarioSessionRecord(
                id="body-only",
                tenant_id="anytoolai",
                region="ru",
                product_id="kernel_demo",
                frontend_id="web_mirror",
                scenario_id="kernel_demo.single_action_smoke_v1",
                scenario_version=1,
                user_id=OWNER.owner_id,
            )
        )
    return app


def event(**changes):
    return {
        "event_id": str(uuid4()),
        "event_type": "web.product_viewed",
        "product_id": "kernel_demo",
        "frontend_id": "web_mirror",
        "web_session_id": str(uuid4()),
        **changes,
    }


def test_paid_events_without_guest_before_and_after_scenario_preserve_dedup(
    paid_app, session_factory
):
    client = TestClient(paid_app)
    before = event()
    after = event(scenario_session_id="paid-session")
    for payload in (before, after):
        response = client.post("/v1/client-events", json=payload)
        assert response.status_code == HTTPStatus.OK, response.text
        assert client.post("/v1/client-events", json=payload).json() == response.json()
        assert (
            client.post(
                "/v1/client-events", json={**payload, "event_type": "web.form_started"}
            ).status_code
            == HTTPStatus.CONFLICT
        )
    with transaction_boundary(session_factory) as session:
        events = list(session.execute(sa.select(event_log_table)).mappings())
        assert len(events) == len((before, after))
        assert all(e["user_id"] == OWNER.owner_id and e["guest_id"] is None for e in events)
        for table in (jobs_table, execution_reservations_table):
            assert session.execute(sa.select(sa.func.count()).select_from(table)).scalar_one() == 0


@pytest.mark.parametrize(
    "changes,status",
    [
        ({"user_id": str(uuid4())}, HTTPStatus.UNPROCESSABLE_ENTITY),
        ({"scenario_session_id": "body-only"}, HTTPStatus.NOT_FOUND),
        ({"scenario_session_id": "unknown"}, HTTPStatus.NOT_FOUND),
    ],
)
def test_paid_event_cannot_adopt_body_or_historical_owner(paid_app, changes, status):
    assert (
        TestClient(paid_app).post("/v1/client-events", json=event(**changes)).status_code == status
    )


def test_guest_and_foreign_owner_cannot_poll_or_record_paid_session(paid_app):
    for principal in (
        None,
        PortalUserPrincipal(
            replace(OWNER, owner_id=str(uuid4())), datetime.now(UTC) + timedelta(minutes=20)
        ),
    ):
        paid_app.dependency_overrides[optional_portal_user] = constant_identity(principal)
        client = TestClient(paid_app)
        assert client.get("/v1/scenario-sessions/paid-session").status_code == HTTPStatus.NOT_FOUND
        assert (
            client.post(
                "/v1/client-events", json=event(scenario_session_id="paid-session")
            ).status_code
            == HTTPStatus.NOT_FOUND
        )


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": True},
        {"schema_version": 1},
        {"schema_version": 2.0},
        {"access_revision": True},
        {"refresh_after": "2026-11-10T00:00:00+01:00"},
        {"extra": "untrusted"},
        {"user_id": "noncanonical"},
        {"access_revision": 0},
    ],
)
def test_snapshot_parser_rejects_invalid_boundary(change):
    payload = snapshot_payload()
    with pytest.raises(ValidationError):
        AccessSnapshot.model_validate({**payload, **change})


def snapshot_payload():
    now = datetime.now(UTC)
    return {
        "schema_version": 2,
        "tenant_id": "anytoolai",
        "region": "ru",
        "user_id": OWNER.owner_id,
        "access_revision": 1,
        "refresh_after": now.isoformat(),
        "expires_at": (now + timedelta(seconds=60)).isoformat(),
        "grants": [{"product_id": "kernel_demo", "valid_until": None}],
        "allowances": [],
    }


def constant_identity(value):
    return lambda: value


def test_runtime_snapshot_and_invalidation_models_validate_reviewed_fixtures():

    root = Path(__file__).resolve().parents[3] / "docs/contracts/portal-kernel-paid/fixtures"
    models = {"snapshot-v2": AccessSnapshot, "invalidation-v1": AccessInvalidation}
    for vector in json.loads((root / "valid.json").read_text()):
        if vector["contract"] in models:
            models[vector["contract"]].model_validate(vector["payload"])
    for vector in json.loads((root / "invalid.json").read_text()):
        if vector["contract"] in models:
            with pytest.raises(ValidationError):
                models[vector["contract"]].model_validate(vector["payload"])


def test_snapshot_http_boundary_is_bounded_scoped_and_never_follows_redirects(monkeypatch):

    client = AccessSnapshotClient(
        Settings(
            portal_base_url="https://portal.invalid",
            portal_access_service_token="synthetic-reverse-" + "s" * 40,
        )
    )

    class Response(io.BytesIO):
        status = HTTPStatus.OK

    opener = Mock()
    monkeypatch.setattr(paid_access, "build_opener", Mock(return_value=opener))
    for body in (
        b"invalid",
        b"x" * (paid_access.SNAPSHOT_MAX_BYTES + 1),
        json.dumps({**snapshot_payload(), "user_id": str(uuid4())}).encode(),
    ):
        opener.open.return_value = Response(body)
        with pytest.raises(ApiError):
            client.fetch(OWNER)
    error_body = io.BytesIO(b"synthetic-service-refusal")
    opener.open.side_effect = HTTPError(
        "https://portal.invalid", HTTPStatus.FORBIDDEN, "synthetic-refusal", {}, error_body
    )
    with pytest.raises(ApiError):
        client.fetch(OWNER)
    assert error_body.closed
    opener.open.side_effect = URLError("synthetic-outage")
    with pytest.raises(ApiError):
        client.fetch(OWNER)
    opener.open.side_effect = None
    opener.open.return_value = Response(json.dumps(snapshot_payload()).encode())
    document = client.fetch(OWNER)
    assert document.user_id == OWNER.owner_id
    request = opener.open.call_args.args[0]
    assert request.full_url.endswith(f"/{OWNER.owner_id}?tenant_id=anytoolai&region=ru")
    assert request.get_method() == "GET"
    assert opener.open.call_args.kwargs["timeout"] == paid_access.PORTAL_TIMEOUT_SECONDS


def test_attached_identity_dependency_refuses_invalid_bearer_without_guest_fallback(paid_app):
    client = Mock()
    client.introspect.side_effect = ApiError(
        status_code=HTTPStatus.UNAUTHORIZED,
        code="kernel_parent_authority_invalid",
        message="Portal identity is no longer valid.",
    )
    paid_app.dependency_overrides.pop(optional_portal_user)
    paid_app.dependency_overrides[get_portal_session_client] = lambda: client
    http = TestClient(paid_app)
    payload = event(guest_id="guest-body-cannot-authorize")
    response = http.post(
        "/v1/client-events", json=payload, headers={"Authorization": "Bearer " + "u" * 50}
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["error"]["code"] == "kernel_parent_authority_invalid"
    client.introspect.assert_called_once()
    client.introspect.reset_mock()
    response = http.post(
        "/v1/client-events", json=payload, headers=[("Authorization", "Bearer " + "u" * 50)] * 2
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    client.introspect.assert_not_called()
