"""Offline Portal identity boundary evidence, with intercepted HTTP only."""

import io
import json
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Annotated, Any
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest
from anytoolai_platform_api import portal_session
from anytoolai_platform_api.main import create_app
from anytoolai_platform_api.portal_session import PortalUserPrincipal, authenticate_portal_user
from anytoolai_platform_api.schemas import ErrorResponse
from anytoolai_platform_api.settings import Settings
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import ValidationError

SERVICE_TOKEN = "synthetic-reverse-service-" + "s" * 32
USER_TOKEN = "synthetic-delegated-user-" + "u" * 32
CODE = "c" * 43
VERIFIER = "v" * 43
USER_ID = "00000000-0000-4000-8000-000000000001"
READ_COUNT = 2
EXCHANGE_PATH = "/v1/portal-session/exchange"


class PortalResponse(io.BytesIO):
    status = HTTPStatus.OK


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    for name in (
        "ANYTOOLAI_PORTAL_SERVICE_TOKEN",
        "ANYTOOLAI_PORTAL_SERVICE_TOKEN_PREVIOUS",
        "ANYTOOLAI_ENABLED_PRODUCT_IDS",
        "ANYTOOLAI_DEPLOYMENT_ACTIVATION_NAME",
        "ANYTOOLAI_DEPLOYMENT_ACTIVATION_MARKER",
        "ANYTOOLAI_TENANT_ID",
        "ANYTOOLAI_REGION",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ANYTOOLAI_PORTAL_BASE_URL", "https://portal.invalid")
    monkeypatch.setenv("ANYTOOLAI_PORTAL_ACCESS_SERVICE_TOKEN", SERVICE_TOKEN)
    application = create_app(database_url="")

    @application.get("/test/principal")
    def principal(
        identity: Annotated[PortalUserPrincipal, Depends(authenticate_portal_user)],
    ) -> dict[str, str]:
        return {"user_id": identity.owner.owner_id, "kind": identity.owner.owner_kind}

    return TestClient(application, raise_server_exceptions=False)


def exchange_payload() -> dict[str, object]:
    return {
        "schema_version": 2,
        "consumer_id": "platform-kernel",
        "consumer_policy_revision": 1,
        "token_type": "Bearer",
        "access_token": USER_TOKEN,
        "tenant_id": "anytoolai",
        "region": "ru",
        "user_id": USER_ID,
        "expires_at": (datetime.now(UTC) + timedelta(minutes=20)).isoformat(),
    }


def introspection_payload() -> dict[str, object]:
    return {
        "schema_version": 2,
        "consumer_id": "platform-kernel",
        "consumer_policy_revision": 1,
        "tenant_id": "anytoolai",
        "region": "ru",
        "user_id": USER_ID,
        "valid_until": (datetime.now(UTC) + timedelta(minutes=19)).isoformat(),
    }


def intercept(monkeypatch: pytest.MonkeyPatch, payload: object) -> Mock:
    opener = Mock()
    opener.open.side_effect = lambda *args, **kwargs: PortalResponse(json.dumps(payload).encode())
    monkeypatch.setattr(portal_session, "build_opener", Mock(return_value=opener))
    return opener


def test_exchange_uses_directional_secret_and_only_forwards_code(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = exchange_payload()
    opener = intercept(monkeypatch, payload)
    response = client.post(
        EXCHANGE_PATH,
        json={"code": CODE, "code_verifier": VERIFIER},
        headers={"Authorization": "Bearer original-portal-bearer-must-not-forward"},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        **payload,
        "expires_at": payload["expires_at"].replace("+00:00", "Z"),
    }
    assert response.headers["cache-control"] == "no-store"
    request = opener.open.call_args.args[0]
    assert request.full_url == "https://portal.invalid/internal/v1/backend-sessions/exchange"
    assert request.get_header("Authorization") == "Bearer " + SERVICE_TOKEN
    assert json.loads(request.data) == {"code": CODE, "code_verifier": VERIFIER}
    assert opener.open.call_args.kwargs["timeout"] == portal_session.PORTAL_TIMEOUT_SECONDS


def test_canonical_principal_introspects_on_every_request_and_never_becomes_guest(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    opener = intercept(monkeypatch, introspection_payload())
    for _ in range(READ_COUNT):
        response = client.get("/test/principal", headers={"Authorization": "Bearer " + USER_TOKEN})
        assert response.status_code == HTTPStatus.OK
        assert response.json() == {"user_id": USER_ID, "kind": "portal_user"}
    assert opener.open.call_count == READ_COUNT
    request = opener.open.call_args.args[0]
    assert request.full_url.endswith("/introspect")
    assert request.get_header("Authorization") == "Bearer " + SERVICE_TOKEN
    assert json.loads(request.data) == {"access_token": USER_TOKEN}
    for headers in (
        {},
        {"Authorization": "Bearer short"},
        [("Authorization", "Bearer " + USER_TOKEN)] * 2,
    ):
        assert client.get("/test/principal", headers=headers).status_code == HTTPStatus.UNAUTHORIZED
    assert opener.open.call_count == READ_COUNT


@pytest.mark.parametrize("operation", ["exchange", "introspect"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", True),
        ("schema_version", 2.0),
        ("schema_version", 1),
        ("consumer_id", "synthetic-summary"),
        ("consumer_policy_revision", True),
        ("consumer_policy_revision", 0),
        ("consumer_policy_revision", 1.5),
        ("tenant_id", "foreign"),
        ("region", "eu"),
        ("user_id", "not-a-uuid"),
        ("extra", "must-be-refused"),
    ],
)
def test_untrusted_response_fails_closed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, operation: str, field: str, value: object
) -> None:
    payload = exchange_payload() if operation == "exchange" else introspection_payload()
    payload[field] = value
    intercept(monkeypatch, payload)
    response = (
        client.post(EXCHANGE_PATH, json={"code": CODE, "code_verifier": VERIFIER})
        if operation == "exchange"
        else client.get("/test/principal", headers={"Authorization": "Bearer " + USER_TOKEN})
    )
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()["error"]["code"] == "portal_identity_unavailable"


@pytest.mark.parametrize("operation", ["exchange", "introspect"])
@pytest.mark.parametrize("deadline", ["expired", "future", "epoch", "nonutc"])
def test_invalid_deadlines_cannot_grant_authority(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, operation: str, deadline: str
) -> None:
    payload = exchange_payload() if operation == "exchange" else introspection_payload()
    value = {
        "expired": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        "future": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "epoch": "4102444800",
        "nonutc": "2026-11-10T12:00:00+08:00",
    }[deadline]
    payload["expires_at" if operation == "exchange" else "valid_until"] = value
    intercept(monkeypatch, payload)
    response = (
        client.post(EXCHANGE_PATH, json={"code": CODE, "code_verifier": VERIFIER})
        if operation == "exchange"
        else client.get("/test/principal", headers={"Authorization": "Bearer " + USER_TOKEN})
    )
    assert response.status_code == (
        HTTPStatus.UNAUTHORIZED if deadline == "expired" else HTTPStatus.SERVICE_UNAVAILABLE
    )
    if operation == "exchange":
        responses = client.app.openapi()["paths"][EXCHANGE_PATH]["post"]["responses"]
        assert responses[str(response.status_code)]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorResponse"
        }
        ErrorResponse.model_validate(response.json())


@pytest.mark.parametrize(
    "code",
    [
        "backend_delegation_expired",
        "backend_parent_authority_invalid",
        "backend_session_code_invalid",
    ],
)
def test_safe_identity_refusals_remain_distinct(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, code: str
) -> None:
    opener = intercept(monkeypatch, None)
    opener.open.side_effect = lambda *args, **kwargs: _raise_http(401, {"detail": {"code": code}})
    response = client.post(EXCHANGE_PATH, json={"code": CODE, "code_verifier": VERIFIER})
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["error"]["code"] == code
    assert response.headers["cache-control"] == "no-store"


def _raise_http(status: int, body: object) -> None:
    raise HTTPError(
        "https://portal.invalid",
        status,
        "safe synthetic error",
        {},
        io.BytesIO(json.dumps(body).encode()),
    )


@pytest.mark.parametrize(
    "failure",
    [
        "timeout",
        "transport",
        "badjson",
        "oversize",
        "redirect",
        "service401",
        "forbidden",
        "unavailable",
    ],
)
def test_dependency_outages_and_invalid_service_auth_never_grant_identity(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    opener = intercept(monkeypatch, None)
    if failure == "timeout":
        opener.open.side_effect = TimeoutError(USER_TOKEN)
    elif failure == "transport":
        opener.open.side_effect = URLError(USER_TOKEN)
    elif failure in {"badjson", "oversize"}:
        opener.open.side_effect = lambda *args, **kwargs: PortalResponse(
            b"[" if failure == "badjson" else b"x" * (portal_session.PORTAL_MAX_RESPONSE_BYTES + 1)
        )
    else:
        status = {"redirect": 302, "service401": 401, "forbidden": 403, "unavailable": 503}[failure]
        opener.open.side_effect = lambda *args, **kwargs: _raise_http(
            status, {"detail": {"code": "service_unauthorized", "secret": USER_TOKEN}}
        )
    response = client.get("/test/principal", headers={"Authorization": "Bearer " + USER_TOKEN})
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert USER_TOKEN not in response.text
    assert opener.open.call_count == 1


def test_secret_canaries_do_not_enter_responses_logs_or_reprs(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    intercept(monkeypatch, exchange_payload())
    for payload in (
        {"code": CODE, "code_verifier": VERIFIER + "!"},
        {"code": CODE, "code_verifier": VERIFIER, "secret": USER_TOKEN},
    ):
        response = client.post(EXCHANGE_PATH, json=payload)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        responses = client.app.openapi()["paths"][EXCHANGE_PATH]["post"]["responses"]
        assert responses[str(response.status_code)]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorResponse"
        }
        ErrorResponse.model_validate(response.json())
        assert all(secret not in response.text for secret in (CODE, VERIFIER, USER_TOKEN))
        assert response.headers["cache-control"] == "no-store"
    assert all(secret not in caplog.text for secret in (SERVICE_TOKEN, CODE, VERIFIER, USER_TOKEN))
    assert SERVICE_TOKEN not in repr(client.app.state.settings)
    assert USER_TOKEN not in repr(
        portal_session.PortalExchangeResponse.model_validate(exchange_payload())
    )


@pytest.mark.parametrize(
    "values",
    [
        {"portal_base_url": "https://portal.invalid"},
        {"portal_access_service_token": SERVICE_TOKEN},
        {"portal_base_url": "http://portal.invalid", "portal_access_service_token": SERVICE_TOKEN},
        {
            "portal_base_url": "https://user:secret@portal.invalid",
            "portal_access_service_token": SERVICE_TOKEN,
        },
        {
            "portal_base_url": "https://portal.invalid/path",
            "portal_access_service_token": SERVICE_TOKEN,
        },
        {"portal_base_url": "https://portal.invalid", "portal_access_service_token": "short"},
        {
            "portal_base_url": "https://portal.invalid",
            "portal_access_service_token": SERVICE_TOKEN,
            "portal_service_token": SERVICE_TOKEN,
        },
    ],
)
def test_invalid_connection_configuration(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate(values)


def test_redirect_policy_refuses_token_forwarding() -> None:
    assert (
        portal_session._NoRedirect().redirect_request(
            None, None, 302, "", {}, "https://foreign.invalid"
        )
        is None
    )


CONTRACT_ROOT = Path(__file__).resolve().parents[3] / "docs/contracts/portal-kernel-paid"
RUNTIME_MODELS = {
    "exchange-request-v1": portal_session.PortalExchangeRequest,
    "exchange-response-v2": portal_session.PortalExchangeResponse,
    "introspection-response-v2": portal_session.PortalIntrospectionResponse,
}
CONTRACT_CASES = [
    (valid, case)
    for valid, filename in ((True, "valid.json"), (False, "invalid.json"))
    for case in (
        json.loads((CONTRACT_ROOT / "fixtures" / filename).read_text())
        + json.loads((CONTRACT_ROOT / "fixtures" / ("backend-" + filename)).read_text())
    )
    if case["contract"] in RUNTIME_MODELS
]


@pytest.mark.parametrize(
    "valid,case", CONTRACT_CASES, ids=[case["name"] for _, case in CONTRACT_CASES]
)
def test_runtime_models_respect_independent_contract_fixtures(
    valid: bool, case: dict[str, Any]
) -> None:
    model = RUNTIME_MODELS[case["contract"]]
    raw = json.dumps(case["payload"])
    if valid:
        model.model_validate_json(raw)
    else:
        with pytest.raises(ValidationError):
            model.model_validate_json(raw)


def test_wire_ttl_bound_accepts_supported_clock_difference(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = exchange_payload()
    payload["expires_at"] = (
        datetime.now(UTC) + timedelta(seconds=portal_session.DELEGATION_TTL_SECONDS + 3)
    ).isoformat()
    intercept(monkeypatch, payload)
    response = client.post(EXCHANGE_PATH, json={"code": CODE, "code_verifier": VERIFIER})
    assert response.status_code == HTTPStatus.OK


def test_error_body_transport_failure_is_dependency_unavailable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    opener = intercept(monkeypatch, None)

    class InterruptedBody(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            raise TimeoutError(USER_TOKEN)

    body = InterruptedBody()
    opener.open.side_effect = HTTPError("https://portal.invalid", 401, "", {}, body)
    response = client.get("/test/principal", headers={"Authorization": "Bearer " + USER_TOKEN})
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert USER_TOKEN not in response.text
