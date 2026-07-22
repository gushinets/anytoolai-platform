from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import sqlalchemy as sa
from anytoolai_platform_api.main import _safe_request_path
from anytoolai_platform_core.artifacts.models import ArtifactRecord, ArtifactStatus
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord, ScenarioSessionStatus
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.db import (
    action_runs_table,
    event_log_table,
    guest_quota_usage_table,
    product_handoffs_table,
    provider_calls_table,
    scenario_sessions_table,
)
from anytoolai_platform_core.storage.transactions import transaction_boundary
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from anytoolai_platform_worker.composition import build_worker
from starlette.requests import Request
from test_scenario_runtime_api import CONFIG_ROOT, _build_session_factory, _create_test_app

FIXTURE_ROOT = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "provider"
    / "fake_provider_outputs"
)


def _seed_source(session) -> tuple[str, str]:
    scenario = ScenarioSessionRepository(session).create(
        ScenarioSessionRecord(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            frontend_id="kernel_demo_ce",
            scenario_id="kernel_demo.handoff_smoke_source_v1",
            scenario_version=1,
            guest_id="guest_demo",
            status=ScenarioSessionStatus.completed,
            current_checkpoint_id="result_ready",
            scenario_chain_id="chain_api_handoff",
            completed_at=datetime.now(UTC),
        )
    )
    jobs = JobRepository(session)
    job = jobs.create(
        JobRecord(
            tenant_id=scenario.tenant_id,
            region=scenario.region,
            product_id=scenario.product_id,
            frontend_id=scenario.frontend_id,
            scenario_session_id=scenario.id,
            workflow_id="kernel_demo.single_action_extract_v1",
            workflow_version=1,
        )
    )
    job = jobs.claim_created(job.id)
    assert job is not None
    artifact = ArtifactRepository(session).create(
        ArtifactRecord(
            tenant_id=scenario.tenant_id,
            region=scenario.region,
            product_id=scenario.product_id,
            frontend_id=scenario.frontend_id,
            scenario_session_id=scenario.id,
            job_id=job.id,
            artifact_type="structured_output",
            status=ArtifactStatus.stored,
            content_json={"title": "API safe summary", "fields": ["one", "two"]},
            metadata={
                "artifact_role": "workflow_result",
                "schema_ref": "kernel_demo.extract_output_v1",
                "schema_version": 1,
                "workflow_id": job.workflow_id,
                "workflow_version": job.workflow_version,
            },
        )
    )
    jobs.mark_succeeded(
        replace(
            job,
            status=JobStatus.succeeded,
            result_artifact_id=artifact.id,
            completed_at=datetime.now(UTC),
        )
    )
    return scenario.id, artifact.id


async def _request(app, method: str, path: str, json: Any | None = None) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        return await client.request(
            method, path, json=json, headers={"X-Request-ID": "req_handoff"}
        )


def _create(app, source_session_id: str, artifact_id: str) -> httpx.Response:
    return asyncio.run(
        _request(
            app,
            "POST",
            "/v1/handoffs",
            {
                "handoff_definition_id": "kernel_demo_source_to_target_v1",
                "source_scenario_session_id": source_session_id,
                "source_artifact_id": artifact_id,
            },
        )
    )


def test_handoff_token_is_redacted_from_request_log_path() -> None:
    token = "hnd_secret_value_that_must_not_be_logged"
    scope = {
        "type": "http",
        "method": "GET",
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
        "root_path": "",
        "path": f"/v1/handoffs/{token}/accept",
        "raw_path": f"/v1/handoffs/{token}/accept".encode(),
        "query_string": b"",
        "headers": [],
    }
    request = Request(scope)
    assert _safe_request_path(request) == "/v1/handoffs/{handoff_token}/accept"
    assert token not in _safe_request_path(request)

    request.scope["route"] = SimpleNamespace(path="/v1/handoffs/{handoff_token}/accept")
    assert _safe_request_path(request) == "/v1/handoffs/{handoff_token}/accept"


def test_handoff_api_create_preview_accept_decline_and_expiry(tmp_path: Path) -> None:
    factory = _build_session_factory(tmp_path)
    app = _create_test_app(factory)
    with transaction_boundary(factory) as session:
        source_id, artifact_id = _seed_source(session)

    created = _create(app, source_id, artifact_id)
    assert created.status_code == HTTPStatus.OK
    created_payload = created.json()
    token = created_payload["handoff_token"]
    assert created_payload["status"] == "created"

    preview = asyncio.run(_request(app, "GET", f"/v1/handoffs/{token}"))
    assert preview.status_code == HTTPStatus.OK
    assert preview.json()["status"] == "viewed"
    assert preview.json()["preview"] == {"title": "API safe summary", "fields": ["one", "two"]}
    assert "source_artifact_id" not in preview.text
    assert "token_hash" not in preview.text

    accepted = asyncio.run(_request(app, "POST", f"/v1/handoffs/{token}/accept", {}))
    assert accepted.status_code == HTTPStatus.OK
    assert accepted.json()["status"] == "consumed"
    assert accepted.json()["target_scenario_session_id"]
    assert accepted.json()["target_job_id"]

    repeated = asyncio.run(_request(app, "POST", f"/v1/handoffs/{token}/accept", {}))
    assert repeated.status_code == HTTPStatus.CONFLICT
    assert repeated.json()["error"]["code"] == "handoff_already_accepted"

    declined_created = _create(app, source_id, artifact_id).json()
    declined = asyncio.run(
        _request(app, "POST", f"/v1/handoffs/{declined_created['handoff_token']}/decline")
    )
    assert declined.status_code == HTTPStatus.OK
    assert declined.json()["status"] == "declined"

    expired_created = _create(app, source_id, artifact_id).json()
    with transaction_boundary(factory) as session:
        session.execute(
            sa.update(product_handoffs_table)
            .where(product_handoffs_table.c.id == expired_created["handoff_id"])
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    expired = asyncio.run(_request(app, "GET", f"/v1/handoffs/{expired_created['handoff_token']}"))
    assert expired.status_code == HTTPStatus.OK
    assert expired.json()["status"] == "expired"
    expired_accept = asyncio.run(
        _request(app, "POST", f"/v1/handoffs/{expired_created['handoff_token']}/accept", {})
    )
    assert expired_accept.status_code == HTTPStatus.GONE

    with transaction_boundary(factory) as session:
        event_types = list(session.execute(sa.select(event_log_table.c.event_type)).scalars())
        assert event_types.count("handoff.accepted") == 1
        assert event_types.count("handoff.consumed") == 1
        assert "handoff.declined" in event_types
        assert "handoff.expired" in event_types


def test_handoff_api_persists_failed_acceptance_and_openapi_contract(tmp_path: Path) -> None:
    factory = _build_session_factory(tmp_path)
    app = _create_test_app(factory)
    with transaction_boundary(factory) as session:
        source_id, artifact_id = _seed_source(session)
    created = _create(app, source_id, artifact_id).json()
    with transaction_boundary(factory) as session:
        session.execute(
            sa.update(product_handoffs_table)
            .where(product_handoffs_table.c.id == created["handoff_id"])
            .values(target_product_id="missing_product")
        )
    failed = asyncio.run(
        _request(app, "POST", f"/v1/handoffs/{created['handoff_token']}/accept", {})
    )
    assert failed.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert failed.json()["error"]["code"] == "handoff_acceptance_failed"
    with transaction_boundary(factory) as session:
        row = (
            session.execute(
                sa.select(product_handoffs_table).where(
                    product_handoffs_table.c.id == created["handoff_id"]
                )
            )
            .mappings()
            .one()
        )
        assert row["status"] == "failed"
        assert (
            session.execute(
                sa.select(sa.func.count())
                .select_from(event_log_table)
                .where(
                    event_log_table.c.event_type == "handoff.failed",
                    event_log_table.c.handoff_id == created["handoff_id"],
                )
            ).scalar_one()
            == 1
        )

    paths = app.openapi()["paths"]
    assert "/v1/handoffs" in paths
    assert "/v1/handoffs/{handoff_token}" in paths
    assert "/v1/handoffs/{handoff_token}/accept" in paths
    assert "/v1/handoffs/{handoff_token}/decline" in paths


def test_immediate_handoff_quota_exhaustion_is_durable_and_safe(tmp_path: Path) -> None:
    factory = _build_session_factory(tmp_path)
    app = _create_test_app(factory)
    registry = app.state.runtime.config_registry
    policy = registry.get_quota_policy("kernel_demo.guest_quota_v1")
    assert policy is not None
    app.state.runtime = replace(
        app.state.runtime,
        config_registry=replace(
            registry,
            quotas={
                **dict(registry.quotas),
                policy.quota_policy_id: replace(policy, limit_count=0),
            },
        ),
    )
    with transaction_boundary(factory) as session:
        source_id, artifact_id = _seed_source(session)

    created = _create(app, source_id, artifact_id).json()
    rejected = asyncio.run(
        _request(
            app,
            "POST",
            f"/v1/handoffs/{created['handoff_token']}/accept",
            {},
        )
    )

    assert rejected.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert rejected.json() == {
        "error": {
            "code": "quota_exhausted",
            "message": "Guest quota exhausted.",
            "request_id": "req_handoff",
        }
    }

    with transaction_boundary(factory) as session:
        handoff = (
            session.execute(
                sa.select(product_handoffs_table).where(
                    product_handoffs_table.c.id == created["handoff_id"]
                )
            )
            .mappings()
            .one()
        )
        usage = session.execute(sa.select(guest_quota_usage_table)).mappings().one()
        quota_events = list(
            session.execute(
                sa.select(event_log_table)
                .where(event_log_table.c.handoff_id == created["handoff_id"])
                .where(event_log_table.c.event_type.like("quota.%"))
                .order_by(event_log_table.c.timestamp, event_log_table.c.event_id)
            ).mappings()
        )
        linked_target_count = session.execute(
            sa.select(sa.func.count())
            .select_from(scenario_sessions_table)
            .where(scenario_sessions_table.c.parent_scenario_session_id == source_id)
        ).scalar_one()
        handoff_event_types = list(
            session.execute(
                sa.select(event_log_table.c.event_type).where(
                    event_log_table.c.handoff_id == created["handoff_id"]
                )
            ).scalars()
        )

    assert handoff["status"] == "failed"
    assert handoff["error_code"] == "quota_exhausted"
    assert handoff["target_scenario_session_id"] is None
    assert handoff["target_job_id"] is None
    assert usage["limit_count"] == 0
    assert usage["used_count"] == 0
    assert [event["event_type"] for event in quota_events] == [
        "quota.checked",
        "quota.exhausted",
    ]
    assert quota_events[-1]["error_code"] == "quota_exhausted"
    assert quota_events[-1]["properties"]["exhausted"] is True
    assert linked_target_count == 0
    assert "handoff.accepted" not in handoff_event_types
    assert handoff_event_types.count("handoff.failed") == 1


def test_immediate_handoff_worker_keeps_target_runtime_lineage(tmp_path: Path) -> None:
    factory = _build_session_factory(tmp_path)
    app = _create_test_app(factory)
    with transaction_boundary(factory) as session:
        source_id, artifact_id = _seed_source(session)
    created = _create(app, source_id, artifact_id).json()
    accepted = asyncio.run(
        _request(app, "POST", f"/v1/handoffs/{created['handoff_token']}/accept", {})
    ).json()
    worker = build_worker(
        session_factory=factory,
        config_root=CONFIG_ROOT,
        provider_adapters={"fake": FakeProviderAdapter(FIXTURE_ROOT)},
    )
    processed = asyncio.run(worker.process_next_job())
    assert processed is not None
    assert processed.id == accepted["target_job_id"]
    assert processed.scenario_session_id == accepted["target_scenario_session_id"]
    assert processed.status is JobStatus.succeeded

    with transaction_boundary(factory) as session:
        action_run = (
            session.execute(
                sa.select(action_runs_table).where(action_runs_table.c.job_id == processed.id)
            )
            .mappings()
            .one()
        )
        provider_call = (
            session.execute(
                sa.select(provider_calls_table).where(provider_calls_table.c.job_id == processed.id)
            )
            .mappings()
            .one()
        )
        workflow_events = list(
            session.execute(
                sa.select(event_log_table).where(event_log_table.c.job_id == processed.id)
            ).mappings()
        )
    assert action_run["scenario_session_id"] == accepted["target_scenario_session_id"]
    assert provider_call["scenario_session_id"] == accepted["target_scenario_session_id"]
    assert all(
        event["scenario_session_id"] == accepted["target_scenario_session_id"]
        for event in workflow_events
    )
    assert all(event["handoff_id"] == created["handoff_id"] for event in workflow_events), [
        (event["event_type"], event["handoff_id"])
        for event in workflow_events
        if event["handoff_id"] != created["handoff_id"]
    ]
