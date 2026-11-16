"""Consumer configuration cannot transfer retained execution history to another audience."""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from threading import Event
from typing import Literal
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from anytoolai_platform_api.paid_access import get_snapshot_client, optional_portal_user
from anytoolai_platform_api.portal_session import (
    PortalSessionClient,
    PortalUserPrincipal,
    get_portal_session_client,
)
from anytoolai_platform_core.quotas.consumer_binding import (
    ConsumerBindingMismatch,
    check_consumer_binding,
    require_consumer_binding,
)
from anytoolai_platform_core.quotas.execution_repository import PaidAllowanceUsageRepository
from anytoolai_platform_core.storage.db import (
    allowance_exhaustion_outbox_table,
    jobs_table,
    paid_access_coherence_table,
    paid_allowance_usage_table,
    paid_consumer_binding_table,
    runtime_tables,
    scenario_sessions_table,
)
from anytoolai_platform_core.storage.transactions import build_session_factory
from anytoolai_platform_core.workflows.models import JobStatus
from anytoolai_platform_worker.exhaustion import ExhaustionDelivery, ExhaustionSettings
from fastapi.testclient import TestClient
from pydantic import SecretStr
from test_execution_admission_postgresql import allowance
from test_execution_finalization_postgresql import worker_for
from test_paid_access_admission_postgresql import START, rows, seed_paid_source
from test_paid_access_admission_postgresql import runtime as admission_runtime
from test_paid_usage_exhaustion_postgresql import receiver as receiver_fixture
from test_scenario_runtime_api import _start_payload

from tests.db_support import provision_database

pytestmark = [pytest.mark.postgresql, pytest.mark.slow]
runtime = admission_runtime
receiver = receiver_fixture


@pytest.fixture
def principal() -> PortalUserPrincipal:
    return PortalUserPrincipal(
        owner=allowance().owner,
        valid_until=datetime.now(UTC) + timedelta(minutes=20),
        consumer_id="platform-kernel",
        consumer_policy_revision=1,
    )


@pytest.mark.parametrize("history", ["empty", "custom", "usage", "deferred", "ambiguous"])
def test_migration_binds_known_history_and_refuses_ambiguous_consumers(principal, history):
    with provision_database(
        database_name_prefix="any766_consumer",
        upgrade_target="0021",
        skip_reason="consumer binding migration",
    ) as (engine, config, _):
        factory = build_session_factory(engine)
        with factory.begin() as session:
            if history in {"custom", "ambiguous"}:
                consumers = ["custom-kernel"] if history == "custom" else ["first", "second"]
                for consumer in consumers:
                    session.execute(
                        paid_access_coherence_table.insert().values(
                            consumer_id=consumer,
                            tenant_id="anytoolai",
                            region="ru",
                            user_id=principal.owner.owner_id,
                            revision_floor=7,
                        )
                    )
            if history == "usage":
                PaidAllowanceUsageRepository(session).ensure_usage(allowance())
        if history == "deferred":
            seed_paid_source(factory, principal)
        preserved = (
            paid_access_coherence_table,
            paid_allowance_usage_table,
            scenario_sessions_table,
        )
        before = {table.name: rows(factory, table) for table in preserved}
        if history == "ambiguous":
            with (
                pytest.raises(sa.exc.DBAPIError, match="multiple consumers"),
                engine.begin() as conn,
            ):
                config.attributes["connection"] = conn
                command.upgrade(config, "head")
            assert not sa.inspect(engine).has_table("paid_consumer_binding", schema="platform")
        else:
            with engine.begin() as conn:
                config.attributes["connection"] = conn
                command.upgrade(config, "head")
            expected = "custom-kernel" if history == "custom" else "platform-kernel"
            assert rows(factory, paid_consumer_binding_table) == (
                [] if history == "empty" else [{"id": 1, "consumer_id": expected}]
            )
        assert before == {table.name: rows(factory, table) for table in preserved}


@pytest.mark.parametrize("history", ["usage", "deferred"])
@pytest.mark.parametrize("same_user", [False, True])
def test_migration_refuses_custom_consumer_over_pre_coherence_history(
    principal, history: Literal["usage", "deferred"], same_user: bool,
) -> None:
    with provision_database(
        database_name_prefix="any766_legacy_consumer",
        upgrade_target="0018",
        skip_reason="legacy consumer ownership migration",
    ) as (engine, config, _):
        factory = build_session_factory(engine)
        if history == "usage":
            with factory.begin() as session:
                PaidAllowanceUsageRepository(session).ensure_usage(
                    allowance(owner=principal.owner, quantity=3)
                )
                session.execute(sa.update(paid_allowance_usage_table).values(used_count=2))
        else:
            seed_paid_source(factory, principal)
        with engine.begin() as conn:
            config.attributes["connection"] = conn
            command.upgrade(config, "0021")
        with factory.begin() as session:
            # A later observation, even for the same user, cannot identify the
            # consumer that owned paid history before coherence existed.
            session.execute(
                paid_access_coherence_table.insert().values(
                    consumer_id="custom-kernel", tenant_id="anytoolai", region="ru",
                    user_id=principal.owner.owner_id if same_user else str(uuid4()),
                    revision_floor=7,
                )
            )
        preserved = (
            paid_access_coherence_table, paid_allowance_usage_table,
            scenario_sessions_table, jobs_table,
        )
        before = {table.name: rows(factory, table) for table in preserved}
        with (
            pytest.raises(sa.exc.DBAPIError, match="Paid history has unproven consumer ownership"),
            engine.begin() as conn,
        ):
            config.attributes["connection"] = conn
            command.upgrade(config, "head")
        assert not sa.inspect(engine).has_table("paid_consumer_binding", schema="platform")
        with engine.connect() as conn:
            assert conn.scalar(sa.text("SELECT version_num FROM alembic_version")) == "0021"
        assert before == {table.name: rows(factory, table) for table in preserved}


@pytest.mark.parametrize(
    "consumer,rollback",
    [
        ("platform-kernel", False),
        ("another-kernel", False),
        ("another-kernel", True),
    ],
)
def test_competing_first_binding_waits_for_commit_or_rollback(runtime, consumer, rollback):
    factory = runtime[0]
    inserting = Event()

    def before_cursor(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO platform.paid_consumer_binding"):
            inserting.set()

    def compete():
        try:
            with factory.begin() as session:
                require_consumer_binding(session, consumer)
            return True
        except ConsumerBindingMismatch:
            return False

    with factory() as first, ThreadPoolExecutor(1) as pool:
        require_consumer_binding(first, "platform-kernel")
        sa.event.listen(factory.kw["bind"], "before_cursor_execute", before_cursor)
        try:
            future = pool.submit(compete)
            assert inserting.wait(5)
            assert not future.done()
        finally:
            if rollback:
                first.rollback()
            else:
                first.commit()
            sa.event.remove(factory.kw["bind"], "before_cursor_execute", before_cursor)
        assert future.result(5) is (rollback or consumer == "platform-kernel")
    # A fresh connection observes the same binding; failed competitors cannot replace it.
    with factory() as session:
        assert check_consumer_binding(session, consumer if rollback else "platform-kernel")


def test_config_change_blocks_all_paid_surfaces_preserves_jobs_and_recovers(runtime, receiver):
    factory, app, registry, principal, document, _ = runtime
    service = "synthetic-service-" + "s" * 32
    app.state.settings = app.state.settings.model_copy(
        update={
            "portal_service_token": SecretStr(service),
            "portal_usage_read_enabled": True,
            "portal_access_invalidation_enabled": True,
        }
    )

    class IdentityTransport(PortalSessionClient):
        def _post(self, operation, payload):
            assert operation == "introspect"
            return json.dumps(
                {
                    "schema_version": 2,
                    "consumer_id": app.state.settings.portal_consumer_id,
                    "consumer_policy_revision": 1,
                    "tenant_id": "anytoolai",
                    "region": "ru",
                    "user_id": principal.owner.owner_id,
                    "valid_until": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
                }
            ).encode()

    app.dependency_overrides.pop(optional_portal_user)
    app.dependency_overrides[get_portal_session_client] = lambda: IdentityTransport(
        app.state.settings
    )
    client = TestClient(app)
    auth = {"Authorization": "Bearer " + "a" * 43, "Idempotency-Key": "original"}
    accepted = client.post(START, json=_start_payload(), headers=auth)
    assert accepted.status_code == HTTPStatus.OK, accepted.text
    original = accepted.json()
    app.state.settings = app.state.settings.model_copy(update={"portal_consumer_id": "other"})

    # A consumer mismatch does not abandon an already accepted job or its reservation.
    worker = worker_for((factory, app, registry))
    try:
        assert asyncio.run(worker.process_job(original["job_id"])).status is JobStatus.succeeded
    finally:
        worker.dispose()
    with factory() as session:
        artifact = session.execute(
            sa.select(jobs_table.c.result_artifact_id).where(
                jobs_table.c.id == original["job_id"],
            )
        ).scalar_one()
    assert artifact
    assert rows(factory, paid_allowance_usage_table)[0]["used_count"] == 1
    assert len(rows(factory, allowance_exhaustion_outbox_table)) == 1
    session_path = "/v1/scenario-sessions/" + original["scenario_session_id"]
    usage_query = {"allowance_id": document.allowances[0].allowance_id}
    before = {name: rows(factory, table) for name, table in runtime_tables.items()}
    requests = [
        ("post", START, {"json": _start_payload()}),
        ("get", session_path, {}),
        ("get", "/v1/results/" + artifact, {}),
        ("get", "/v1/products/kernel_demo/paid-usage", {"params": usage_query}),
        ("post", session_path + "/next-actions/missing", {"json": {}}),
        ("post", "/v1/handoffs", {"json": {}}),
        ("get", "/v1/handoffs/missing", {}),
        ("post", "/v1/handoffs/missing/accept", {"json": {}}),
        ("post", "/v1/handoffs/missing/decline", {"json": {}}),
        ("post", "/v1/client-events", {"json": {}}),
    ]
    for method, path, kwargs in requests:
        response = client.request(method, path, headers=auth, **kwargs)
        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE, (path, response.text)
        assert response.json()["error"]["code"] == "paid_consumer_mismatch"
    service_auth = {"Authorization": "Bearer " + service}
    assert (
        client.get(
            "/internal/v1/usage/" + principal.owner.owner_id,
            headers=service_auth,
            params=usage_query | {"tenant_id": "anytoolai", "region": "ru"},
        ).status_code
        == HTTPStatus.SERVICE_UNAVAILABLE
    )
    assert (
        client.post(
            "/internal/v1/access-invalidations",
            headers=service_auth,
            json={
                "schema_version": 1,
                "tenant_id": "anytoolai",
                "region": "ru",
                "user_id": principal.owner.owner_id,
                "access_revision": 99,
            },
        ).status_code
        == HTTPStatus.SERVICE_UNAVAILABLE
    )
    origin, seen, _, _ = receiver
    settings = ExhaustionSettings(
        base_url=origin,
        service_token=SecretStr(service),
        tenant_id="anytoolai",
        region="ru",
        consumer_id="other",
        app_env="test",
    )
    with pytest.raises(ConsumerBindingMismatch):
        ExhaustionDelivery(factory, settings).deliver_once()
    assert seen == []
    assert before == {name: rows(factory, table) for name, table in runtime_tables.items()}

    assert_restored_history(
        factory, app, client, auth, session_path, artifact, original, usage_query
    )
    assert ExhaustionDelivery(
        factory,
        settings.model_copy(
            update={
                "consumer_id": "platform-kernel",
            }
        ),
    ).deliver_once()
    assert len(seen) == 1
    assert rows(factory, allowance_exhaustion_outbox_table)[0]["state"] == "delivered"


def assert_restored_history(
    factory, app, client, auth, session_path, artifact, original, usage_query
):
    # Restore the saved audience. Historical access/replay needs no current grant or snapshot.
    app.state.settings = app.state.settings.model_copy(
        update={"portal_consumer_id": "platform-kernel"}
    )

    class OfflineAuthority:
        def fetch(self, owner):
            pytest.fail("Historical reads/replay must not require fresh grants")

    app.dependency_overrides[get_snapshot_client] = OfflineAuthority
    with factory.begin() as session:
        session.execute(sa.update(paid_access_coherence_table).values(snapshot=None))
    assert client.get(session_path, headers=auth).status_code == HTTPStatus.OK
    assert client.get("/v1/results/" + artifact, headers=auth).status_code == HTTPStatus.OK
    replay = client.post(START, json=_start_payload(), headers=auth)
    assert replay.status_code == HTTPStatus.OK, replay.text
    assert replay.json()["scenario_session_id"] == original["scenario_session_id"]
    assert replay.json()["job_id"] == original["job_id"]
    usage = client.get("/v1/products/kernel_demo/paid-usage", params=usage_query, headers=auth)
    assert usage.json()["items"][0]["successful_used"] == 1


def test_delivery_waits_for_first_binding_without_claiming(runtime, receiver):
    factory = runtime[0]
    origin, seen, _, _ = receiver
    assert not ExhaustionDelivery(
        factory,
        ExhaustionSettings(
            base_url=origin,
            service_token=SecretStr("synthetic-" + "s" * 32),
            tenant_id="anytoolai",
            region="ru",
            app_env="test",
        ),
    ).deliver_once()
    assert seen == []
    assert rows(factory, paid_consumer_binding_table) == []
