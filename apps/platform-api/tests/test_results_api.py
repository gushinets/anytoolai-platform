from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

import httpx
import pytest
from anytoolai_platform_core.artifacts.models import ArtifactRecord, ArtifactStatus
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord, ScenarioSessionStatus
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.transactions import (
    SessionFactory,
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from test_scenario_runtime_api import _create_test_app

from tests.db_support import provision_database

pytestmark = [pytest.mark.postgresql, pytest.mark.slow]

WORKFLOW_ID = "kernel_demo.single_action_extract_v1"
WORKFLOW_VERSION = 1
SCHEMA_REF = "kernel_demo.extract_output_v1"
SCHEMA_VERSION = 1


@pytest.fixture
def session_factory() -> Iterator[SessionFactory]:
    with provision_database(
        database_name_prefix="anytoolai_results_api_test",
        skip_reason="PostgreSQL results API coverage",
    ) as (engine, _alembic_config, _database_url):
        yield build_session_factory(engine)


def _seed_result(
    session,
    *,
    tenant_id: str = "anytoolai",
    region: str = "default",
    artifact_type: str = "structured_output",
    action_run_id: str | None = None,
    content_json: Any = None,
    metadata_overrides: dict[str, Any] | None = None,
    job_status: JobStatus = JobStatus.succeeded,
) -> tuple[str, str, str]:
    scenario = ScenarioSessionRepository(session).create(
        ScenarioSessionRecord(
            tenant_id=tenant_id,
            region=region,
            product_id="kernel_demo",
            frontend_id="kernel_demo_ce",
            scenario_id="kernel_demo.handoff_smoke_source_v1",
            scenario_version=1,
            guest_id="guest_demo",
            status=ScenarioSessionStatus.completed,
            current_checkpoint_id="result_ready",
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
            workflow_id=WORKFLOW_ID,
            workflow_version=WORKFLOW_VERSION,
        )
    )
    job = jobs.claim_created(job.id)
    assert job is not None
    metadata = {
        "artifact_role": "workflow_result",
        "schema_ref": SCHEMA_REF,
        "schema_version": SCHEMA_VERSION,
        "workflow_id": job.workflow_id,
        "workflow_version": job.workflow_version,
    }
    metadata.update(metadata_overrides or {})
    artifact = ArtifactRepository(session).create(
        ArtifactRecord(
            tenant_id=scenario.tenant_id,
            region=scenario.region,
            product_id=scenario.product_id,
            frontend_id=scenario.frontend_id,
            scenario_session_id=scenario.id,
            job_id=job.id,
            action_run_id=action_run_id,
            artifact_type=artifact_type,
            status=ArtifactStatus.stored,
            content_json=(
                {"deadline": "2026-08-30", "fields": ["budget", "deliverables"]}
                if content_json is None
                else content_json
            ),
            metadata=metadata,
        )
    )
    if job_status is JobStatus.succeeded:
        jobs.mark_succeeded(
            replace(
                job,
                status=JobStatus.succeeded,
                result_artifact_id=artifact.id,
                completed_at=datetime.now(UTC),
            )
        )
    return scenario.id, job.id, artifact.id


async def _request(app, method: str, path: str) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        return await client.request(method, path, headers={"X-Request-ID": "req_results"})


def test_get_result_artifact_returns_frontend_safe_canonical_result(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)
    with transaction_boundary(session_factory) as session:
        scenario_id, job_id, artifact_id = _seed_result(session)

    response = asyncio.run(_request(app, "GET", f"/v1/results/{artifact_id}"))
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body == {
        "result_artifact_id": artifact_id,
        "scenario_session_id": scenario_id,
        "job_id": job_id,
        "workflow_id": WORKFLOW_ID,
        "workflow_version": WORKFLOW_VERSION,
        "schema_ref": SCHEMA_REF,
        "schema_version": SCHEMA_VERSION,
        "created_at": body["created_at"],
        "output": {"deadline": "2026-08-30", "fields": ["budget", "deliverables"]},
    }
    # frontend-safe: no raw/debug internals, prompts, or provider/model identifiers leak.
    for forbidden in ("prompt", "provider", "model", "litellm", "pydantic_run_id", "metadata"):
        assert forbidden not in response.text.lower()

    paths = app.openapi()["paths"]
    assert "/v1/results/{result_artifact_id}" in paths


def test_get_result_artifact_unknown_id_fails_safely(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)
    response = asyncio.run(_request(app, "GET", "/v1/results/artifact_does_not_exist"))
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "result_artifact_not_found"


def test_get_result_artifact_out_of_tenant_scope_fails_safely(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)
    with transaction_boundary(session_factory) as session:
        _, _, artifact_id = _seed_result(session, tenant_id="other_tenant")

    response = asyncio.run(_request(app, "GET", f"/v1/results/{artifact_id}"))
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "result_artifact_not_found"


def test_get_result_artifact_rejects_raw_debug_artifact(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)
    with transaction_boundary(session_factory) as session:
        scenario_id, job_id, _canonical_artifact_id = _seed_result(session)
        debug_artifact = ArtifactRepository(session).create(
            ArtifactRecord(
                tenant_id="anytoolai",
                region="default",
                product_id="kernel_demo",
                frontend_id="kernel_demo_ce",
                scenario_session_id=scenario_id,
                job_id=job_id,
                action_run_id="action_run_debug",
                artifact_type="structured_output_debug_raw",
                status=ArtifactStatus.stored,
                content_json={"raw_provider_payload": "should never be frontend-safe"},
                metadata={"artifact_role": "raw_debug"},
            )
        )

    response = asyncio.run(_request(app, "GET", f"/v1/results/{debug_artifact.id}"))
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "result_artifact_unavailable"


def test_get_result_artifact_rejects_schema_version_drift(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)
    with transaction_boundary(session_factory) as session:
        _, _, artifact_id = _seed_result(
            session,
            metadata_overrides={"schema_version": 999},
        )

    response = asyncio.run(_request(app, "GET", f"/v1/results/{artifact_id}"))
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "result_artifact_unavailable"


def test_get_result_artifact_rejects_non_object_content(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)
    with transaction_boundary(session_factory) as session:
        _, _, artifact_id = _seed_result(session, content_json=["not", "an", "object"])

    response = asyncio.run(_request(app, "GET", f"/v1/results/{artifact_id}"))
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "result_artifact_unavailable"


def test_get_result_artifact_rejects_unfinished_job(session_factory: SessionFactory) -> None:
    app = _create_test_app(session_factory)
    with transaction_boundary(session_factory) as session:
        _, _, artifact_id = _seed_result(session, job_status=JobStatus.running)

    response = asyncio.run(_request(app, "GET", f"/v1/results/{artifact_id}"))
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "result_artifact_unavailable"


def test_get_result_artifact_workflow_version_reflects_job_not_live_config(
    session_factory: SessionFactory,
) -> None:
    # A config redeploy can bump a workflow's version in the live registry after a job ran.
    # The response must report the version the job actually ran under (job.workflow_version),
    # not whatever the current registry happens to say for that workflow_id today.
    app = _create_test_app(session_factory)
    with transaction_boundary(session_factory) as session:
        _, _, artifact_id = _seed_result(session)

    registry = app.state.runtime.config_registry
    workflow = registry.get_workflow(WORKFLOW_ID)
    assert workflow is not None
    app.state.runtime = replace(
        app.state.runtime,
        config_registry=replace(
            registry,
            workflows={**registry.workflows, WORKFLOW_ID: replace(workflow, version=2)},
        ),
    )

    response = asyncio.run(_request(app, "GET", f"/v1/results/{artifact_id}"))
    assert response.status_code == HTTPStatus.OK
    assert response.json()["workflow_version"] == WORKFLOW_VERSION
