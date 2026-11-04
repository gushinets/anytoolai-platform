from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime
from http import HTTPStatus

import pytest
import sqlalchemy as sa
from anytoolai_platform_core.quotas.finalization import finalize_success, release_execution
from anytoolai_platform_core.quotas.models import ExecutionOwner, ExecutionOwnerKind
from anytoolai_platform_core.quotas.readback import read_consumption
from anytoolai_platform_core.storage.db import event_log_table, guest_quota_usage_table, jobs_table
from anytoolai_platform_core.storage.transactions import transaction_boundary
from test_execution_admission_postgresql import allowance, rows, start
from test_execution_admission_postgresql import runtime as runtime_fixture
from test_execution_finalization_postgresql import candidate
from test_identity_quota_api import _request

pytestmark = [pytest.mark.postgresql, pytest.mark.slow]
runtime = runtime_fixture
GUEST = ExecutionOwner("anytoolai", "ru", ExecutionOwnerKind.guest, "guest_demo")


def quota(runtime):
    response = asyncio.run(
        _request(runtime[1], "GET", "/v1/products/kernel_demo/quota?guest_id=guest_demo")
    )
    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert datetime.fromisoformat(payload["read_at"]).tzinfo is not None
    assert set(payload) == {
        "guest_id",
        "product_id",
        "quota_policy_id",
        "quota_dimension",
        "dimension_key",
        "scenario_id",
        "unit",
        "period",
        "limit_count",
        "used_count",
        "successful_used_count",
        "legacy_used_count",
        "reserved_count",
        "available_count",
        "remaining_count",
        "exhausted",
        "resets_at",
        "read_at",
    }
    return payload


def fail(factory, acceptance):
    with transaction_boundary(factory) as session:
        session.execute(
            sa.update(jobs_table)
            .where(jobs_table.c.id == acceptance.job_id)
            .values(status="failed")
        )
        assert release_execution(session, acceptance.job_id).applied
        assert not release_execution(session, acceptance.job_id).applied


def test_guest_http_refresh_after_reserve_success_release_preserves_legacy(runtime):
    factory, _, registry = runtime
    initial = quota(runtime)
    assert (initial["used_count"], initial["reserved_count"], initial["available_count"]) == (
        0,
        0,
        3,
    )
    assert rows(factory, guest_quota_usage_table) == []
    with transaction_boundary(factory) as session:
        first = start(session, registry)
    busy = quota(runtime)
    assert (
        busy["used_count"],
        busy["reserved_count"],
        busy["remaining_count"],
        busy["available_count"],
    ) == (0, 1, 3, 2)
    fail(factory, first)
    with transaction_boundary(factory) as session:
        session.execute(
            sa.update(guest_quota_usage_table).values(used_count=2, legacy_used_count=2)
        )
        second = start(session, registry, key="success")
    busy = quota(runtime)
    assert not busy["exhausted"]
    assert (
        busy["used_count"],
        busy["legacy_used_count"],
        busy["successful_used_count"],
        busy["reserved_count"],
        busy["available_count"],
    ) == (2, 2, 0, 1, 0)
    final = candidate(runtime, second)
    with transaction_boundary(factory) as session:
        assert finalize_success(session, second.job_id, final, config_registry=registry).applied
        assert not finalize_success(session, second.job_id, final, config_registry=registry).applied
        assert not release_execution(session, second.job_id).applied
    exhausted = quota(runtime)
    assert (
        exhausted["used_count"],
        exhausted["legacy_used_count"],
        exhausted["successful_used_count"],
        exhausted["reserved_count"],
        exhausted["remaining_count"],
        exhausted["available_count"],
        exhausted["exhausted"],
    ) == (3, 2, 1, 0, 0, 0, True)
    events = [
        e
        for e in rows(factory, event_log_table)
        if e["event_type"] in {"quota.reserved", "quota.consumed", "quota.released"}
    ]
    assert sorted(e["event_type"] for e in events) == [
        "quota.consumed",
        "quota.released",
        "quota.reserved",
        "quota.reserved",
    ]
    for event in events:
        assert (event["tenant_id"], event["region"], event["guest_id"]) == (
            "anytoolai",
            "ru",
            "guest_demo",
        )
        assert event["job_id"] and event["scenario_session_id"] and event["frontend_id"]
        assert event["properties"]["owner_kind"] == "guest"
        assert (
            event["properties"]["guest_quota_usage_id"] == second.reservation.guest_quota_usage_id
        )
        assert event["properties"]["scenario_id"]
    consumed = next(e for e in events if e["event_type"] == "quota.consumed")
    assert consumed["artifact_id"] == final.artifact.id
    assert consumed["properties"]["successful_used_count"] == 1


@pytest.mark.parametrize("paid", [True, False])
def test_readback_is_one_owned_query_unknown_is_unobserved_and_errors_propagate(
    runtime, paid, monkeypatch
):
    factory, _, registry = runtime
    grant = allowance() if paid else None
    with transaction_boundary(factory) as session:
        accepted = start(session, registry, grant)
    owner = GUEST if grant is None else grant.owner
    bucket_id = (
        accepted.reservation.paid_allowance_usage_id
        if paid
        else accepted.reservation.guest_quota_usage_id
    )
    with transaction_boundary(factory) as session:
        original = session.execute
        queries = []

        def execute(statement, *args, **kwargs):
            queries.append(statement)
            return original(statement, *args, **kwargs)

        monkeypatch.setattr(session, "execute", execute)
        state = read_consumption(session, owner, bucket_id)
        assert len(queries) == 1
        assert state.read_at.tzinfo is not None
        assert state.used == state.legacy_used == state.successful_used == 0
        assert state.reserved == 1 and state.remaining == state.quantity
        assert state.available == state.quantity - 1
        assert read_consumption(session, replace(owner, region="foreign"), bucket_id) is None
        foreign = replace(owner, owner_id=allowance().owner.owner_id if paid else "foreign")
        assert read_consumption(session, foreign, bucket_id) is None
        assert read_consumption(session, owner, "unknown") is None

        def unavailable(*args, **kwargs):
            raise sa.exc.OperationalError("readback", {}, RuntimeError("unavailable"))

        monkeypatch.setattr(session, "execute", unavailable)
        with pytest.raises(sa.exc.OperationalError):
            read_consumption(session, owner, bucket_id)


def test_paid_readback_and_events_remain_bound_to_original_allowance(runtime):
    factory, _, registry = runtime
    grant = allowance()
    with transaction_boundary(factory) as session:
        first = start(session, registry, grant)
    final = candidate(runtime, first)
    with transaction_boundary(factory) as session:
        finalize_success(session, first.job_id, final, config_registry=registry)
        new_grant = replace(grant, allowance_id=allowance().allowance_id)
        second = start(session, registry, new_grant, key="new-cycle")
        replay = start(session, registry, new_grant)
        assert replay.is_replay and replay.reservation.id == first.reservation.id
        old = read_consumption(session, grant.owner, first.reservation.paid_allowance_usage_id)
        new = read_consumption(session, grant.owner, second.reservation.paid_allowance_usage_id)
        assert (old.used, old.reserved, old.available, old.legacy_used) == (1, 0, 0, 0)
        assert (new.used, new.reserved, new.remaining) == (0, 1, 1)
        assert old.bucket.allowance.allowance_id == grant.allowance_id
        assert new.bucket.allowance.allowance_id == new_grant.allowance_id
    consumed = [e for e in rows(factory, event_log_table) if e["event_type"] == "quota.consumed"]
    assert len(consumed) == 1
    assert consumed[0]["user_id"] == grant.owner.owner_id and consumed[0]["guest_id"] is None
    assert consumed[0]["properties"]["allowance_id"] == grant.allowance_id
    assert consumed[0]["properties"]["metric_key"] == grant.metric_key
    assert consumed[0]["properties"]["owner_kind"] == "portal_user"
