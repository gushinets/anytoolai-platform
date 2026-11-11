"""Actual PostgreSQL metering/outbox and synthetic reverse HTTP; no live providers."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread, current_thread
from time import sleep
from typing import Any
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from anytoolai_platform_api.dependencies import get_settings
from anytoolai_platform_api.portal_session import PortalUserPrincipal, authenticate_portal_user
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.quotas.execution_repository import PaidAllowanceUsageRepository
from anytoolai_platform_core.quotas.exhaustion import (
    claim_exhaustion,
    enqueue_exhaustion,
    settle_exhaustion,
)
from anytoolai_platform_core.quotas.finalization import finalize_success
from anytoolai_platform_core.quotas.models import ExecutionAcceptance, FinalExecutionResult
from anytoolai_platform_core.storage.db import (
    allowance_exhaustion_outbox_table as outbox,
)
from anytoolai_platform_core.storage.db import (
    artifacts_table,
    paid_allowance_usage_table,
)
from anytoolai_platform_core.storage.transactions import (
    SessionFactory,
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.workflows import runner
from anytoolai_platform_core.workflows.models import JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from anytoolai_platform_worker import exhaustion as delivery_module
from anytoolai_platform_worker.exhaustion import ExhaustionDelivery, ExhaustionSettings
from anytoolai_platform_worker.queues import WorkflowJobMessage
from anytoolai_platform_worker.worker import Worker
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session
from test_execution_admission_postgresql import allowance, rows, start
from test_execution_admission_postgresql import runtime as runtime_fixture
from test_execution_finalization_postgresql import candidate, worker_for
from test_paid_contract_fixtures import validate_contract

from tests.db_support import provision_database

pytestmark = [pytest.mark.postgresql, pytest.mark.slow]
runtime = runtime_fixture
DUPLICATE_DELIVERIES = 2
SERVICE = "synthetic-portal-usage-" + "s" * 32


def usage_client(runtime: tuple[SessionFactory, FastAPI, ConfigRegistry]) -> TestClient:
    _, app, _ = runtime
    app.dependency_overrides[get_settings] = lambda: Settings(
        portal_service_token=SecretStr(SERVICE),
        portal_usage_read_enabled=True,
    )
    return TestClient(app)


def usage_path(grant: Any, *ids: str) -> str:
    return f"/internal/v1/usage/{grant.owner.owner_id}?tenant_id=anytoolai&region=ru" + "".join(
        "&allowance_id=" + identity for identity in (ids or (grant.allowance_id,))
    )


def test_usage_unknown_zero_busy_exhausted_and_historical_product_scope(
    runtime: tuple[SessionFactory, FastAPI, ConfigRegistry],
) -> None:
    factory, app, registry = runtime
    grant = allowance()
    with usage_client(runtime) as client:
        headers = {"Authorization": "Bearer " + SERVICE}
        response = client.get(usage_path(grant), headers=headers)
        validate_contract("usage-response-v1", response.json())
        assert response.json()["items"] == [
            {"allowance_id": grant.allowance_id, "status": "unobserved"}
        ]
        assert rows(factory, paid_allowance_usage_table) == []
        with transaction_boundary(factory) as session:
            PaidAllowanceUsageRepository(session).ensure_usage(grant)
        zero = client.get(usage_path(grant), headers=headers).json()["items"][0]
        assert zero["successful_used"] == zero["reserved"] == 0
        assert zero["remaining"] == zero["available"] == 1
        with transaction_boundary(factory) as session:
            accepted = start(session, registry, grant)
        busy = client.get(usage_path(grant), headers=headers).json()["items"][0]
        assert (
            busy["successful_used"],
            busy["reserved"],
            busy["remaining"],
            busy["available"],
        ) == (0, 1, 1, 0)
        assert rows(factory, outbox) == []
        foreign = allowance()
        hidden = client.get(usage_path(foreign, grant.allowance_id, str(uuid4())), headers=headers)
        assert all(set(item) == {"allowance_id", "status"} for item in hidden.json()["items"])
        worker = worker_for(runtime)
        try:
            assert asyncio.run(worker.process_job(accepted.job_id)).status is JobStatus.succeeded
            assert asyncio.run(worker.process_job(accepted.job_id)).status is JobStatus.succeeded
        finally:
            worker.dispose()
        used = client.get(usage_path(grant), headers=headers)
        validate_contract("usage-response-v1", used.json())
        assert used.headers["Cache-Control"] == "no-store"
        assert (
            used.json()["items"][0]["successful_used"],
            used.json()["items"][0]["reserved"],
        ) == (1, 0)
        assert len(rows(factory, outbox)) == 1
        principal = PortalUserPrincipal(
            grant.owner, datetime.now(UTC) + timedelta(minutes=5), "platform-kernel", 1
        )
        app.dependency_overrides[authenticate_portal_user] = lambda: principal
        for product, status in (("kernel_demo", "observed"), ("foreign", "unobserved")):
            result = client.get(
                f"/v1/products/{product}/paid-usage?allowance_id={grant.allowance_id}"
            )
            assert (
                result.status_code == HTTPStatus.OK
                and result.json()["items"][0]["status"] == status
            )
        assert rows(factory, paid_allowance_usage_table)[0]["used_count"] == 1


@pytest.mark.parametrize(
    "suffix", ["", "&allowance_id=bad", "&allowance_id=BOOL", "&tenant_id=foreign"]
)
def test_usage_refusals_and_no_browser_access(
    runtime: tuple[SessionFactory, FastAPI, ConfigRegistry], suffix: str
) -> None:
    grant = allowance()
    with usage_client(runtime) as client:
        path = usage_path(grant)
        assert client.get(path).status_code == HTTPStatus.UNAUTHORIZED
        assert (
            client.get(
                path,
                headers={"Authorization": "Bearer " + SERVICE, "Origin": "https://browser.test"},
            ).status_code
            == HTTPStatus.FORBIDDEN
        )
        if suffix:
            result = client.get(path + suffix, headers={"Authorization": "Bearer " + SERVICE})
            assert result.status_code in (403, 422)
        assert (
            client.get(
                path + "&allowance_id=" + grant.allowance_id,
                headers={"Authorization": "Bearer " + SERVICE},
            ).status_code
            == HTTPStatus.UNPROCESSABLE_ENTITY
        )
        assert (
            client.get(
                path.split("&allowance_id")[0], headers={"Authorization": "Bearer " + SERVICE}
            ).status_code
            == HTTPStatus.UNPROCESSABLE_ENTITY
        )
        assert (
            client.get(
                usage_path(grant, *(str(uuid4()) for _ in range(101))),
                headers={"Authorization": "Bearer " + SERVICE},
            ).status_code
            == HTTPStatus.UNPROCESSABLE_ENTITY
        )
        factory, app, _ = runtime
        app.dependency_overrides[get_settings] = lambda: Settings(
            portal_service_token=SecretStr(SERVICE)
        )
        assert (
            client.get(path, headers={"Authorization": "Bearer " + SERVICE}).status_code
            == HTTPStatus.FORBIDDEN
        )
        assert rows(factory, paid_allowance_usage_table) == []


def test_usage_storage_failure_is_503_without_counters(
    runtime: tuple[SessionFactory, FastAPI, ConfigRegistry], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: Any) -> None:
        raise sa.exc.OperationalError("read", {}, RuntimeError("synthetic storage unavailable"))

    monkeypatch.setattr(PaidAllowanceUsageRepository, "get_owned_allowance", fail)
    with usage_client(runtime) as client:
        response = client.get(
            usage_path(allowance()), headers={"Authorization": "Bearer " + SERVICE}
        )
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE and "items" not in response.json()


def test_final_result_debit_outbox_rollback_is_atomic(
    runtime: tuple[SessionFactory, FastAPI, ConfigRegistry],
) -> None:
    factory, _, registry = runtime
    grant = allowance()
    with transaction_boundary(factory) as session:
        accepted = start(session, registry, grant)
    final = candidate(runtime, accepted)
    with pytest.raises(RuntimeError, match="rollback"), transaction_boundary(factory) as session:
        transition = finalize_success(session, accepted.job_id, final, config_registry=registry)
        enqueue_exhaustion(session, transition)
        assert session.scalar(sa.select(sa.func.count()).select_from(outbox)) == 1
        raise RuntimeError("rollback")
    assert rows(factory, outbox) == rows(factory, artifacts_table) == []
    bucket = rows(factory, paid_allowance_usage_table)[0]
    assert (bucket["used_count"], bucket["reserved_count"]) == (0, 1)


def test_rollback_recovery_writes_one_exhaustion_and_duplicate_is_immutable(
    runtime: tuple[SessionFactory, FastAPI, ConfigRegistry], monkeypatch: pytest.MonkeyPatch
) -> None:

    factory, _, registry = runtime
    with transaction_boundary(factory) as session:
        accepted = start(session, registry, allowance())
    original = runner.enqueue_exhaustion
    calls = []

    def fail_first(session: Session, transition: Any) -> None:
        original(session, transition)
        calls.append(transition)
        if len(calls) == 1:
            raise RuntimeError("synthetic crash after exhaustion insertion")

    monkeypatch.setattr(runner, "enqueue_exhaustion", fail_first)
    worker = worker_for(runtime)
    try:
        assert asyncio.run(worker.process_job(accepted.job_id)).status is JobStatus.succeeded
    finally:
        worker.dispose()
    assert len(calls) == DUPLICATE_DELIVERIES
    before = rows(factory, outbox)
    assert len(before) == 1 and rows(factory, paid_allowance_usage_table)[0]["used_count"] == 1
    final = candidate_from_success(runtime, accepted)
    with transaction_boundary(factory) as session:
        transition = finalize_success(session, accepted.job_id, final, config_registry=registry)
        assert not transition.became_exhausted
        enqueue_exhaustion(session, transition)
    assert rows(factory, outbox) == before


def candidate_from_success(
    runtime: tuple[SessionFactory, FastAPI, ConfigRegistry], accepted: Any
) -> FinalExecutionResult:

    with runtime[0]() as session:
        job = JobRepository(session).get(accepted.job_id)
        return FinalExecutionResult(job, ArtifactRepository(session).get(job.result_artifact_id))


@pytest.fixture
def receiver() -> Iterator[tuple[str, list, list[int], Event]]:
    seen = []
    status = [204]
    delivered = Event()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            seen.append(
                (
                    self.path,
                    self.headers["Authorization"],
                    json.loads(self.rfile.read(int(self.headers["Content-Length"]))),
                )
            )
            self.send_response(status[0])
            self.end_headers()
            delivered.set()

        def log_message(self, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", seen, status, delivered
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def exhausted(runtime: tuple[SessionFactory, FastAPI, ConfigRegistry]) -> ExecutionAcceptance:
    factory, _, registry = runtime
    with transaction_boundary(factory) as session:
        accepted = start(session, registry, allowance())
    worker = worker_for(runtime)
    try:
        asyncio.run(worker.process_job(accepted.job_id))
    finally:
        worker.dispose()
    return accepted


def delivery(factory: SessionFactory, origin: str) -> ExhaustionDelivery:
    return ExhaustionDelivery(
        factory,
        ExhaustionSettings(
            base_url=origin,
            service_token=SecretStr("synthetic-reverse-" + "s" * 32),
            tenant_id="anytoolai",
            region="ru",
            app_env="test",
        ),
    )


def expire(factory: SessionFactory) -> None:
    with factory.begin() as session:
        session.execute(
            sa.update(outbox).values(
                lease_expires_at=sa.func.clock_timestamp() - sa.text("interval '1 second'"),
                next_attempt_at=sa.func.clock_timestamp() - sa.text("interval '1 second'"),
            )
        )


def test_crash_after_remote_ack_redelivers_identical_event_and_fences_old_claim(
    runtime: tuple[SessionFactory, FastAPI, ConfigRegistry],
    receiver: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = runtime[0]
    exhausted(runtime)
    assert claim_exhaustion(factory, "anytoolai", "foreign") is None
    origin, seen, _, _ = receiver
    original = delivery_module.settle_exhaustion

    def crash(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("crash before local acknowledgement")

    monkeypatch.setattr(delivery_module, "settle_exhaustion", crash)
    with pytest.raises(RuntimeError, match="crash"):
        delivery(factory, origin).deliver_once()
    assert rows(factory, outbox)[0]["state"] == "pending"
    expire(factory)
    monkeypatch.setattr(delivery_module, "settle_exhaustion", original)
    assert delivery(factory, origin).deliver_once()
    validate_contract("exhaustion-v1", seen[0][2])
    assert seen[0] == seen[1] and len(seen) == DUPLICATE_DELIVERIES
    assert not delivery(factory, origin).deliver_once()
    assert rows(factory, outbox)[0]["state"] == "delivered"
    with factory.begin() as session:
        session.execute(
            sa.update(outbox).values(state="pending", next_attempt_at=sa.func.clock_timestamp())
        )
    first = claim_exhaustion(factory, "anytoolai", "ru")
    expire(factory)
    assert not settle_exhaustion(factory, first)
    second = claim_exhaustion(factory, "anytoolai", "ru")
    assert not settle_exhaustion(factory, first)
    assert settle_exhaustion(factory, second)
    assert claim_exhaustion(factory, "anytoolai", "foreign") is None


@pytest.mark.parametrize(
    "status, expected",
    [
        (429, "pending"),
        (503, "pending"),
        (401, "parked"),
        (409, "parked"),
        (302, "parked"),
        (200, "parked"),
    ],
)
def test_retry_and_permanent_parking(
    runtime: tuple[SessionFactory, FastAPI, ConfigRegistry],
    receiver: tuple,
    status: int,
    expected: str,
) -> None:
    factory = runtime[0]
    exhausted(runtime)
    origin, seen, response_status, _ = receiver
    response_status[0] = status
    assert delivery(factory, origin).deliver_once()
    row = rows(factory, outbox)[0]
    assert row["state"] == expected and row["attempt_count"] == 1
    assert row["last_error"].endswith(":" + str(status))
    assert row["lease_owner"] is row["lease_expires_at"] is None
    assert not delivery(factory, origin).deliver_once()
    assert len(seen) == 1


def test_worker_delivers_while_workflow_is_waiting(
    runtime: tuple[SessionFactory, FastAPI, ConfigRegistry], receiver: tuple
) -> None:

    factory = runtime[0]
    exhausted(runtime)
    origin, seen, _, delivered = receiver

    class Handler:
        async def handle(self, job_id: str) -> None:
            assert await asyncio.to_thread(delivered.wait, 5)
            worker.request_shutdown()

        def dispose(self) -> None:
            pass

    class Queue:
        def next_message(self) -> WorkflowJobMessage:
            return WorkflowJobMessage(job_id="synthetic-long-workflow")

    worker = Worker(
        Handler(),
        job_queue=Queue(),
        exhaustion_delivery=delivery(factory, origin),
        poll_interval_seconds=0.01,
    )
    try:
        asyncio.run(worker.run_forever())
    finally:
        worker.dispose()
    assert len(seen) == 1 and rows(factory, outbox)[0]["state"] == "delivered"


def test_forward_outbox_migration_keeps_existing_usage_without_inventing_events() -> None:

    with provision_database(
        database_name_prefix="any766_exhaustion_migration",
        upgrade_target="0020",
        skip_reason="exhaustion migration",
    ) as (engine, config, _):
        factory = build_session_factory(engine)
        with factory.begin() as session:
            record = PaidAllowanceUsageRepository(session).ensure_usage(allowance())
            session.execute(
                sa.update(paid_allowance_usage_table)
                .where(paid_allowance_usage_table.c.id == record.id)
                .values(used_count=1)
            )
        before = rows(factory, paid_allowance_usage_table)
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        assert rows(factory, paid_allowance_usage_table) == before
        assert rows(factory, outbox) == []


def test_expired_lease_cannot_ack_after_row_lock_wait(
    runtime: tuple[SessionFactory, FastAPI, ConfigRegistry],
) -> None:
    factory = runtime[0]
    exhausted(runtime)
    claim = claim_exhaustion(factory, "anytoolai", "ru")
    waiting = Event()
    engine = factory.kw["bind"]

    def before_cursor(
        connection: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        if current_thread().name.startswith("exhaustion-settle") and statement.startswith("SELECT"):
            waiting.set()

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="exhaustion-settle") as pool:
        try:
            with factory.begin() as session:
                session.execute(sa.select(outbox.c.id).with_for_update()).scalar_one()
                session.execute(
                    sa.update(outbox).values(
                        lease_expires_at=sa.func.clock_timestamp()
                        + sa.text("interval '200 milliseconds'"),
                    )
                )
                sa.event.listen(engine, "before_cursor_execute", before_cursor)
                acknowledgement = pool.submit(settle_exhaustion, factory, claim)
                assert waiting.wait(5)
                sleep(0.3)  # The row remains locked across the finite lease boundary.
            assert not acknowledgement.result(timeout=5)
        finally:
            sa.event.remove(engine, "before_cursor_execute", before_cursor)
    assert rows(factory, outbox)[0]["state"] == "pending"
