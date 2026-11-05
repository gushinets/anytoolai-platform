from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa
from anytoolai_platform_api.routers.handoffs import _service as handoff_service
from anytoolai_platform_api.routers.scenario_runtime import _runtime_service
from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.handoffs.models import AcceptHandoffCommand, HandoffStartPolicy
from anytoolai_platform_core.handoffs.repository import HandoffRepository
from anytoolai_platform_core.handoffs.service import (
    HandoffAcceptanceExecutionError,
    HandoffExpiredError,
    HandoffNotActionableError,
    HandoffSourceInvalidError,
)
from anytoolai_platform_core.products.models import UsageMetricDefinition
from anytoolai_platform_core.quotas.execution_repository import (
    ExecutionReservationRepository,
    PaidAllowanceUsageRepository,
)
from anytoolai_platform_core.quotas.finalization import release_execution
from anytoolai_platform_core.quotas.models import (
    ExecutionOwner,
    ExecutionOwnerKind,
    ExecutionReplayIdentity,
    ExecutionReplayNamespace,
    PaidAllowance,
)
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.scenarios.service import (
    ScenarioRuntimeService,
    compute_idempotency_request_hash,
)
from anytoolai_platform_core.storage.db import (
    event_log_table,
    execution_reservations_table,
    guest_quota_usage_table,
    jobs_table,
    paid_allowance_usage_table,
    product_handoffs_table,
    scenario_sessions_table,
)
from anytoolai_platform_core.storage.transactions import build_session_factory, transaction_boundary
from anytoolai_platform_core.workflows.models import JobConsumptionMode, JobRecord
from anytoolai_platform_core.workflows.repository import JobRepository
from test_handoffs_api import _create, _request, _seed_source
from test_scenario_runtime_api import _create_test_app, _start_payload

from tests.db_support import provision_database

pytestmark = [pytest.mark.postgresql, pytest.mark.slow]
SCENARIO = "kernel_demo.single_action_smoke_v1"
METRIC = "kernel_demo.test_runs"


@pytest.fixture
def runtime():
    with provision_database(
        database_name_prefix="any507_admission", skip_reason="execution reservation admission"
    ) as (engine, _, _):
        factory = build_session_factory(engine)
        app = _create_test_app(factory)
        registry = app.state.runtime.config_registry
        product = registry.get_product("kernel_demo")
        registry = replace(
            registry,
            products={
                **registry.products,
                "kernel_demo": replace(
                    product, usage_metrics=(UsageMetricDefinition(METRIC, "run", False),)
                ),
            },
        )
        app.state.runtime = replace(app.state.runtime, config_registry=registry)
        yield factory, app, registry


def allowance(**changes) -> PaidAllowance:
    return replace(
        PaidAllowance(
            owner=ExecutionOwner("anytoolai", "ru", ExecutionOwnerKind.portal_user, str(uuid4())),
            allowance_id=str(uuid4()),
            product_id="kernel_demo",
            metric_key=METRIC,
            unit="run",
            quantity=1,
        ),
        **changes,
    )


def start(session, registry, grant=None, key="request", **changes):
    values = {
        "tenant_id": "anytoolai",
        "region": "ru",
        "product_id": "kernel_demo",
        "scenario_id": SCENARIO,
        "frontend_id": "kernel_demo_ce",
        "input_payload": _start_payload()["input"],
        "idempotency_key": key,
    }
    if grant is not None:
        values.update(execution_owner=grant.owner, paid_allowance=grant)
    else:
        values["guest_id"] = "guest_demo"
    values.update(changes)
    return _runtime_service(session=session, registry=registry).start_session(**values)


def rows(factory, table):
    with transaction_boundary(factory) as session:
        return list(session.execute(sa.select(table)).mappings())


def assert_empty_admission(factory):
    for table in (
        scenario_sessions_table,
        jobs_table,
        execution_reservations_table,
        paid_allowance_usage_table,
        guest_quota_usage_table,
        event_log_table,
    ):
        assert rows(factory, table) == []


@pytest.mark.parametrize("paid", [True, False])
def test_concurrent_duplicate_reserves_once_and_rolls_back_every_losing_candidate(
    runtime, monkeypatch, paid
):
    factory, _, registry = runtime
    grant = allowance() if paid else None
    count = 6
    barrier = threading.Barrier(count)
    original = ScenarioRuntimeService.find_execution_replay
    local = threading.local()

    def miss_together(self, *args):
        result = original(self, *args)
        if not getattr(local, "looked", False):
            local.looked = True
            assert result is None
            barrier.wait(timeout=15)
        return result

    monkeypatch.setattr(ScenarioRuntimeService, "find_execution_replay", miss_together)

    def submit(_):
        with transaction_boundary(factory) as session:
            return start(session, registry, grant)

    with ThreadPoolExecutor(max_workers=count) as pool:
        accepted = list(pool.map(submit, range(count)))
    assert sum(not item.is_replay for item in accepted) == 1
    assert len({item.job_id for item in accepted}) == 1
    assert len({item.reservation.id for item in accepted}) == 1
    assert len(rows(factory, scenario_sessions_table)) == 1
    assert len(rows(factory, jobs_table)) == 1
    assert len(rows(factory, execution_reservations_table)) == 1
    bucket = rows(factory, paid_allowance_usage_table if paid else guest_quota_usage_table)[0]
    assert (bucket["used_count"], bucket["reserved_count"]) == (0, 1)
    events = rows(factory, event_log_table)
    assert [event["event_type"] for event in events].count("scenario.started") == 1
    assert not any(event["event_type"] == "quota.consumed" for event in events)


def test_last_unit_competitors_get_capacity_reserved_without_candidate_rows(runtime):
    factory, _, registry = runtime
    grant = allowance()
    barrier = threading.Barrier(6)

    def submit(index):
        barrier.wait(timeout=15)
        try:
            with transaction_boundary(factory) as session:
                return start(session, registry, grant, key=f"request-{index}")
        except PlatformError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=6) as pool:
        outcomes = list(pool.map(submit, range(6)))
    assert outcomes.count("quota_capacity_reserved") == 5
    assert len(rows(factory, scenario_sessions_table)) == 1
    assert len(rows(factory, jobs_table)) == 1
    assert len(rows(factory, execution_reservations_table)) == 1
    assert rows(factory, paid_allowance_usage_table)[0]["used_count"] == 0
    audits = [e for e in rows(factory, event_log_table) if e["event_type"] == "quota.capacity_reserved"]
    assert len(audits) == 5
    for event in audits:
        assert event["user_id"] == grant.owner.owner_id
        assert event["scenario_session_id"] and event["job_id"]
        assert event["properties"]["allowance_id"] == grant.allowance_id
        assert event["properties"]["available_count"] == 0
        assert event["properties"]["remaining_count"] == 1
        assert not event["properties"]["exhausted"]


def test_replay_uses_original_bucket_after_cycle_change_and_terminal_failure(runtime):
    factory, _, registry = runtime
    grant = allowance()
    with transaction_boundary(factory) as session:
        first = start(session, registry, grant)
        session.execute(
            sa.update(jobs_table)
            .where(jobs_table.c.id == first.job_id)
            .values(status="failed", completed_at=datetime.now(UTC), error_code="test_failure")
        )
    new_cycle = replace(grant, allowance_id=str(uuid4()))
    with transaction_boundary(factory) as session:
        replay = start(session, registry, new_cycle)
        no_allowance_replay = start(session, registry, grant, paid_allowance=None)
        runtime_service = _runtime_service(session=session, registry=registry)
        identity = ExecutionReplayIdentity(
            "kernel_demo", SCENARIO, ExecutionReplayNamespace.start, "request"
        )
        direct_replay = runtime_service.find_execution_replay(
            session, grant.owner, identity, first.reservation.request_hash
        )
        assert direct_replay.is_replay and direct_replay.job_id == first.job_id
        with factory() as other_session, pytest.raises(ValueError, match="caller-owned Session"):
            runtime_service.find_execution_replay(
                other_session, grant.owner, identity, first.reservation.request_hash
            )
        next_execution = start(session, registry, new_cycle, key="new-cycle")
    assert replay.is_replay and no_allowance_replay.is_replay
    assert replay.job_id == first.job_id
    assert replay.status.value == "failed"
    assert replay.reservation.paid_allowance_usage_id == first.reservation.paid_allowance_usage_id
    assert (
        next_execution.reservation.paid_allowance_usage_id
        != first.reservation.paid_allowance_usage_id
    )
    assert len(rows(factory, paid_allowance_usage_table)) == 2
    with (
        pytest.raises(PlatformError, match="different request"),
        transaction_boundary(factory) as session,
    ):
        start(session, registry, new_cycle, frontend_id="different_frontend")
    assert len(rows(factory, jobs_table)) == 2


def test_same_key_different_owners_and_allowance_ids_do_not_share_counters(runtime, monkeypatch):
    factory, _, registry = runtime
    first_grant = allowance()
    second_grant = allowance()
    original = ScenarioSessionRepository.get_by_idempotency_key

    def forbid_null(self, **kwargs):
        assert kwargs["guest_id"] is not None
        return original(self, **kwargs)

    monkeypatch.setattr(
        "anytoolai_platform_core.scenarios.repository.ScenarioSessionRepository.get_by_idempotency_key",
        forbid_null,
    )
    with transaction_boundary(factory) as session:
        first = start(session, registry, first_grant)
        second = start(session, registry, second_grant)
        guest = start(session, registry)
    assert len({first.job_id, second.job_id, guest.job_id}) == 3
    assert len(rows(factory, paid_allowance_usage_table)) == 2
    assert len(rows(factory, guest_quota_usage_table)) == 1
    assert rows(factory, guest_quota_usage_table)[0]["used_count"] == 0
    conflicting = replace(first_grant, owner=second_grant.owner)
    with (
        pytest.raises(PlatformError, match="binding cannot change"),
        transaction_boundary(factory) as session,
    ):
        start(session, registry, conflicting, key="other-owner")
    assert len(rows(factory, jobs_table)) == 3


@pytest.mark.parametrize(
    "change",
    [
        {"product_id": "other_product"},
        {"metric_key": "unknown.metric"},
        {"unit": "other_unit"},
        {
            "owner": ExecutionOwner(
                "other_tenant", "ru", ExecutionOwnerKind.portal_user, str(uuid4())
            )
        },
    ],
)
def test_invalid_first_binding_creates_no_execution_or_bucket(runtime, change):
    factory, _, registry = runtime
    grant = allowance()
    with pytest.raises(PlatformError), transaction_boundary(factory) as session:
        start(session, registry, grant, paid_allowance=replace(grant, **change))
    assert_empty_admission(factory)


@pytest.mark.parametrize(
    "field,value", [("quantity", 2), ("metric_key", "kernel_demo.other_runs"), ("unit", "other")]
)
def test_existing_allowance_tuple_is_immutable(runtime, field, value):
    factory, _, registry = runtime
    grant = allowance()
    with transaction_boundary(factory) as session:
        first = start(session, registry, grant)
    if field == "metric_key":
        product = registry.get_product("kernel_demo")
        registry = replace(
            registry,
            products={
                **registry.products,
                "kernel_demo": replace(
                    product,
                    usage_metrics=(
                        *product.usage_metrics,
                        UsageMetricDefinition(value, "run", False),
                    ),
                ),
            },
        )
    if field == "unit":
        product = registry.get_product("kernel_demo")
        registry = replace(
            registry,
            products={
                **registry.products,
                "kernel_demo": replace(
                    product, usage_metrics=(UsageMetricDefinition(METRIC, value, False),)
                ),
            },
        )
    before = rows(factory, paid_allowance_usage_table)
    with (
        pytest.raises(PlatformError, match="binding cannot change"),
        transaction_boundary(factory) as session,
    ):
        start(session, registry, replace(grant, **{field: value}), key="new-request")
    assert rows(factory, paid_allowance_usage_table) == before
    with transaction_boundary(factory) as session:
        replay = start(session, registry, replace(grant, **{field: value}))
    assert replay.is_replay and replay.job_id == first.job_id


@pytest.mark.parametrize("paid", [True, False])
def test_caller_denial_after_reservation_rolls_back_all_state(runtime, paid):
    factory, _, registry = runtime
    grant = allowance() if paid else None
    with (
        pytest.raises(RuntimeError, match="caller admission denied"),
        transaction_boundary(factory) as session,
    ):
        accepted = start(session, registry, grant)
        assert accepted.reservation is not None
        raise RuntimeError("caller admission denied")
    assert_empty_admission(factory)
    with transaction_boundary(factory) as session:
        assert not start(session, registry, grant).is_replay


@pytest.mark.parametrize("boundary", ["reservation", "counter"])
def test_fault_between_admission_writes_never_leaves_partial_state(runtime, monkeypatch, boundary):
    factory, _, registry = runtime
    repository, method = (
        (ExecutionReservationRepository, "create")
        if boundary == "reservation"
        else (PaidAllowanceUsageRepository, "reserve_if_available")
    )
    original = getattr(repository, method)

    def fail_after_write(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("injected write failure")

    monkeypatch.setattr(repository, method, fail_after_write)
    with (
        pytest.raises(RuntimeError, match="injected write failure"),
        transaction_boundary(factory) as session,
    ):
        start(session, registry, allowance())
    assert_empty_admission(factory)


def test_paid_identity_requires_explicit_owner_and_key(runtime):
    factory, _, registry = runtime
    grant = allowance()
    with pytest.raises(PlatformError) as error, transaction_boundary(factory) as session:
        start(session, registry, grant, key=None)
    assert error.value.code == "idempotency_key_required"
    with pytest.raises(PlatformError) as error, transaction_boundary(factory) as session:
        start(session, registry, guest_id=None, user_id=grant.owner.owner_id)
    assert error.value.code == "guest_identity_required"
    assert_empty_admission(factory)


def test_empty_guest_identity_retains_safe_validation_without_admission_rows(runtime):
    factory, app, _ = runtime
    response = asyncio.run(
        _request(
            app,
            "POST",
            f"/v1/products/kernel_demo/scenarios/{SCENARIO}/start",
            _start_payload(guest_id=""),
        )
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "guest_identity_required"
    assert_empty_admission(factory)


def test_legacy_guest_replay_does_not_synthesize_a_reservation(runtime):
    factory, _, registry = runtime
    request_hash = compute_idempotency_request_hash(
        tenant_id="anytoolai",
        region="ru",
        product_id="kernel_demo",
        scenario_id=SCENARIO,
        frontend_id="kernel_demo_ce",
        guest_id="guest_demo",
        user_id=None,
        input_payload=_start_payload()["input"],
    )
    with transaction_boundary(factory) as session:
        stored = ScenarioSessionRepository(session).create(
            ScenarioSessionRecord(
                tenant_id="anytoolai",
                region="ru",
                product_id="kernel_demo",
                scenario_id=SCENARIO,
                scenario_version=1,
                frontend_id="kernel_demo_ce",
                guest_id="guest_demo",
                idempotency_key="request",
                idempotency_request_hash=request_hash,
            )
        )
        job = JobRepository(session).create(
            JobRecord(
                tenant_id=stored.tenant_id,
                region=stored.region,
                product_id=stored.product_id,
                frontend_id=stored.frontend_id,
                scenario_session_id=stored.id,
                workflow_id="kernel_demo.single_action_extract_v1",
                workflow_version=1,
            )
        )
    with transaction_boundary(factory) as session:
        replay = start(session, registry)
    assert replay.is_replay and replay.job_id == job.id
    assert replay.reservation is None
    assert rows(factory, execution_reservations_table) == []
    assert rows(factory, guest_quota_usage_table) == []


def test_unmetered_null_guest_replay_preserves_its_existing_contract(runtime):
    factory, _, registry = runtime
    product = registry.get_product("kernel_demo")
    registry = replace(
        registry,
        products={**registry.products, "kernel_demo": replace(product, quota_policy_ref=None)},
    )
    with transaction_boundary(factory) as session:
        first = start(session, registry, guest_id=None, user_id="historical-untrusted-user")
    with transaction_boundary(factory) as session:
        replay = start(session, registry, guest_id=None, user_id="historical-untrusted-user")
    assert replay.is_replay and replay.job_id == first.job_id
    assert replay.reservation is None
    assert rows(factory, jobs_table)[0]["consumption_mode"] is JobConsumptionMode.unmetered
    assert len(rows(factory, jobs_table)) == 1
    assert rows(factory, execution_reservations_table) == []


def test_paid_handoff_replay_precedes_expiry_and_does_not_inherit_source_user_authority(runtime):
    factory, app, registry = runtime
    with transaction_boundary(factory) as session:
        source, artifact = _seed_source(session)
        session.execute(
            sa.update(scenario_sessions_table)
            .where(scenario_sessions_table.c.id == source)
            .values(user_id=str(uuid4()))
        )
    created = _create(app, source, artifact).json()
    grant = allowance()
    command = AcceptHandoffCommand("anytoolai", "ru")
    with transaction_boundary(factory) as session:
        accepted = handoff_service(session, registry).accept(
            created["handoff_token"], command, execution_owner=grant.owner, paid_allowance=grant
        )
    with transaction_boundary(factory) as session:
        session.execute(
            sa.update(product_handoffs_table)
            .where(product_handoffs_table.c.id == created["handoff_id"])
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    with transaction_boundary(factory) as session:
        replay = handoff_service(session, registry).accept(
            created["handoff_token"], command, execution_owner=grant.owner
        )
    assert replay.is_replay
    assert replay.preview.target_job_id == accepted.preview.target_job_id
    assert len(rows(factory, execution_reservations_table)) == 1
    reservation = rows(factory, execution_reservations_table)[0]
    assert reservation["replay_namespace"] == "handoff"
    assert reservation["replay_key"] == created["handoff_id"]
    assert reservation["owner_id"] == grant.owner.owner_id
    assert rows(factory, guest_quota_usage_table) == []
    with pytest.raises(HandoffSourceInvalidError), transaction_boundary(factory) as session:
        handoff_service(session, registry).accept(created["handoff_token"], command)


def test_busy_handoff_http_rolls_back_claim_and_can_retry_same_token(runtime):
    factory, app, registry = runtime
    policy = registry.get_quota_policy("kernel_demo.guest_quota_v1")
    registry = replace(
        registry, quotas={**registry.quotas, policy.quota_policy_id: replace(policy, limit_count=1)}
    )
    app.state.runtime = replace(app.state.runtime, config_registry=registry)
    with transaction_boundary(factory) as session:
        occupied = start(session, registry)
        source, artifact = _seed_source(session)
    created = _create(app, source, artifact).json()
    path = f"/v1/handoffs/{created['handoff_token']}/accept"
    busy = asyncio.run(_request(app, "POST", path, {}))
    assert busy.status_code == 429
    assert busy.json()["error"]["code"] == "quota_capacity_reserved"
    handoff = rows(factory, product_handoffs_table)[0]
    assert handoff["status"].value == "created"
    assert handoff["target_job_id"] is None and handoff["error_code"] is None
    audits = [e for e in rows(factory, event_log_table) if e["event_type"] == "quota.capacity_reserved"]
    assert len(audits) == 1
    assert audits[0]["handoff_id"] == created["handoff_id"]
    assert audits[0]["job_id"] and audits[0]["scenario_session_id"]
    assert audits[0]["properties"]["reserved_count"] == 1
    assert not audits[0]["properties"]["exhausted"]
    assert len(rows(factory, jobs_table)) == 2  # occupied target capacity and historical source
    assert not any(
        event["event_type"] == "handoff.failed" for event in rows(factory, event_log_table)
    )
    # Terminal release restores the same allowance; consent/token/guest remain unchanged.
    with transaction_boundary(factory) as session:
        session.execute(
            sa.update(jobs_table).where(jobs_table.c.id == occupied.job_id).values(status="failed")
        )
        assert release_execution(session, occupied.job_id).applied
    accepted = asyncio.run(_request(app, "POST", path, {}))
    assert accepted.status_code == 200
    replay = asyncio.run(_request(app, "POST", path, {}))
    assert replay.json() == accepted.json()
    assert len(rows(factory, execution_reservations_table)) == 2
    assert rows(factory, guest_quota_usage_table)[0]["reserved_count"] == 1
    assert all(
        row["consumption_mode"] is JobConsumptionMode.reserved
        for row in rows(factory, jobs_table)
        if row["scenario_session_id"] != source
    )


@pytest.mark.parametrize("paid", [True, False])
def test_deferred_handoff_reserves_nothing_and_replays_original_target(runtime, paid):
    factory, app, registry = runtime
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
    with transaction_boundary(factory) as session:
        source, artifact = _seed_source(session)
    created = _create(app, source, artifact).json()
    grant = allowance()
    kwargs = {"execution_owner": grant.owner} if paid else {}
    with transaction_boundary(factory) as session:
        accepted = handoff_service(session, registry).accept(
            created["handoff_token"], AcceptHandoffCommand("anytoolai", "ru"), **kwargs
        )
    with transaction_boundary(factory) as session:
        replay = handoff_service(session, registry).accept(
            created["handoff_token"], AcceptHandoffCommand("anytoolai", "ru"), **kwargs
        )
    assert replay.is_replay and replay.preview == accepted.preview
    assert accepted.preview.target_job_id is None
    assert len(rows(factory, jobs_table)) == 1
    assert rows(factory, execution_reservations_table) == []
    assert rows(factory, guest_quota_usage_table) == []
    assert rows(factory, paid_allowance_usage_table) == []


def test_paid_final_exhaustion_preserves_critical_handoff_failure_and_audit(runtime):
    factory, app, registry = runtime
    with transaction_boundary(factory) as session:
        source, artifact = _seed_source(session)
    created = _create(app, source, artifact).json()
    grant = allowance(quantity=0)
    with (
        pytest.raises(HandoffAcceptanceExecutionError) as error,
        transaction_boundary(factory) as session,
    ):
        handoff_service(session, registry).accept(
            created["handoff_token"],
            AcceptHandoffCommand("anytoolai", "ru"),
            execution_owner=grant.owner,
            paid_allowance=grant,
        )
    assert error.value.error_code == "quota_exhausted"
    handoff = rows(factory, product_handoffs_table)[0]
    assert handoff["status"].value == "failed"
    assert handoff["target_job_id"] is None
    assert handoff["error_code"] == "quota_exhausted"
    events = [
        event
        for event in rows(factory, event_log_table)
        if event["handoff_id"] == created["handoff_id"]
    ]
    assert [event["event_type"] for event in events].count("quota.checked") == 1
    assert [event["event_type"] for event in events].count("quota.exhausted") == 1
    assert [event["event_type"] for event in events].count("handoff.failed") == 1
    assert len(rows(factory, jobs_table)) == 1
    assert rows(factory, execution_reservations_table) == []
    assert rows(factory, paid_allowance_usage_table)[0]["reserved_count"] == 0


@pytest.mark.parametrize("competitor", ["decline", "expire"])
def test_accept_competing_with_decline_or_expiry_has_one_consistent_winner(runtime, competitor):
    factory, app, registry = runtime
    with transaction_boundary(factory) as session:
        source, artifact = _seed_source(session)
    created = _create(app, source, artifact).json()
    with transaction_boundary(factory) as session:
        handoff = HandoffRepository(session).get_by_id(
            created["handoff_id"], tenant_id="anytoolai", region="ru"
        )
    barrier = threading.Barrier(2)
    before_expiry = handoff.expires_at - timedelta(seconds=1)

    def accept():
        barrier.wait(timeout=15)
        try:
            with transaction_boundary(factory) as session:
                return handoff_service(session, registry, clock=lambda: before_expiry).accept(
                    created["handoff_token"], AcceptHandoffCommand("anytoolai", "ru")
                )
        except (HandoffExpiredError, HandoffNotActionableError) as exc:
            return exc.code

    def compete():
        barrier.wait(timeout=15)
        with transaction_boundary(factory) as session:
            service = handoff_service(session, registry, clock=lambda: before_expiry)
            if competitor == "expire":
                return service.expire(handoff, now=handoff.expires_at + timedelta(seconds=1))
            try:
                return service.decline(created["handoff_token"], tenant_id="anytoolai", region="ru")
            except HandoffNotActionableError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        accepting, competing = pool.submit(accept), pool.submit(compete)
        outcome = accepting.result(timeout=20)
        competing.result(timeout=20)
    stored = rows(factory, product_handoffs_table)[0]
    reservations = rows(factory, execution_reservations_table)
    if isinstance(outcome, str):
        assert stored["status"].value == ("declined" if competitor == "decline" else "expired")
        assert reservations == []
        assert len(rows(factory, jobs_table)) == 1
    else:
        assert stored["status"].value == "consumed"
        assert len(reservations) == 1
        assert reservations[0]["job_id"] == outcome.preview.target_job_id
        assert rows(factory, guest_quota_usage_table)[0]["reserved_count"] == 1
