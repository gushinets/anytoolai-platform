"""Authenticated read/replay P fences a late old-P start without requiring grants."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from threading import Event
from unittest.mock import Mock

import pytest
from anytoolai_platform_api.paid_access import (
    AccessSnapshot,
    get_snapshot_client,
    optional_portal_user,
)
from anytoolai_platform_api.portal_session import PortalSessionClient, get_portal_session_client
from anytoolai_platform_core.quotas.access_coherence import AccessCoherenceRepository
from anytoolai_platform_core.quotas.models import ExecutionOwner
from anytoolai_platform_core.storage.db import (
    execution_reservations_table,
    jobs_table,
    paid_allowance_usage_table,
    scenario_sessions_table,
)
from anytoolai_platform_core.storage.transactions import transaction_boundary
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.exc import SQLAlchemyError
from test_paid_access_admission_postgresql import START, rows, snapshot
from test_paid_access_admission_postgresql import runtime as admission_runtime
from test_scenario_runtime_api import _start_payload

pytestmark = [pytest.mark.postgresql, pytest.mark.slow]
runtime = admission_runtime
NEW_POLICY = 2


def headers(token: str, key: str = "original") -> dict[str, str]:
    return {"Authorization": "Bearer " + token * 43, "Idempotency-Key": key}


def observe_through_route(
    client: TestClient, surface: str, original: dict, document: AccessSnapshot
) -> Response:
    if surface in {"replay", "conflict"}:
        payload = _start_payload()
        if surface == "conflict":
            payload["input"]["text"] = "different request under the original key"
        return client.post(START, json=payload, headers=headers("c"))
    if surface == "usage":
        return client.get(
            "/v1/products/kernel_demo/paid-usage",
            params={"allowance_id": document.allowances[0].allowance_id},
            headers=headers("c"),
        )
    session_id = original["scenario_session_id"] if surface == "session" else "missing"
    return client.get("/v1/scenario-sessions/" + session_id, headers=headers("c"))


@pytest.mark.parametrize("surface", ["replay", "session", "usage", "missing-session", "conflict"])
def test_authenticated_policy_observation_fences_late_start_on_every_read_path(
    runtime, surface: str
) -> None:
    factory, app, _, principal, _, _ = runtime
    document = snapshot(principal.owner, quantity=4)
    delayed, release = Event(), Event()

    class Authority:
        calls = 0

        def fetch(self, owner: ExecutionOwner) -> AccessSnapshot:
            assert owner == principal.owner
            self.calls += 1
            assert self.calls == 1, "Read/replay must not fetch a snapshot"
            return document

    class IdentityTransport(PortalSessionClient):
        def _post(self, operation: str, payload: dict) -> bytes:
            # Substitute only the remote transport: retain production wire parsing,
            # scope/expiry checks and the actual request dependencies.
            assert operation == "introspect"
            assert factory.kw["bind"].pool.checkedout() == 0
            token = payload["access_token"]
            response = json.dumps(
                {
                    "schema_version": 2,
                    "consumer_id": principal.consumer_id,
                    "consumer_policy_revision": NEW_POLICY if token == "c" * 43 else 1,
                    "tenant_id": principal.owner.tenant_id,
                    "region": principal.owner.region,
                    "user_id": principal.owner.owner_id,
                    "valid_until": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
                }
            ).encode()
            if token == "b" * 43:
                delayed.set()
                assert release.wait(10)
            return response

    authority = Authority()
    identity = IdentityTransport(app.state.settings)
    app.dependency_overrides.pop(optional_portal_user)
    app.dependency_overrides[get_portal_session_client] = lambda: identity
    app.dependency_overrides[get_snapshot_client] = lambda: authority
    client = TestClient(app)

    def start(token: str, key: str) -> Response:
        return client.post(START, json=_start_payload(), headers=headers(token, key))

    def retained_work() -> dict:
        return {
            table.name: rows(factory, table)
            for table in (
                jobs_table,
                scenario_sessions_table,
                execution_reservations_table,
                paid_allowance_usage_table,
            )
        }

    first = start("a", "original")
    assert first.status_code == HTTPStatus.OK, first.text
    original = first.json()
    session_url = "/v1/scenario-sessions/" + original["scenario_session_id"]
    before = retained_work()
    with ThreadPoolExecutor(1) as pool:
        late = pool.submit(start, "b", "late-new-request")
        try:
            assert delayed.wait(10)
            observed = observe_through_route(client, surface, original, document)
            expected = {"missing-session": HTTPStatus.NOT_FOUND, "conflict": HTTPStatus.CONFLICT}
            assert observed.status_code == expected.get(surface, HTTPStatus.OK), observed.text
            if surface == "replay":
                assert observed.json() == original
            with transaction_boundary(factory) as db:
                state = AccessCoherenceRepository(
                    db, principal.owner, consumer_id=principal.consumer_id
                ).read()
                assert state["policy_floor"] == NEW_POLICY
                assert state["snapshot"] is None
                assert state["revision_floor"] == document.access_revision
            assert retained_work() == before
        finally:
            release.set()
        refused = late.result(10)
    assert refused.status_code == HTTPStatus.SERVICE_UNAVAILABLE, refused.text
    assert refused.json()["error"]["code"] == "paid_access_unavailable"
    assert document.refresh_after > datetime.now(UTC)  # Refusal is P, not expired authority.
    assert retained_work() == before

    # A still-valid identity from an older in-flight introspection remains enough
    # for historical read/replay, even with the snapshot evicted and no grants fetched.
    assert start("a", "original").json() == original
    assert client.get(session_url, headers=headers("a")).status_code == HTTPStatus.OK
    assert authority.calls == 1
    with transaction_boundary(factory) as db:
        assert (
            AccessCoherenceRepository(
                db, principal.owner, consumer_id=principal.consumer_id
            ).read()["policy_floor"]
            == NEW_POLICY
        )
    assert retained_work() == before


def test_policy_observation_storage_failure_refuses_without_partial_commit(
    runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory, app, _, principal, _, _ = runtime
    client = TestClient(app)
    first = client.post(START, json=_start_payload(), headers=headers("a"))
    assert first.status_code == HTTPStatus.OK
    url = "/v1/scenario-sessions/" + first.json()["scenario_session_id"]
    identity = Mock(spec=PortalSessionClient)
    identity.introspect.return_value = replace(principal, consumer_policy_revision=NEW_POLICY)
    app.dependency_overrides.pop(optional_portal_user)
    app.dependency_overrides[get_portal_session_client] = lambda: identity
    observe = AccessCoherenceRepository.observe_policy

    def interrupted_observation(repository: AccessCoherenceRepository, revision: int) -> bool:
        observe(repository, revision)
        raise SQLAlchemyError("synthetic persistence failure after policy write")

    with factory() as db:
        before = dict(
            AccessCoherenceRepository(db, principal.owner, consumer_id=principal.consumer_id).read()
        )
    with monkeypatch.context() as fault:
        fault.setattr(AccessCoherenceRepository, "observe_policy", interrupted_observation)
        refused = client.get(url, headers=headers("c"))
    assert refused.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert refused.json()["error"]["code"] == "paid_access_unavailable"
    with factory() as db:
        assert (
            dict(
                AccessCoherenceRepository(
                    db, principal.owner, consumer_id=principal.consumer_id
                ).read()
            )
            == before
        )
    assert client.get(url, headers=headers("c")).status_code == HTTPStatus.OK
    with factory() as db:
        state = AccessCoherenceRepository(
            db, principal.owner, consumer_id=principal.consumer_id
        ).read()
        assert state["policy_floor"] == NEW_POLICY
        assert state["snapshot"] is None
