from __future__ import annotations

import asyncio
from http import HTTPStatus

import pytest
import sqlalchemy as sa
from alembic import command
from anytoolai_platform_core.quotas.models import ExecutionOwner, ExecutionOwnerKind
from anytoolai_platform_core.quotas.readback import read_consumption
from anytoolai_platform_core.storage.db import guest_quota_usage_table
from anytoolai_platform_core.storage.transactions import (
    engine_from_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.workflows.models import JobStatus
from test_execution_admission_postgresql import allowance, start
from test_execution_admission_postgresql import runtime as runtime_fixture
from test_execution_finalization_postgresql import worker_for
from test_scenario_runtime_api import _request

from tests.db_support import build_alembic_config

pytestmark = [pytest.mark.postgresql, pytest.mark.slow]
runtime = runtime_fixture


def snapshot(connection, metadata):
    return {
        table.name: [
            dict(row)
            for row in connection.execute(
                sa.select(table).order_by(*table.primary_key.columns)
            ).mappings()
        ]
        for table in metadata.tables.values()
    }


def test_0017_preserves_results_paid_usage_and_all_reservation_states(runtime):
    factory, app, registry = runtime
    engine = engine_from_session_factory(factory)
    config = build_alembic_config(engine.url.render_as_string(hide_password=False))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0016")
        historical_metadata = sa.MetaData(schema="platform")
        historical_metadata.reflect(connection, schema="platform")

    grant = allowance()
    with transaction_boundary(factory) as session:
        success = start(session, registry, key="success")
        canceled = start(session, registry, key="canceled")
        paid = start(session, registry, grant, key="paid")
    worker = worker_for(runtime)
    try:
        finished = asyncio.run(worker.process_job(success.job_id))
        paid_finished = asyncio.run(worker.process_job(paid.job_id))
        assert finished.status is paid_finished.status is JobStatus.succeeded
        assert worker.cancel_job(canceled.job_id).status is JobStatus.canceled
        with transaction_boundary(factory) as session:
            pending = start(session, registry, key="pending")
            bucket_id = success.reservation.guest_quota_usage_id
            # An old writer after preparation changes only used_count.
            session.execute(
                sa.update(guest_quota_usage_table)
                .where(guest_quota_usage_table.c.id == bucket_id)
                .values(used_count=guest_quota_usage_table.c.used_count + 1)
            )

        with engine.begin() as connection:
            before = snapshot(connection, historical_metadata)
            assert before["guest_quota_usage"][0]["legacy_used_count"] == 0
            config.attributes["connection"] = connection
            command.upgrade(config, "0017")
            before["guest_quota_usage"][0]["legacy_used_count"] = 1
            assert snapshot(connection, historical_metadata) == before
            command.upgrade(config, "head")

        owner = ExecutionOwner("anytoolai", "ru", ExecutionOwnerKind.guest, "guest_demo")
        with transaction_boundary(factory) as session:
            state = read_consumption(session, owner, bucket_id)
            assert (state.used, state.legacy_used, state.successful_used, state.reserved) == (
                2,
                1,
                1,
                1,
            )
            replay = start(session, registry, key="success")
            assert replay.is_replay and replay.result_artifact_id == finished.result_artifact_id
            paid_replay = start(session, registry, grant, key="paid")
            assert paid_replay.is_replay
            assert paid_replay.result_artifact_id == paid_finished.result_artifact_id
        response = asyncio.run(_request(app, "GET", f"/v1/results/{finished.result_artifact_id}"))
        assert response.status_code == HTTPStatus.OK, response.text
        assert response.json()["output"]["values"]["deadline"] == "next Friday"

        assert asyncio.run(worker.process_job(pending.job_id)).status is JobStatus.succeeded
        with transaction_boundary(factory) as session:
            state = read_consumption(session, owner, bucket_id)
            assert (state.used, state.legacy_used, state.successful_used, state.reserved) == (
                3,
                1,
                2,
                0,
            )
    finally:
        worker.dispose()
