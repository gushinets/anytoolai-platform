from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Iterator

import httpx
import pytest
import sqlalchemy as sa
from anytoolai_platform_api.routers.handoffs import _service as _handoff_service
from anytoolai_platform_core.handoffs import service as handoff_service_module
from anytoolai_platform_core.handoffs.models import AcceptHandoffCommand
from anytoolai_platform_core.handoffs.repository import HandoffRepository
from anytoolai_platform_core.handoffs.service import HandoffAcceptanceExecutionError
from anytoolai_platform_core.quotas.models import QuotaDimension, QuotaPolicy
from anytoolai_platform_core.storage.db import (
    event_log_table,
    guest_quota_usage_table,
    jobs_table,
    product_handoffs_table,
    scenario_sessions_table,
)
from anytoolai_platform_core.storage.transactions import (
    SessionFactory,
    build_session_factory,
    transaction_boundary,
)
from tests.db_support import provision_database
from test_handoffs_api import _create as _create_handoff
from test_handoffs_api import _seed_source as _seed_handoff_source
from test_scenario_runtime_api import (
    _create_test_app,
    _start_payload,
)

TEST_GUEST_QUOTA_LIMIT = 3


@contextmanager
def _provision_api_app(
    database_name_prefix: str,
) -> Iterator[tuple[SessionFactory, object]]:
    with provision_database(
        database_name_prefix=database_name_prefix,
        skip_reason="PostgreSQL quota concurrency coverage",
    ) as (engine, _alembic_config, _database_url):
        session_factory = build_session_factory(engine)
        yield session_factory, _create_test_app(session_factory)


@pytest.mark.postgresql
@pytest.mark.slow
def test_postgresql_parallel_scenario_starts_consume_quota_exactly_once() -> None:
    """Production-semantics quota check for PostgreSQL row locks and conditional updates.

    Set ANYTOOLAI_POSTGRES_TEST_DATABASE_URL to a PostgreSQL maintenance database URL. The test
    creates and drops its own disposable database, then runs the real Alembic migration chain.
    """
    with _provision_api_app("anytoolai_a13_quota_test") as (session_factory, app):
        quota_limit = _scenario_start_quota_limit(app)
        request_count = max(quota_limit + 5, 8)

        async def start_many() -> list[httpx.Response]:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await asyncio.gather(
                    *[
                        client.post(
                            "/v1/products/kernel_demo/scenarios/"
                            "kernel_demo.single_action_smoke_v1/start",
                            json=_start_payload(),
                            headers={"X-Request-ID": f"req_pg_quota_parallel_{index}"},
                        )
                        for index in range(request_count)
                    ]
                )

        responses = asyncio.run(start_many())
        status_codes = [response.status_code for response in responses]

        assert status_codes.count(HTTPStatus.OK) == quota_limit
        assert (
            status_codes.count(HTTPStatus.TOO_MANY_REQUESTS)
            == request_count - quota_limit
        )
        assert all(
            response.json()["error"]["code"] == "quota_exhausted"
            for response in responses
            if response.status_code == HTTPStatus.TOO_MANY_REQUESTS
        )

        with transaction_boundary(session_factory) as session:
            scenario_count = session.execute(
                sa.select(sa.func.count()).select_from(scenario_sessions_table)
            ).scalar_one()
            job_count = session.execute(
                sa.select(sa.func.count()).select_from(jobs_table)
            ).scalar_one()
            usages = list(session.execute(sa.select(guest_quota_usage_table)).mappings())
            event_types = list(session.execute(sa.select(event_log_table.c.event_type)).scalars())

        assert scenario_count == quota_limit
        assert job_count == quota_limit
        assert len(usages) == 1
        usage = usages[0]
        assert usage["used_count"] == quota_limit
        assert usage["limit_count"] == quota_limit
        assert usage["quota_dimension"] == "product"
        assert usage["dimension_key"] == "kernel_demo"
        assert event_types.count("quota.consumed") == quota_limit
        assert event_types.count("quota.exhausted") == request_count - quota_limit


@pytest.mark.postgresql
@pytest.mark.slow
def test_postgresql_concurrent_duplicate_submit_with_idempotency_key_consumes_quota_once() -> None:
    """ANY-150: N concurrent /start requests sharing one Idempotency-Key (differing
    only by X-Request-ID) must consume exactly one quota unit and create exactly one
    session/job.

    This is the core correctness claim behind putting the atomic insert-or-select
    before quota consumption in ScenarioRuntimeService.start_session: only the request
    that actually wins the DB-level unique-constraint race may consume quota, so no
    concurrent duplicate can be double-charged (or, symmetrically, none can be
    incorrectly quota_exhausted for what is really the same logical request as one
    that already succeeded). Deliberately run against PostgreSQL, not SQLite, and
    through the real HTTP router: an equivalent test driven directly against the ASGI
    app on this repo's SQLite harness reliably hits `sqlite3.OperationalError:
    database is locked`, because concurrent begin_nested()/SAVEPOINT writers racing
    across the two ATTACHed database files is a genuine SQLite limitation, not a code
    defect -- see docs/architecture/runtime-storage.md's "SQLite-based verification"
    compromise, which already documents that production-safe concurrency needs this
    PostgreSQL integration path rather than the fast SQLite suite.
    """
    with _provision_api_app("anytoolai_a150_idem_concurrent") as (
        session_factory,
        app,
    ):
        request_count = 8

        async def start_parallel_requests() -> list[httpx.Response]:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await asyncio.gather(
                    *[
                        client.post(
                            "/v1/products/kernel_demo/scenarios/"
                            "kernel_demo.single_action_smoke_v1/start",
                            json=_start_payload(),
                            headers={
                                "X-Request-ID": f"req_pg_idem_parallel_{index}",
                                "Idempotency-Key": "idem-pg-parallel-same-key",
                            },
                        )
                        for index in range(request_count)
                    ]
                )

        responses = asyncio.run(start_parallel_requests())

        assert all(response.status_code == HTTPStatus.OK for response in responses)
        bodies = [response.json() for response in responses]
        assert all(body == bodies[0] for body in bodies)

        with transaction_boundary(session_factory) as session:
            scenario_count = session.execute(
                sa.select(sa.func.count()).select_from(scenario_sessions_table)
            ).scalar_one()
            job_count = session.execute(
                sa.select(sa.func.count()).select_from(jobs_table)
            ).scalar_one()
            usage = session.execute(sa.select(guest_quota_usage_table)).mappings().one()
            started_count = session.execute(
                sa.select(sa.func.count())
                .select_from(event_log_table)
                .where(event_log_table.c.event_type == "scenario.started")
            ).scalar_one()
            consumed_count = session.execute(
                sa.select(sa.func.count())
                .select_from(event_log_table)
                .where(event_log_table.c.event_type == "quota.consumed")
            ).scalar_one()

        assert scenario_count == 1
        assert job_count == 1
        assert usage["used_count"] == 1
        assert started_count == 1
        assert consumed_count == 1


@pytest.mark.postgresql
@pytest.mark.slow
def test_postgresql_parallel_starts_consume_scenario_dimension_quota_with_independent_counters() -> (
    None
):
    with _provision_api_app("anytoolai_a13_scenario_quota_test") as (session_factory, app):
        scenario_quota_limit = _force_scenario_guest_quota(app)
        scenario_ids = [
            "kernel_demo.single_action_smoke_v1",
            "kernel_demo.multi_step_workflow_smoke_v1",
        ]
        assert len(set(scenario_ids)) == 2
        requests_per_scenario = max(scenario_quota_limit + 5, 8)
        requests: list[tuple[str, int]] = [
            (scenario_id, index)
            for scenario_id in scenario_ids
            for index in range(requests_per_scenario)
        ]

        async def start_many() -> list[tuple[str, httpx.Response]]:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                responses = await asyncio.gather(
                    *[
                        client.post(
                            f"/v1/products/kernel_demo/scenarios/{scenario_id}/start",
                            json=_start_payload(),
                            headers={
                                "X-Request-ID": (
                                    f"req_pg_quota_indep_{scenario_id}_{index}"
                                )
                            },
                        )
                        for scenario_id, index in requests
                    ]
                )
            return [
                (scenario_id, response)
                for (scenario_id, _index), response in zip(requests, responses, strict=True)
            ]

        scenario_responses = asyncio.run(start_many())
        expected_ok = scenario_quota_limit * len(scenario_ids)
        expected_rejected = (
            requests_per_scenario - scenario_quota_limit
        ) * len(scenario_ids)
        status_codes = [
            response.status_code for _scenario_id, response in scenario_responses
        ]

        assert status_codes.count(HTTPStatus.OK) == expected_ok
        assert status_codes.count(HTTPStatus.TOO_MANY_REQUESTS) == expected_rejected
        assert all(
            status_code in {HTTPStatus.OK, HTTPStatus.TOO_MANY_REQUESTS}
            for status_code in status_codes
        )
        assert all(
            response.json()["error"]["code"] == "quota_exhausted"
            for _scenario_id, response in scenario_responses
            if response.status_code == HTTPStatus.TOO_MANY_REQUESTS
        )

        for scenario_id in scenario_ids:
            scenario_status_codes = [
                response.status_code
                for response_scenario_id, response in scenario_responses
                if response_scenario_id == scenario_id
            ]
            assert scenario_status_codes.count(HTTPStatus.OK) == scenario_quota_limit
            assert (
                scenario_status_codes.count(HTTPStatus.TOO_MANY_REQUESTS)
                == requests_per_scenario - scenario_quota_limit
            )

        with transaction_boundary(session_factory) as session:
            scenario_count = session.execute(
                sa.select(sa.func.count()).select_from(scenario_sessions_table)
            ).scalar_one()
            job_count = session.execute(
                sa.select(sa.func.count()).select_from(jobs_table)
            ).scalar_one()
            usages = list(
                session.execute(
                    sa.select(guest_quota_usage_table).order_by(
                        guest_quota_usage_table.c.scenario_id
                    )
                ).mappings()
            )
            event_types = list(session.execute(sa.select(event_log_table.c.event_type)).scalars())

        assert scenario_count == expected_ok
        assert job_count == expected_ok
        assert len(usages) == len(scenario_ids)
        usage_by_scenario = {row["scenario_id"]: row for row in usages}
        assert set(usage_by_scenario) == set(scenario_ids)
        for scenario_id in scenario_ids:
            usage = usage_by_scenario[scenario_id]
            assert usage["quota_dimension"] == "scenario"
            assert usage["dimension_key"] == scenario_id
            assert usage["scenario_id"] == scenario_id
            assert usage["used_count"] == scenario_quota_limit
            assert usage["limit_count"] == scenario_quota_limit
        assert event_types.count("quota.consumed") == expected_ok
        assert event_types.count("quota.exhausted") == expected_rejected


@pytest.mark.postgresql
@pytest.mark.slow
def test_postgresql_parallel_handoff_accept_creates_one_target() -> None:
    with _provision_api_app("anytoolai_a17_handoff_test") as (session_factory, app):
        with transaction_boundary(session_factory) as session:
            source_session_id, artifact_id = _seed_handoff_source(session)
        created = _create_handoff(app, source_session_id, artifact_id).json()

        async def accept_twice() -> list[httpx.Response]:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                path = f"/v1/handoffs/{created['handoff_token']}/accept"
                return await asyncio.gather(
                    client.post(path, json={}, headers={"X-Request-ID": "req_pg_handoff_1"}),
                    client.post(path, json={}, headers={"X-Request-ID": "req_pg_handoff_2"}),
                )

        responses = asyncio.run(accept_twice())
        assert sorted(response.status_code for response in responses) == [200, 409]
        with transaction_boundary(session_factory) as session:
            handoff = (
                session.execute(
                    sa.select(product_handoffs_table).where(
                        product_handoffs_table.c.id == created["handoff_id"]
                    )
                )
                .mappings()
                .one()
            )
            target_session_count = session.execute(
                sa.select(sa.func.count())
                .select_from(scenario_sessions_table)
                .where(scenario_sessions_table.c.parent_scenario_session_id == source_session_id)
            ).scalar_one()
            target_job_count = session.execute(
                sa.select(sa.func.count())
                .select_from(jobs_table)
                .where(jobs_table.c.scenario_session_id == handoff["target_scenario_session_id"])
            ).scalar_one()
            accepted_events = session.execute(
                sa.select(sa.func.count())
                .select_from(event_log_table)
                .where(
                    event_log_table.c.event_type == "handoff.accepted",
                    event_log_table.c.handoff_id == created["handoff_id"],
                )
            ).scalar_one()
        assert handoff["status"] == "consumed"
        assert target_session_count == 1
        assert target_job_count == 1
        assert accepted_events == 1


@pytest.mark.postgresql
@pytest.mark.slow
def test_postgresql_parallel_exhausted_handoff_accept_recovers_quota_once() -> None:
    with _provision_api_app("anytoolai_a17_handoff_exhausted_test") as (session_factory, app):
        _force_zero_guest_quota(app)
        with transaction_boundary(session_factory) as session:
            source_session_id, artifact_id = _seed_handoff_source(session)
        created = _create_handoff(app, source_session_id, artifact_id).json()
        request_count = 8

        async def accept_many() -> list[httpx.Response]:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                path = f"/v1/handoffs/{created['handoff_token']}/accept"
                return await asyncio.gather(
                    *[
                        client.post(
                            path,
                            json={},
                            headers={"X-Request-ID": f"req_pg_handoff_exhausted_{index}"},
                        )
                        for index in range(request_count)
                    ]
                )

        responses = asyncio.run(accept_many())
        assert any(
            response.status_code == HTTPStatus.TOO_MANY_REQUESTS
            and response.json()["error"]["code"] == "quota_exhausted"
            for response in responses
        )
        assert all(
            response.status_code in {HTTPStatus.CONFLICT, HTTPStatus.TOO_MANY_REQUESTS}
            for response in responses
        )

        with transaction_boundary(session_factory) as session:
            handoff = (
                session.execute(
                    sa.select(product_handoffs_table).where(
                        product_handoffs_table.c.id == created["handoff_id"]
                    )
                )
                .mappings()
                .one()
            )
            quota_event_types = list(
                session.execute(
                    sa.select(event_log_table.c.event_type).where(
                        event_log_table.c.handoff_id == created["handoff_id"],
                        event_log_table.c.event_type.in_(["quota.checked", "quota.exhausted"]),
                    )
                ).scalars()
            )
            handoff_failed_count = session.execute(
                sa.select(sa.func.count())
                .select_from(event_log_table)
                .where(
                    event_log_table.c.handoff_id == created["handoff_id"],
                    event_log_table.c.event_type == "handoff.failed",
                )
            ).scalar_one()
            target_session_count = session.execute(
                sa.select(sa.func.count())
                .select_from(scenario_sessions_table)
                .where(scenario_sessions_table.c.parent_scenario_session_id == source_session_id)
            ).scalar_one()
            usage = session.execute(sa.select(guest_quota_usage_table)).mappings().one()

        assert handoff["status"] == "failed"
        assert handoff["error_code"] == "quota_exhausted"
        assert quota_event_types.count("quota.checked") == 1
        assert quota_event_types.count("quota.exhausted") == 1
        assert handoff_failed_count == 1
        assert target_session_count == 0
        assert usage["limit_count"] == 0
        assert usage["used_count"] == 0


@pytest.mark.postgresql
@pytest.mark.slow
def test_quota_exhausted_accept_racing_with_decline_preserves_exactly_once_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _provision_api_app("anytoolai_a17_handoff_decline_race") as (
        session_factory,
        app,
    ):
        _force_zero_guest_quota(app)
        with transaction_boundary(session_factory) as session:
            source_session_id, artifact_id = _seed_handoff_source(session)
        created = _create_handoff(app, source_session_id, artifact_id).json()

        release_recovery = threading.Event()
        recovery_ready = threading.Event()
        decline_waiting_for_lock = threading.Event()
        _pause_handoff_quota_recovery(
            monkeypatch,
            recovery_ready=recovery_ready,
            release_recovery=release_recovery,
        )
        _observe_handoff_lock_attempt(
            monkeypatch,
            thread_name_prefix="decline-race",
            observed=decline_waiting_for_lock,
        )

        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="handoff-race") as executor:
            accept_future = executor.submit(
                _accept_handoff_response,
                app,
                created["handoff_token"],
                "req_pg_handoff_decline_race_accept",
            )
            assert recovery_ready.wait(10)
            decline_future = executor.submit(
                _run_named,
                "decline-race",
                _decline_handoff_response,
                app,
                created["handoff_token"],
                "req_pg_handoff_decline_race_decline",
            )
            assert decline_waiting_for_lock.wait(10)
            release_recovery.set()
            accepted = accept_future.result(timeout=10)
            declined = decline_future.result(timeout=10)

        assert accepted.status_code == HTTPStatus.TOO_MANY_REQUESTS
        assert accepted.json()["error"]["code"] == "quota_exhausted"
        assert declined.status_code == HTTPStatus.CONFLICT
        assert declined.json()["error"]["code"] == "handoff_failed"
        _assert_quota_exhausted_handoff_recovery_state(
            session_factory,
            handoff_id=created["handoff_id"],
            source_session_id=source_session_id,
            expected_handoff_status="failed",
        )


@pytest.mark.postgresql
@pytest.mark.slow
def test_quota_exhausted_accept_racing_with_expiry_preserves_exactly_once_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _provision_api_app("anytoolai_a17_handoff_expiry_race") as (
        session_factory,
        app,
    ):
        _force_zero_guest_quota(app)
        with transaction_boundary(session_factory) as session:
            source_session_id, artifact_id = _seed_handoff_source(session)
        created = _create_handoff(app, source_session_id, artifact_id).json()

        release_recovery = threading.Event()
        recovery_ready = threading.Event()
        expiry_waiting_for_lock = threading.Event()
        _pause_handoff_quota_recovery(
            monkeypatch,
            recovery_ready=recovery_ready,
            release_recovery=release_recovery,
        )
        _observe_handoff_lock_attempt(
            monkeypatch,
            thread_name_prefix="expiry-race",
            observed=expiry_waiting_for_lock,
        )

        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="handoff-race") as executor:
            accept_future = executor.submit(
                _accept_handoff_response,
                app,
                created["handoff_token"],
                "req_pg_handoff_expiry_race_accept",
            )
            assert recovery_ready.wait(10)
            expiry_future = executor.submit(
                _run_named,
                "expiry-race",
                _expired_preview,
                session_factory,
                app,
                created["handoff_token"],
                created["expires_at"],
            )
            assert expiry_waiting_for_lock.wait(10)
            release_recovery.set()
            accepted = accept_future.result(timeout=10)
            expired_preview = expiry_future.result(timeout=10)

        assert accepted.status_code == HTTPStatus.TOO_MANY_REQUESTS
        assert accepted.json()["error"]["code"] == "quota_exhausted"
        assert expired_preview.status.value == "expired"
        _assert_quota_exhausted_handoff_recovery_state(
            session_factory,
            handoff_id=created["handoff_id"],
            source_session_id=source_session_id,
            expected_handoff_status="failed",
        )


@pytest.mark.postgresql
@pytest.mark.slow
def test_parallel_quota_exhausted_accept_recovery_is_idempotent() -> None:
    with _provision_api_app("anytoolai_a17_handoff_parallel_quota") as (
        session_factory,
        app,
    ):
        _force_zero_guest_quota(app)
        with transaction_boundary(session_factory) as session:
            source_session_id, artifact_id = _seed_handoff_source(session)
        created = _create_handoff(app, source_session_id, artifact_id).json()
        request_count = 8

        async def accept_many() -> list[httpx.Response]:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                path = f"/v1/handoffs/{created['handoff_token']}/accept"
                return await asyncio.gather(
                    *[
                        client.post(
                            path,
                            json={},
                            headers={
                                "X-Request-ID": f"req_pg_handoff_parallel_quota_{index}"
                            },
                        )
                        for index in range(request_count)
                    ]
                )

        responses = asyncio.run(accept_many())
        assert any(
            response.status_code == HTTPStatus.TOO_MANY_REQUESTS
            and response.json()["error"]["code"] == "quota_exhausted"
            for response in responses
        )
        assert all(
            response.status_code in {HTTPStatus.CONFLICT, HTTPStatus.TOO_MANY_REQUESTS}
            for response in responses
        )
        _assert_quota_exhausted_handoff_recovery_state(
            session_factory,
            handoff_id=created["handoff_id"],
            source_session_id=source_session_id,
            expected_handoff_status="failed",
        )


@pytest.mark.postgresql
@pytest.mark.slow
def test_handoff_quota_recovery_failure_does_not_return_quota_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _provision_api_app("anytoolai_a17_handoff_critical_recovery") as (
        session_factory,
        app,
    ):
        _force_zero_guest_quota(app)
        with transaction_boundary(session_factory) as session:
            source_session_id, artifact_id = _seed_handoff_source(session)
        created = _create_handoff(app, source_session_id, artifact_id).json()

        def fail_recovery(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
            raise RuntimeError("forced quota recovery failure")

        monkeypatch.setattr(
            HandoffRepository,
            "finalize_quota_failure_recovery",
            fail_recovery,
        )

        response = asyncio.run(
            _request_with_exception_response(
                app,
                "POST",
                f"/v1/handoffs/{created['handoff_token']}/accept",
                {},
            )
        )

        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert response.json()["error"]["code"] == "internal_server_error"

        with transaction_boundary(session_factory) as session:
            handoff = (
                session.execute(
                    sa.select(product_handoffs_table).where(
                        product_handoffs_table.c.id == created["handoff_id"]
                    )
                )
                .mappings()
                .one()
            )
            quota_event_count = session.execute(
                sa.select(sa.func.count())
                .select_from(event_log_table)
                .where(
                    event_log_table.c.handoff_id == created["handoff_id"],
                    event_log_table.c.event_type.in_(["quota.checked", "quota.exhausted"]),
                )
            ).scalar_one()
            target_session_count = session.execute(
                sa.select(sa.func.count())
                .select_from(scenario_sessions_table)
                .where(scenario_sessions_table.c.parent_scenario_session_id == source_session_id)
            ).scalar_one()

        assert handoff["status"] in {"created", "viewed"}
        assert quota_event_count == 0
        assert target_session_count == 0


@pytest.mark.postgresql
@pytest.mark.slow
def test_postgresql_quota_recovery_finalizes_without_router_transaction() -> None:
    with _provision_api_app("anytoolai_a17_handoff_reservation_test") as (session_factory, app):
        _force_zero_guest_quota(app)
        with transaction_boundary(session_factory) as session:
            source_session_id, artifact_id = _seed_handoff_source(session)
        created = _create_handoff(app, source_session_id, artifact_id).json()

        with (
            pytest.raises(HandoffAcceptanceExecutionError) as acceptance_error,
            transaction_boundary(session_factory) as session,
        ):
            _handoff_service(
                session,
                app.state.runtime.config_registry,
            ).accept(
                created["handoff_token"],
                AcceptHandoffCommand(
                    tenant_id="anytoolai",
                    region="default",
                ),
            )
        assert acceptance_error.value.error_code == "quota_exhausted"

        with transaction_boundary(session_factory) as session:
            handoff = (
                session.execute(
                    sa.select(product_handoffs_table).where(
                        product_handoffs_table.c.id == created["handoff_id"]
                    )
                )
                .mappings()
                .one()
            )
            event_types = list(
                session.execute(
                    sa.select(event_log_table.c.event_type).where(
                        event_log_table.c.handoff_id == created["handoff_id"]
                    )
                ).scalars()
            )

        assert handoff["status"] == "failed"
        assert handoff["error_code"] == "quota_exhausted"
        assert event_types.count("handoff.failed") == 1
        assert event_types.count("quota.checked") == 1
        assert event_types.count("quota.exhausted") == 1

        with transaction_boundary(session_factory) as session:
            repeated = _handoff_service(
                session,
                app.state.runtime.config_registry,
            ).mark_failed(
                created["handoff_id"],
                tenant_id="anytoolai",
                region="default",
                error_code="quota_exhausted",
            )
            handoff_failed_count = session.execute(
                sa.select(sa.func.count())
                .select_from(event_log_table)
                .where(
                    event_log_table.c.handoff_id == created["handoff_id"],
                    event_log_table.c.event_type == "handoff.failed",
                )
            ).scalar_one()

        assert repeated.status.value == "failed"
        assert handoff_failed_count == 1


def _pause_handoff_quota_recovery(
    monkeypatch: pytest.MonkeyPatch,
    *,
    recovery_ready: threading.Event,
    release_recovery: threading.Event,
) -> None:
    original_finalize = HandoffRepository.finalize_quota_failure_recovery

    def paused_finalize(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        recovery_ready.set()
        assert release_recovery.wait(10)
        return original_finalize(self, *args, **kwargs)

    monkeypatch.setattr(
        HandoffRepository,
        "finalize_quota_failure_recovery",
        paused_finalize,
    )


def _observe_handoff_lock_attempt(
    monkeypatch: pytest.MonkeyPatch,
    *,
    thread_name_prefix: str,
    observed: threading.Event,
) -> None:
    original_lock = handoff_service_module.acquire_handoff_lifecycle_lock

    def observed_lock(session, handoff_id):  # noqa: ANN001
        if threading.current_thread().name.startswith(thread_name_prefix):
            observed.set()
        return original_lock(session, handoff_id)

    monkeypatch.setattr(
        handoff_service_module,
        "acquire_handoff_lifecycle_lock",
        observed_lock,
    )


def _accept_handoff_response(app, handoff_token: str, request_id: str) -> httpx.Response:
    return asyncio.run(
        _request_with_id(
            app,
            "POST",
            f"/v1/handoffs/{handoff_token}/accept",
            {},
            request_id,
        )
    )


def _decline_handoff_response(app, handoff_token: str, request_id: str) -> httpx.Response:
    return asyncio.run(
        _request_with_id(
            app,
            "POST",
            f"/v1/handoffs/{handoff_token}/decline",
            None,
            request_id,
        )
    )


def _run_named(thread_name: str, function, *args):  # noqa: ANN001, ANN002, ANN202
    threading.current_thread().name = thread_name
    return function(*args)


async def _request_with_id(
    app,
    method: str,
    path: str,
    json: object | None,
    request_id: str,
) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        return await client.request(
            method,
            path,
            json=json,
            headers={"X-Request-ID": request_id},
        )


def _expired_preview(
    session_factory: SessionFactory,
    app,
    handoff_token: str,
    expires_at: str,
):
    expiry_time = datetime_from_isoformat(expires_at) + timedelta(seconds=1)
    with transaction_boundary(session_factory) as session:
        return _handoff_service(
            session,
            app.state.runtime.config_registry,
            clock=lambda: expiry_time,
        ).get_preview(
            handoff_token,
            tenant_id="anytoolai",
            region="default",
        )


async def _request_with_exception_response(
    app,
    method: str,
    path: str,
    json: object | None = None,
) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        return await client.request(
            method,
            path,
            json=json,
            headers={"X-Request-ID": "req_pg_handoff_critical_recovery"},
        )


def _assert_quota_exhausted_handoff_recovery_state(
    session_factory: SessionFactory,
    *,
    handoff_id: str,
    source_session_id: str,
    expected_handoff_status: str,
) -> None:
    with transaction_boundary(session_factory) as session:
        handoff = (
            session.execute(
                sa.select(product_handoffs_table).where(
                    product_handoffs_table.c.id == handoff_id
                )
            )
            .mappings()
            .one()
        )
        quota_event_types = list(
            session.execute(
                sa.select(event_log_table.c.event_type).where(
                    event_log_table.c.handoff_id == handoff_id,
                    event_log_table.c.event_type.in_(["quota.checked", "quota.exhausted"]),
                )
            ).scalars()
        )
        handoff_event_types = list(
            session.execute(
                sa.select(event_log_table.c.event_type).where(
                    event_log_table.c.handoff_id == handoff_id,
                    event_log_table.c.event_type.like("handoff.%"),
                )
            ).scalars()
        )
        target_session_count = session.execute(
            sa.select(sa.func.count())
            .select_from(scenario_sessions_table)
            .where(scenario_sessions_table.c.parent_scenario_session_id == source_session_id)
        ).scalar_one()
        target_job_count = session.execute(
            sa.select(sa.func.count())
            .select_from(jobs_table)
            .where(jobs_table.c.scenario_session_id != source_session_id)
        ).scalar_one()
        usage = session.execute(sa.select(guest_quota_usage_table)).mappings().one()

    assert handoff["status"] == expected_handoff_status
    assert handoff["error_code"] == "quota_exhausted"
    assert handoff["target_scenario_session_id"] is None
    assert handoff["target_job_id"] is None
    assert quota_event_types.count("quota.checked") == 1
    assert quota_event_types.count("quota.exhausted") == 1
    assert handoff_event_types.count("handoff.failed") == 1
    assert "handoff.declined" not in handoff_event_types
    assert "handoff.expired" not in handoff_event_types
    assert "handoff.accepted" not in handoff_event_types
    assert "handoff.consumed" not in handoff_event_types
    assert target_session_count == 0
    assert target_job_count == 0
    assert usage["limit_count"] == 0
    assert usage["used_count"] == 0


def datetime_from_isoformat(value: str):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _scenario_start_quota_limit(app) -> int:
    policy = _override_guest_quota_policy(
        app,
        limit_count=TEST_GUEST_QUOTA_LIMIT,
    )
    return policy.limit_count


def _force_scenario_guest_quota(app) -> int:
    policy = _override_guest_quota_policy(
        app,
        dimension=QuotaDimension.scenario,
        limit_count=TEST_GUEST_QUOTA_LIMIT,
    )
    return policy.limit_count


def _force_zero_guest_quota(app) -> None:
    _override_guest_quota_policy(app, limit_count=0)


def _override_guest_quota_policy(
    app,
    *,
    quota_policy_id: str = "kernel_demo.guest_quota_v1",
    **policy_changes: object,
) -> QuotaPolicy:
    registry = app.state.runtime.config_registry
    policy = registry.get_quota_policy(quota_policy_id)
    assert policy is not None
    updated_policy = replace(policy, **policy_changes)
    app.state.runtime = replace(
        app.state.runtime,
        config_registry=replace(
            registry,
            quotas={
                **dict(registry.quotas),
                policy.quota_policy_id: updated_policy,
            },
        ),
    )
    return updated_policy
