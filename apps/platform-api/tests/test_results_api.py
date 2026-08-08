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
                {"title": "Extracted", "fields": ["budget", "deliverables"]}
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
        "output": {"title": "Extracted", "fields": ["budget", "deliverables"]},
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


def test_get_result_artifact_out_of_region_scope_fails_safely(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)
    with transaction_boundary(session_factory) as session:
        _, _, artifact_id = _seed_result(session, region="other_region")

    response = asyncio.run(_request(app, "GET", f"/v1/results/{artifact_id}"))
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "result_artifact_not_found"


def test_get_result_artifact_rejects_raw_debug_artifact(session_factory: SessionFactory) -> None:
    # The job's result_artifact_id must point at the tested artifact itself, otherwise the
    # canonical guard rejects it on `job.result_artifact_id != artifact.id` before ever
    # evaluating `artifact_type`, making this test pass even if the artifact-type guard broke.
    app = _create_test_app(session_factory)
    with transaction_boundary(session_factory) as session:
        _, _, artifact_id = _seed_result(session, artifact_type="structured_output_debug_raw")

    response = asyncio.run(_request(app, "GET", f"/v1/results/{artifact_id}"))
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "result_artifact_unavailable"


def test_get_result_artifact_rejects_action_scoped_artifact(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)
    with transaction_boundary(session_factory) as session:
        _, _, artifact_id = _seed_result(session, action_run_id="action_run_demo")

    response = asyncio.run(_request(app, "GET", f"/v1/results/{artifact_id}"))
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "result_artifact_unavailable"


def test_get_result_artifact_rejects_non_workflow_result_role(
    session_factory: SessionFactory,
) -> None:
    app = _create_test_app(session_factory)
    with transaction_boundary(session_factory) as session:
        _, _, artifact_id = _seed_result(
            session, metadata_overrides={"artifact_role": "raw_debug"}
        )

    response = asyncio.run(_request(app, "GET", f"/v1/results/{artifact_id}"))
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "result_artifact_unavailable"


def test_get_result_artifact_rejects_artifact_job_scope_mismatch(
    session_factory: SessionFactory,
) -> None:
    # The artifact lookup is tenant/region-scoped, but the linked job was previously loaded
    # globally by job_id with no comparison of tenant/region/product/frontend against the
    # artifact. Simulate a corrupted/cross-scope pairing directly at the repository layer
    # (job creation enforces its own tenant/region/product/frontend against the scenario
    # session, so the mismatch must be introduced on the artifact instead) to prove the
    # canonical guard now rejects it.
    app = _create_test_app(session_factory)
    with transaction_boundary(session_factory) as session:
        _, job_id, canonical_artifact_id = _seed_result(session)
        canonical_artifact = ArtifactRepository(session).get(canonical_artifact_id)
        assert canonical_artifact is not None
        mismatched_artifact = ArtifactRepository(session).create(
            replace(
                canonical_artifact,
                id=f"{canonical_artifact_id}_mismatch",
                product_id="other_product",
            )
        )
        jobs = JobRepository(session)
        job = jobs.get(job_id)
        assert job is not None
        jobs.update(replace(job, result_artifact_id=mismatched_artifact.id))
        artifact_id = mismatched_artifact.id

    response = asyncio.run(_request(app, "GET", f"/v1/results/{artifact_id}"))
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


def test_get_result_artifact_rejects_content_violating_output_schema(
    session_factory: SessionFactory,
) -> None:
    # The configured kernel_demo.extract_output_v1 schema is permissive
    # ({"type": "object", "additionalProperties": true}), so no dict can violate it as
    # shipped. Tighten it in the live registry (same technique as the workflow-version
    # drift test above) to exercise the real jsonschema re-validation failure path in
    # resolve_canonical_workflow_result, not just the isinstance(..., Mapping) guard.
    app = _create_test_app(session_factory)
    with transaction_boundary(session_factory) as session:
        _, _, artifact_id = _seed_result(session, content_json={"unexpected": "shape"})

    registry = app.state.runtime.config_registry
    schema = registry.get_schema(SCHEMA_REF)
    assert schema is not None
    app.state.runtime = replace(
        app.state.runtime,
        config_registry=replace(
            registry,
            schemas={
                **registry.schemas,
                SCHEMA_REF: replace(
                    schema,
                    schema={
                        "type": "object",
                        "required": ["title"],
                        "properties": {"title": {"type": "string"}},
                    },
                ),
            },
        ),
    )

    response = asyncio.run(_request(app, "GET", f"/v1/results/{artifact_id}"))
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "result_artifact_unavailable"


def test_get_result_artifact_allows_generic_words_as_key_substrings(
    session_factory: SessionFactory,
) -> None:
    # The denylist backstop matches the *whole* normalized key, not a substring, so a legitimate
    # field like `car_model` or `insurance_provider` is never mistaken for a leaked
    # provider/model identifier.
    app = _create_test_app(session_factory)
    with transaction_boundary(session_factory) as session:
        _, _, artifact_id = _seed_result(
            session,
            content_json={
                "title": "Extracted",
                "fields": ["budget"],
                "car_model": "Model X",
                "insurance_provider": "Acme Insurance",
            },
        )

    response = asyncio.run(_request(app, "GET", f"/v1/results/{artifact_id}"))
    assert response.status_code == HTTPStatus.OK
    assert response.json()["output"]["car_model"] == "Model X"


def test_get_result_artifact_allows_domain_fields_containing_a_marker_as_substring(
    session_factory: SessionFactory,
) -> None:
    # Whole-key matching must not collide with legitimate compound domain fields that happen to
    # contain a denylist marker as a substring (e.g. `model_id` inside `vehicle_model_id`). A
    # prior substring-based matcher would have 404'd all of these.
    app = _create_test_app(session_factory)
    with transaction_boundary(session_factory) as session:
        _, _, artifact_id = _seed_result(
            session,
            content_json={
                "title": "Extracted",
                "fields": ["budget"],
                "vehicle_model_id": "vin-123",
                "car_model_version": "2024",
                "insurance_provider_name": "Acme Insurance",
                "business_trace_id": "biz-456",
            },
        )

    response = asyncio.run(_request(app, "GET", f"/v1/results/{artifact_id}"))
    assert response.status_code == HTTPStatus.OK
    output = response.json()["output"]
    assert output["vehicle_model_id"] == "vin-123"
    assert output["car_model_version"] == "2024"
    assert output["insurance_provider_name"] == "Acme Insurance"
    assert output["business_trace_id"] == "biz-456"


@pytest.mark.parametrize(
    "key",
    ["prompt", "provider", "model", "provider_call_id", "gateway_model"],
)
def test_get_result_artifact_rejects_bare_internal_field_names(
    session_factory: SessionFactory,
    key: str,
) -> None:
    # These are the actual bare internal field names used for provider/prompt lineage elsewhere
    # in the platform (`providers/models.py`, `context/execution_context.py`). A prior denylist
    # deliberately left bare words off to avoid false-positiving on `car_model`/
    # `insurance_provider`, which also let these exact internal names through undetected.
    app = _create_test_app(session_factory)
    with transaction_boundary(session_factory) as session:
        _, _, artifact_id = _seed_result(
            session,
            content_json={
                "title": "Extracted",
                "fields": ["budget"],
                key: "leaked-internal-value",
            },
        )

    response = asyncio.run(_request(app, "GET", f"/v1/results/{artifact_id}"))
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "result_artifact_unavailable"


@pytest.mark.parametrize(
    "key",
    ["provider-model", "providerModel", "ProviderModel", "pydantic-run-id", "pydanticRunId"],
)
def test_get_result_artifact_rejects_leak_shaped_key_variants(
    session_factory: SessionFactory,
    key: str,
) -> None:
    # The denylist matcher must normalize hyphen/underscore/camelCase separators before
    # matching, otherwise a schema-valid key like `provider-model` or `providerModel` bypasses
    # the underscore-form marker `provider_model` entirely.
    app = _create_test_app(session_factory)
    with transaction_boundary(session_factory) as session:
        _, _, artifact_id = _seed_result(
            session,
            content_json={
                "title": "Extracted",
                "fields": ["budget"],
                key: "leaked-internal-model-id",
            },
        )

    response = asyncio.run(_request(app, "GET", f"/v1/results/{artifact_id}"))
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "result_artifact_unavailable"


def test_get_result_artifact_rejects_leak_shaped_content_under_open_schema(
    session_factory: SessionFactory,
) -> None:
    # The shipped kernel_demo.extract_output_v1 workflow output schema is
    # `{"type": "object", "additionalProperties": true}`, so schema-valid content can still
    # carry a provider/prompt-shaped key the schema never restricted. Unlike handoffs (which
    # only ever expose an explicit per-field allowlist mapping), this endpoint returns the
    # full normalized output object, so ResultService applies its own denylist backstop.
    app = _create_test_app(session_factory)
    with transaction_boundary(session_factory) as session:
        _, _, artifact_id = _seed_result(
            session,
            content_json={
                "title": "Extracted",
                "fields": ["budget"],
                "provider_model": "leaked-internal-model-id",
            },
        )

    response = asyncio.run(_request(app, "GET", f"/v1/results/{artifact_id}"))
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "result_artifact_unavailable"
    assert "leaked-internal-model-id" not in response.text


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
