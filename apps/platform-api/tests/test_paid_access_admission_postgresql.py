"""Real PostgreSQL coherence, paid HTTP admission and transaction races; synthetic authority."""

import asyncio
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from threading import Barrier, Event
from time import monotonic, sleep
from uuid import uuid4

import httpx
import pytest
import sqlalchemy as sa
from anytoolai_platform_api import paid_access
from anytoolai_platform_api.errors import ApiError
from anytoolai_platform_api.paid_access import (
    AccessSnapshot,
    evict,
    get_snapshot_client,
    install,
    invalidate,
    optional_portal_user,
)
from anytoolai_platform_api.portal_session import PortalUserPrincipal
from anytoolai_platform_api.routers import handoffs
from anytoolai_platform_core.handoffs.models import HandoffStartPolicy, HandoffStatus
from anytoolai_platform_core.products.models import UsageMetricDefinition
from anytoolai_platform_core.quotas.execution_repository import PaidAllowanceUsageRepository
from anytoolai_platform_core.quotas.models import ExecutionOwner, ExecutionOwnerKind
from anytoolai_platform_core.storage.db import (
    execution_reservations_table,
    jobs_table,
    paid_access_coherence_table,
    paid_allowance_usage_table,
    product_handoffs_table,
    scenario_sessions_table,
)
from anytoolai_platform_core.storage.transactions import build_session_factory, transaction_boundary
from fastapi.testclient import TestClient
from pydantic import SecretStr
from test_handoffs_api import _seed_source
from test_scenario_runtime_api import _create_test_app, _start_payload

from tests.db_support import provision_database

pytestmark = [pytest.mark.postgresql, pytest.mark.slow]
NEXT_REVISION = 2
POST_WAIT_CHECK = 2
SCENARIO = "kernel_demo.single_action_smoke_v1"
METRIC = "kernel_demo.test_runs"
START = f"/v1/products/kernel_demo/scenarios/{SCENARIO}/start"


def snapshot(owner, *, revision=1, quantity=1, allowance_id=None, ttl=180):
    now = datetime.now(UTC)
    return AccessSnapshot.model_validate(
        {
            "schema_version": 2,
            "tenant_id": owner.tenant_id,
            "region": owner.region,
            "user_id": owner.owner_id,
            "access_revision": revision,
            "refresh_after": (now + timedelta(seconds=60)).isoformat(),
            "expires_at": (now + timedelta(seconds=ttl)).isoformat(),
            "grants": [{"product_id": "kernel_demo", "valid_until": None}],
            "allowances": [
                {
                    "allowance_id": allowance_id or str(uuid4()),
                    "product_id": "kernel_demo",
                    "metric_key": METRIC,
                    "unit": "run",
                    "quantity": quantity,
                }
            ],
        }
    )


@pytest.fixture
def runtime():
    with provision_database(
        database_name_prefix="any766_admission", skip_reason="paid admission"
    ) as (engine, _, _):
        factory = build_session_factory(engine)
        app = _create_test_app(factory)
        registry = app.state.runtime.config_registry
        product = registry.get_product("kernel_demo")

        scenarios = {
            key: replace(value, paid_metric_key=METRIC) for key, value in registry.scenarios.items()
        }
        registry = replace(
            registry,
            scenarios=scenarios,
            products={
                **registry.products,
                "kernel_demo": replace(
                    product, usage_metrics=(UsageMetricDefinition(METRIC, "run", False),)
                ),
            },
        )
        app.state.runtime = replace(app.state.runtime, config_registry=registry)
        owner = ExecutionOwner("anytoolai", "ru", ExecutionOwnerKind.portal_user, str(uuid4()))
        principal = PortalUserPrincipal(
            owner,
            datetime.now(UTC) + timedelta(minutes=20),
            consumer_id="platform-kernel",
            consumer_policy_revision=1,
        )
        app.dependency_overrides[optional_portal_user] = lambda: principal
        document = snapshot(owner)

        class Client:
            calls = 0

            def fetch(self, actual):
                assert actual == owner
                self.calls += 1
                return document

        remote = Client()
        app.dependency_overrides[get_snapshot_client] = lambda: remote
        yield factory, app, registry, principal, document, remote


def rows(factory, table):
    with transaction_boundary(factory) as session:
        return list(session.execute(sa.select(table)).mappings())


def test_paid_http_replay_precedes_revocation_outage_and_mutable_configuration(runtime):
    factory, app, registry, principal, document, remote = runtime
    client = TestClient(app)
    payload = _start_payload()
    payload["user_id"] = "untrusted-body"
    first = client.post(START, json=payload, headers={"Idempotency-Key": "original"})
    assert first.status_code == HTTPStatus.OK, first.text
    reservation = rows(factory, execution_reservations_table)[0]
    assert reservation["owner_id"] == principal.owner.owner_id
    assert rows(factory, scenario_sessions_table)[0]["guest_id"] is None
    with transaction_boundary(factory) as session:
        invalidate(session, principal.owner, 2)
    app.state.settings = app.state.settings.model_copy(update={"enabled_product_ids": frozenset()})
    app.state.runtime = replace(app.state.runtime, config_registry=replace(registry, scenarios={}))
    replay = client.post(START, json=payload, headers={"Idempotency-Key": "original"})
    assert replay.status_code == HTTPStatus.OK and replay.json() == first.json()
    assert remote.calls == 1
    assert len(rows(factory, execution_reservations_table)) == 1
    payload["input"]["text"] = "different"
    assert (
        client.post(START, json=payload, headers={"Idempotency-Key": "original"}).status_code
        == HTTPStatus.CONFLICT
    )
    app.state.runtime = replace(app.state.runtime, config_registry=registry)
    assert (
        client.post(
            START, json=_start_payload(), headers={"Idempotency-Key": "disabled"}
        ).status_code
        == HTTPStatus.NOT_FOUND
    )
    app.state.settings = app.state.settings.model_copy(update={"enabled_product_ids": None})
    assert (
        client.post(START, json=_start_payload(), headers={"Idempotency-Key": "new"}).status_code
        == HTTPStatus.SERVICE_UNAVAILABLE
    )


def test_stale_install_after_invalidation_and_eviction_never_lowers_floor(runtime):
    factory, _, _, principal, document, _ = runtime
    with transaction_boundary(factory) as session:
        assert install(session, principal.owner, document)
    locked, release = Event(), Event()

    def invalidation():
        with transaction_boundary(factory) as session:
            invalidate(session, principal.owner, 2)
            locked.set()
            assert release.wait(5)

    def stale_install():
        assert locked.wait(5)
        with transaction_boundary(factory) as session:
            return install(session, principal.owner, document)

    with ThreadPoolExecutor(2) as pool:
        inv = pool.submit(invalidation)
        assert locked.wait(5)
        stale = pool.submit(stale_install)
        assert_database_wait(factory)
        release.set()
        inv.result(5)
        assert stale.result(5) is False
    with transaction_boundary(factory) as session:
        evict(session, principal.owner)
    row = rows(factory, paid_access_coherence_table)[0]
    assert row["revision_floor"] == NEXT_REVISION and row["snapshot"] is None
    # A new Session/client process observes durable state, not a process cache.
    with transaction_boundary(factory) as session:
        assert install(session, principal.owner, snapshot(principal.owner, revision=2))
        with pytest.raises(ApiError, match="unavailable"):
            install(session, principal.owner, snapshot(principal.owner, revision=2, quantity=2))


def test_last_unit_http_competition_reserves_only_one(runtime, monkeypatch):
    factory, app, _, _, _, remote = runtime
    barrier = Barrier(2)
    fetch = remote.fetch

    def fetch_together(owner):
        barrier.wait(timeout=5)
        return fetch(owner)

    monkeypatch.setattr(remote, "fetch", fetch_together)

    async def compete():
        # One server event loop, with real concurrent sync handlers and PG transactions.
        # Separate TestClient event loops race FastAPI's lazy included-router cache itself.
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            return await asyncio.gather(
                *(
                    client.post(START, json=_start_payload(), headers={"Idempotency-Key": key})
                    for key in ("one", "two")
                )
            )

    results = asyncio.run(compete())
    assert sorted(r.status_code for r in results) == [
        HTTPStatus.OK,
        HTTPStatus.TOO_MANY_REQUESTS,
    ], [(r.status_code, r.text) for r in results]
    assert len(rows(factory, execution_reservations_table)) == 1
    assert rows(factory, paid_allowance_usage_table)[0]["reserved_count"] == 1
    assert len(rows(factory, jobs_table)) == 1


@pytest.mark.parametrize(
    "expired_authority,expected",
    [
        ("principal", HTTPStatus.UNAUTHORIZED),
        ("snapshot", HTTPStatus.SERVICE_UNAVAILABLE),
        ("grant", HTTPStatus.SERVICE_UNAVAILABLE),
    ],
)
def test_expiry_after_real_postgresql_bucket_wait_rolls_back_entire_start(
    runtime,
    monkeypatch,
    expired_authority,
    expected,
):
    factory, app, _, principal, document, _ = runtime
    grant_end = datetime.now(UTC) + timedelta(seconds=120)
    document = document.model_copy(
        update={
            "grants": [document.grants[0].model_copy(update={"valid_until": grant_end})],
            "expires_at": min(document.expires_at, grant_end),
        }
    )
    with transaction_boundary(factory) as session:
        install(session, principal.owner, document)
    original_now = paid_access.db_now
    expired = Event()
    deadline = {
        "principal": principal.valid_until,
        "snapshot": document.expires_at,
        "grant": grant_end,
    }[expired_authority]
    monkeypatch.setattr(
        paid_access,
        "db_now",
        lambda session: (
            deadline + timedelta(seconds=1) if expired.is_set() else original_now(session)
        ),
    )
    with ThreadPoolExecutor(1) as pool:
        # Real PG row locking, observed through pg_stat_activity before advancing wall time.
        with transaction_boundary(factory) as holder:
            holder.execute(sa.select(paid_allowance_usage_table).with_for_update()).all()
            future = pool.submit(
                lambda: TestClient(app).post(
                    START, json=_start_payload(), headers={"Idempotency-Key": "wait"}
                )
            )
            assert_database_wait(factory)
            expired.set()
        response = future.result(5)
    assert response.status_code == expected, response.text
    for table in (jobs_table, scenario_sessions_table, execution_reservations_table):
        assert rows(factory, table) == []
    assert rows(factory, paid_allowance_usage_table)[0]["reserved_count"] == 0


def assert_database_wait(factory):
    until = monotonic() + 5
    while monotonic() < until:
        with transaction_boundary(factory) as session:
            waiting = session.execute(
                sa.text(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                    "AND wait_event_type = 'Lock' AND pid <> pg_backend_pid()"
                )
            ).scalar_one()
        if waiting:
            return
        sleep(0.01)
    pytest.fail("admission did not reach a PostgreSQL lock wait")


def test_install_race_and_same_revision_immutability_survive_eviction(runtime):
    factory, _, _, principal, document, _ = runtime
    newer = snapshot(principal.owner, revision=2, allowance_id=document.allowances[0].allowance_id)
    ready, release = Event(), Event()

    def newer_install():
        with transaction_boundary(factory) as session:
            install(session, principal.owner, newer)
            ready.set()
            assert release.wait(5)

    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(newer_install)
        assert ready.wait(5)
        second = pool.submit(lambda: install_one(factory, principal.owner, document))
        assert_database_wait(factory)
        release.set()
        first.result(5)
        assert second.result(5) is False
    with transaction_boundary(factory) as session:
        evict(session, principal.owner)
    changed = newer.model_copy(
        update={"allowances": [newer.allowances[0].model_copy(update={"quantity": 2})]}
    )
    with pytest.raises(ApiError):
        install_one(factory, principal.owner, changed)
    assert rows(factory, paid_access_coherence_table)[0]["revision_floor"] == NEXT_REVISION


def install_one(factory, owner, document):
    with transaction_boundary(factory) as session:
        return install(session, owner, document)


def seed_paid_source(factory, principal):

    with transaction_boundary(factory) as session:
        source, artifact = _seed_source(session)
        session.execute(
            sa.update(scenario_sessions_table)
            .where(scenario_sessions_table.c.id == source)
            .values(
                guest_id=None,
                user_id=principal.owner.owner_id,
                metadata={"execution_owner": asdict(principal.owner)},
            )
        )
    return source, artifact


def create_paid_handoff(client, source, artifact):
    response = client.post(
        "/v1/handoffs",
        json={
            "handoff_definition_id": "kernel_demo_source_to_target_v1",
            "source_scenario_session_id": source,
            "source_artifact_id": artifact,
        },
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()["handoff_token"]


def test_late_handoff_authority_refusal_rolls_back_every_effect_and_remains_retryable(
    runtime, monkeypatch
):

    factory, app, _, principal, document, _ = runtime
    client = TestClient(app)
    source, artifact = seed_paid_source(factory, principal)
    token = create_paid_handoff(client, source, artifact)
    with transaction_boundary(factory) as session:
        install(session, principal.owner, document)
    calls = 0
    real = handoffs.eligible_allowance

    def late_failure(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == POST_WAIT_CHECK:
            raise paid_access.unavailable()
        return real(*args, **kwargs)

    monkeypatch.setattr(handoffs, "eligible_allowance", late_failure)
    response = client.post(f"/v1/handoffs/{token}/accept", json={})
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE, response.text
    handoff = rows(factory, product_handoffs_table)[0]
    assert handoff["status"] == HandoffStatus.created
    assert handoff["target_scenario_session_id"] is None and handoff["error_code"] is None
    assert len(rows(factory, scenario_sessions_table)) == 1
    assert len(rows(factory, jobs_table)) == 1
    assert rows(factory, execution_reservations_table) == []
    monkeypatch.setattr(handoffs, "eligible_allowance", real)
    assert client.post(f"/v1/handoffs/{token}/accept", json={}).status_code == HTTPStatus.OK
    with transaction_boundary(factory) as session:
        invalidate(session, principal.owner, 2)
    app.state.settings = app.state.settings.model_copy(update={"enabled_product_ids": frozenset()})
    assert client.post(f"/v1/handoffs/{token}/accept", json={}).status_code == HTTPStatus.OK


def test_all_paid_resource_surfaces_refuse_guest_and_foreign_owner(runtime):
    factory, app, _, principal, _, _ = runtime
    source, artifact = seed_paid_source(factory, principal)
    client = TestClient(app)
    token = create_paid_handoff(client, source, artifact)
    for identity in (
        None,
        replace(principal, owner=replace(principal.owner, owner_id=str(uuid4()))),
    ):
        app.dependency_overrides[optional_portal_user] = constant_identity(identity)
        for method, path, payload in [
            ("get", f"/v1/scenario-sessions/{source}", None),
            (
                "post",
                f"/v1/scenario-sessions/{source}/next-actions/copy_result",
                {"checkpoint_id": "result_ready"},
            ),
            ("get", f"/v1/results/{artifact}", None),
            ("get", f"/v1/handoffs/{token}", None),
            ("post", f"/v1/handoffs/{token}/accept", {}),
            ("post", f"/v1/handoffs/{token}/decline", {}),
            (
                "post",
                "/v1/handoffs",
                {
                    "handoff_definition_id": "kernel_demo_source_to_target_v1",
                    "source_scenario_session_id": source,
                    "source_artifact_id": artifact,
                },
            ),
        ]:
            response = client.request(method, path, json=payload)
            assert response.status_code == HTTPStatus.NOT_FOUND, (path, response.text)


def test_invalidation_receiver_auth_scope_permission_rotation_and_no_store(runtime):
    factory, app, _, principal, _, _ = runtime

    app.state.settings = app.state.settings.model_copy(
        update={
            "portal_service_token": SecretStr("s" * 40),
            "portal_service_token_previous": SecretStr("p" * 40),
            "portal_access_invalidation_enabled": True,
        }
    )
    client = TestClient(app)
    payload = {
        "schema_version": 1,
        "tenant_id": "anytoolai",
        "region": "ru",
        "user_id": principal.owner.owner_id,
        "access_revision": 2,
    }
    path = "/internal/v1/access-invalidations"
    assert client.post(path, json=payload).status_code == HTTPStatus.UNAUTHORIZED
    for token in ("s" * 40, "p" * 40):
        response = client.post(path, json=payload, headers={"Authorization": f"Bearer {token}"})
        assert (
            response.status_code == HTTPStatus.NO_CONTENT
            and response.headers["cache-control"] == "no-store"
        )
    headers = {"Authorization": "Bearer " + "s" * 40}
    assert (
        client.post(path, json={**payload, "region": "eu"}, headers=headers).status_code
        == HTTPStatus.FORBIDDEN
    )
    assert (
        client.post(
            path, json=payload, headers={**headers, "Origin": "https://browser.invalid"}
        ).status_code
        == HTTPStatus.FORBIDDEN
    )
    assert (
        client.post(
            path, json=payload, headers=[("Authorization", "Bearer " + "s" * 40)] * 2
        ).status_code
        == HTTPStatus.UNAUTHORIZED
    )
    assert (
        client.post(path, json={**payload, "access_revision": True}, headers=headers).status_code
        == HTTPStatus.UNPROCESSABLE_ENTITY
    )
    app.state.settings = app.state.settings.model_copy(
        update={"portal_access_invalidation_enabled": False}
    )
    assert client.post(path, json=payload, headers=headers).status_code == HTTPStatus.FORBIDDEN
    assert rows(factory, paid_access_coherence_table)[0]["revision_floor"] == NEXT_REVISION


def constant_identity(value):
    return lambda: value


def test_empty_zero_and_positive_revisions_deny_without_acceptance(runtime):
    factory, app, _, principal, document, remote = runtime
    empty = document.model_copy(update={"access_revision": 0, "grants": [], "allowances": []})
    with transaction_boundary(factory) as session:
        install(session, principal.owner, empty)
    client = TestClient(app)
    assert (
        client.post(START, json=_start_payload(), headers={"Idempotency-Key": "zero"}).status_code
        == HTTPStatus.FORBIDDEN
    )
    with transaction_boundary(factory) as session:
        install(session, principal.owner, empty.model_copy(update={"access_revision": 1}))
    assert (
        client.post(
            START, json=_start_payload(), headers={"Idempotency-Key": "positive-empty"}
        ).status_code
        == HTTPStatus.FORBIDDEN
    )
    assert rows(factory, jobs_table) == [] and rows(factory, execution_reservations_table) == []
    assert remote.calls == 0


def test_valid_finite_snapshot_survives_outage_but_not_expiry(runtime, monkeypatch):
    factory, app, _, principal, document, remote = runtime
    document = document.model_copy(
        update={"refresh_after": datetime.now(UTC) - timedelta(seconds=1)}
    )
    with transaction_boundary(factory) as session:
        install(session, principal.owner, document)
    monkeypatch.setattr(
        remote, "fetch", lambda owner: (_ for _ in ()).throw(paid_access.unavailable())
    )
    client = TestClient(app)
    response = client.post(START, json=_start_payload(), headers={"Idempotency-Key": "outage"})
    assert response.status_code == HTTPStatus.OK, response.text
    monkeypatch.setattr(
        paid_access, "db_now", lambda session: document.expires_at + timedelta(seconds=1)
    )
    assert (
        client.post(
            START, json=_start_payload(), headers={"Idempotency-Key": "expired"}
        ).status_code
        == HTTPStatus.SERVICE_UNAVAILABLE
    )
    assert len(rows(factory, jobs_table)) == 1


def test_frozen_tuple_conflict_is_local_and_usage_is_never_reset(runtime):
    factory, app, registry, principal, document, _ = runtime
    with transaction_boundary(factory) as session:
        install(session, principal.owner, document)
    conflicting = document.model_copy(
        update={
            "access_revision": 2,
            "allowances": [document.allowances[0].model_copy(update={"quantity": 2})],
        }
    )
    with transaction_boundary(factory) as session:
        install(session, principal.owner, conflicting)
    client = TestClient(app)
    assert (
        client.post(
            START, json=_start_payload(), headers={"Idempotency-Key": "conflict"}
        ).status_code
        == HTTPStatus.CONFLICT
    )
    assert rows(factory, paid_allowance_usage_table)[0]["quantity"] == 1
    assert rows(factory, execution_reservations_table) == []
    # A proven replacement cycle uses its own new immutable bucket.
    with transaction_boundary(factory) as session:
        install(session, principal.owner, snapshot(principal.owner, revision=3))
    assert (
        client.post(
            START, json=_start_payload(), headers={"Idempotency-Key": "replacement"}
        ).status_code
        == HTTPStatus.OK
    )
    assert len(rows(factory, paid_allowance_usage_table)) == NEXT_REVISION


def test_owned_historical_results_and_deferred_handoff_need_identity_not_grants(runtime):

    factory, app, registry, principal, document, _ = runtime
    definition = registry.get_handoff("kernel_demo_source_to_target_v1")
    registry = replace(
        registry,
        handoffs={
            **registry.handoffs,
            definition.handoff_id: replace(
                definition, target_start_policy=HandoffStartPolicy.deferred
            ),
        },
    )
    app.state.runtime = replace(app.state.runtime, config_registry=registry)
    source, artifact = seed_paid_source(factory, principal)
    client = TestClient(app)
    token = create_paid_handoff(client, source, artifact)
    response = client.post(f"/v1/handoffs/{token}/accept", json={})
    assert response.status_code == HTTPStatus.OK, response.text
    target = response.json()["target_scenario_session_id"]
    assert rows(factory, execution_reservations_table) == []
    with transaction_boundary(factory) as session:
        invalidate(session, principal.owner, 2)
    assert client.get(f"/v1/results/{artifact}").status_code == HTTPStatus.OK
    assert client.get(f"/v1/scenario-sessions/{target}").status_code == HTTPStatus.OK
    app.dependency_overrides[optional_portal_user] = constant_identity(None)
    assert client.get(f"/v1/scenario-sessions/{target}").status_code == HTTPStatus.NOT_FOUND


def test_admission_commit_and_invalidation_ack_are_serialized(runtime, monkeypatch):
    factory, app, _, principal, document, _ = runtime
    install_one(factory, principal.owner, document)
    reserved, finish = Event(), Event()
    original = PaidAllowanceUsageRepository.reserve_if_available

    def hold_reserved(self, record):
        result = original(self, record)
        reserved.set()
        assert finish.wait(5)
        return result

    monkeypatch.setattr(PaidAllowanceUsageRepository, "reserve_if_available", hold_reserved)

    def invalidate_now():
        with transaction_boundary(factory) as session:
            invalidate(session, principal.owner, NEXT_REVISION)

    with ThreadPoolExecutor(2) as pool:
        admission = pool.submit(
            lambda: TestClient(app).post(
                START, json=_start_payload(), headers={"Idempotency-Key": "linearized"}
            )
        )
        assert reserved.wait(5)
        invalidation = pool.submit(invalidate_now)
        assert_database_wait(factory)
        assert not invalidation.done()
        finish.set()
        assert admission.result(5).status_code == HTTPStatus.OK
        invalidation.result(5)
    assert rows(factory, paid_access_coherence_table)[0]["revision_floor"] == NEXT_REVISION
    assert len(rows(factory, execution_reservations_table)) == 1


def test_duplicate_metric_allowances_deny_only_dependent_scenario(runtime):
    factory, app, registry, principal, document, _ = runtime
    other_id, other_metric = "kernel_demo.other_scenario_v1", "kernel_demo.other_runs"
    scenario = registry.get_scenario(SCENARIO)
    product = registry.get_product("kernel_demo")
    registry = replace(
        registry,
        scenarios={
            **registry.scenarios,
            other_id: replace(scenario, scenario_id=other_id, paid_metric_key=other_metric),
        },
        products={
            **registry.products,
            "kernel_demo": replace(
                product,
                scenarios=(*product.scenarios, other_id),
                usage_metrics=(
                    *product.usage_metrics,
                    UsageMetricDefinition(other_metric, "run", False),
                ),
            ),
        },
    )
    app.state.runtime = replace(app.state.runtime, config_registry=registry)
    document = document.model_copy(
        update={
            "allowances": [
                document.allowances[0],
                document.allowances[0].model_copy(update={"allowance_id": str(uuid4())}),
                document.allowances[0].model_copy(
                    update={"allowance_id": str(uuid4()), "metric_key": other_metric}
                ),
            ]
        }
    )
    install_one(factory, principal.owner, document)
    client = TestClient(app)
    assert (
        client.post(
            START, json=_start_payload(), headers={"Idempotency-Key": "ambiguous"}
        ).status_code
        == HTTPStatus.FORBIDDEN
    )
    response = client.post(
        f"/v1/products/kernel_demo/scenarios/{other_id}/start",
        json=_start_payload(),
        headers={"Idempotency-Key": "independent"},
    )
    assert response.status_code == HTTPStatus.OK, response.text


def test_revision_floor_survives_fresh_interpreter_restart(runtime):
    factory, _, _, principal, document, _ = runtime
    install_one(factory, principal.owner, document)
    with transaction_boundary(factory) as session:
        invalidate(session, principal.owner, NEXT_REVISION)
        evict(session, principal.owner)
    environment = os.environ.copy()
    environment["ANY766_RESTART_DATABASE"] = factory.kw["bind"].url.render_as_string(
        hide_password=False
    )
    environment["ANY766_RESTART_USER"] = principal.owner.owner_id
    code = """
import asyncio
import os
import sqlalchemy as sa
from anytoolai_platform_core.quotas.access_coherence import AccessCoherenceRepository
from anytoolai_platform_core.quotas.models import ExecutionOwner, ExecutionOwnerKind
from anytoolai_platform_core.storage.transactions import build_session_factory, transaction_boundary
engine = sa.create_engine(os.environ['ANY766_RESTART_DATABASE'])
try:
    with transaction_boundary(build_session_factory(engine)) as session:
        owner = ExecutionOwner('anytoolai', 'ru', ExecutionOwnerKind.portal_user,
                               os.environ['ANY766_RESTART_USER'])
        row = AccessCoherenceRepository(session, owner).read()
        assert row['revision_floor'] == 2 and row['snapshot'] is None
        assert row['snapshot_revision'] == 1 and row['semantic_digest']
finally:
    engine.dispose()
"""
    subprocess.run(
        [sys.executable, "-c", code], env=environment, check=True, capture_output=True, timeout=10
    )
