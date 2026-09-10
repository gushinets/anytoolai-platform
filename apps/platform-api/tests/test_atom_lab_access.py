from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path

import httpx
import pytest
import sqlalchemy as sa
from anytoolai_platform_api.bootstrap import RuntimeStorageDependencies
from anytoolai_platform_api.main import create_app
from anytoolai_platform_core.artifacts.models import ArtifactRecord, ArtifactStatus
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord, ScenarioSessionStatus
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.db import scenario_sessions_table
from anytoolai_platform_core.storage.transactions import SessionFactory, transaction_boundary
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from pydantic import BaseModel, ConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
ACCESS_CODE = "atom-lab-test-code"


class _ValidationProbe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int


async def _request(
    app,
    path: str,
    *,
    method: str = "GET",
    json: dict[str, object] | None = None,
    access_code: str | None = None,
    request_id: str = "req_atom_lab",
) -> httpx.Response:
    headers = {"X-Request-ID": request_id}
    if access_code is not None:
        headers["X-Atom-Lab-Access-Code"] = access_code
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        return await client.request(method, path, headers=headers, json=json)


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANYTOOLAI_ATOM_LAB_ACCESS_CODE", ACCESS_CODE)
    return create_app(config_root=CONFIG_ROOT)


@pytest.fixture
def stored_app(app, session_factory: SessionFactory):
    app.state.runtime = replace(
        app.state.runtime,
        storage=RuntimeStorageDependencies(session_factory=session_factory),
    )
    return app


@pytest.mark.parametrize("access_code", [None, "wrong-code"])
def test_atom_lab_catalog_rejects_missing_or_wrong_access_code(
    app, access_code: str | None
) -> None:
    response = asyncio.run(
        _request(app, "/v1/atom-lab/atoms", access_code=access_code, request_id="req_denied")
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {
        "error": {
            "code": "atom_lab_access_denied",
            "message": "Доступ к Atom Lab запрещён.",
            "field_errors": [],
        },
        "request_id": "req_denied",
    }
    assert ACCESS_CODE not in response.text


def test_atom_lab_catalog_fails_closed_without_server_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANYTOOLAI_ATOM_LAB_ACCESS_CODE", raising=False)
    application = create_app(config_root=CONFIG_ROOT)

    response = asyncio.run(
        _request(
            application,
            "/v1/atom-lab/atoms",
            access_code=ACCESS_CODE,
            request_id="req_unavailable",
        )
    )

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json() == {
        "error": {
            "code": "atom_lab_unavailable",
            "message": "Atom Lab недоступен.",
            "field_errors": [],
        },
        "request_id": "req_unavailable",
    }


def test_atom_lab_catalog_returns_protected_registry_data(app) -> None:
    response = asyncio.run(_request(app, "/v1/atom-lab/atoms", access_code=ACCESS_CODE))

    assert response.status_code == HTTPStatus.OK
    assert [item["atom_id"] for item in response.json()] == [
        "A01",
        "A02",
        "A03",
        "A04",
        "A05",
        "A06",
        "A07",
        "A08",
        "A09",
        "A10",
        "A11",
    ]
    assert response.json()[0]["prompt"]

    detail = asyncio.run(_request(app, "/v1/atom-lab/atoms/A10", access_code=ACCESS_CODE))
    assert detail.status_code == HTTPStatus.OK
    assert detail.json()["atom_id"] == "A10"


def test_atom_lab_unknown_atom_uses_safe_error_envelope(app) -> None:
    response = asyncio.run(
        _request(
            app,
            "/v1/atom-lab/atoms/A99",
            access_code=ACCESS_CODE,
            request_id="req_unknown",
        )
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {
        "error": {
            "code": "atom_not_found",
            "message": "Атом не найден.",
            "field_errors": [],
        },
        "request_id": "req_unknown",
    }


def test_atom_lab_request_validation_uses_the_lab_error_envelope(app) -> None:
    @app.post("/v1/atom-lab/validation-probe")
    def validation_probe(payload: _ValidationProbe) -> dict[str, int]:
        return {"count": payload.count}

    response = asyncio.run(
        _request(
            app,
            "/v1/atom-lab/validation-probe",
            method="POST",
            json={"count": "not-an-integer", "secret_input": "must-not-be-echoed"},
            request_id="req_validation",
        )
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json() == {
        "error": {
            "code": "request_validation_failed",
            "message": "Проверка запроса не пройдена.",
            "field_errors": [
                {"path": "count", "message": "Недопустимое значение."},
                {"path": "secret_input", "message": "Недопустимое значение."},
            ],
        },
        "request_id": "req_validation",
    }
    assert "must-not-be-echoed" not in response.text


def test_atom_lab_shell_is_public_but_contains_no_protected_catalog_data(app) -> None:
    page = asyncio.run(_request(app, "/atom-lab"))
    styles = asyncio.run(_request(app, "/atom-lab/atom_lab.css"))
    script = asyncio.run(_request(app, "/atom-lab/atom_lab.js"))

    assert page.status_code == HTTPStatus.OK
    assert styles.status_code == HTTPStatus.OK
    assert script.status_code == HTTPStatus.OK
    assert '<input id="access-code" type="password"' in page.text
    assert '<script src="/atom-lab/atom_lab.js" defer></script>' in page.text
    assert "X-Atom-Lab-Access-Code" in script.text
    assert "textContent" in script.text
    for forbidden in (
        "localStorage",
        "sessionStorage",
        "document.cookie",
        "console.log",
        "kernel.schemas.extract_input_v1",
        "kernel_demo.extract_structured_fields.v1",
        "Извлекает из исходного текста значения полей",
    ):
        assert forbidden not in page.text
        assert forbidden not in script.text


def test_atom_lab_routes_do_not_remove_the_existing_demo(app) -> None:
    assert asyncio.run(_request(app, "/demo")).status_code == HTTPStatus.OK
    assert "/v1/demo/runs" in app.openapi()["paths"]
    assert "/v1/atom-lab/atoms" in app.openapi()["paths"]
    assert "/v1/atom-lab/atoms/{atom_id}" in app.openapi()["paths"]


def _seed_result(session_factory: SessionFactory, *, runtime_scope: str | None) -> tuple[str, str]:
    metadata = {} if runtime_scope is None else {"runtime_scope": runtime_scope}
    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).create(
            ScenarioSessionRecord(
                tenant_id="anytoolai",
                region="default",
                product_id="kernel_demo",
                frontend_id="kernel_demo_ce",
                scenario_id="kernel_demo.handoff_smoke_source_v1",
                scenario_version=1,
                guest_id="guest_atom_lab_scope",
                status=ScenarioSessionStatus.completed,
                current_checkpoint_id="result_ready",
                metadata=metadata,
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
                content_json={"values": {"deadline": "2026-09-30"}, "missing_fields": []},
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


def _public_request(
    app,
    method: str,
    path: str,
    json: dict[str, object] | None = None,
) -> httpx.Response:
    return asyncio.run(_request(app, path, method=method, json=json))


def test_public_session_and_result_routes_hide_seeded_lab_resources(
    stored_app, session_factory: SessionFactory
) -> None:
    scenario_id, artifact_id = _seed_result(session_factory, runtime_scope="atom_lab")

    session_response = _public_request(stored_app, "GET", f"/v1/scenario-sessions/{scenario_id}")
    next_action_response = _public_request(
        stored_app,
        "POST",
        f"/v1/scenario-sessions/{scenario_id}/next-actions/copy_result",
        {"checkpoint_id": "result_ready"},
    )
    result_response = _public_request(stored_app, "GET", f"/v1/results/{artifact_id}")

    assert session_response.status_code == HTTPStatus.NOT_FOUND
    assert session_response.json()["error"]["code"] == "scenario_session_not_found"
    assert next_action_response.status_code == HTTPStatus.NOT_FOUND
    assert next_action_response.json()["error"]["code"] == "scenario_session_not_found"
    assert result_response.status_code == HTTPStatus.NOT_FOUND
    assert result_response.json()["error"]["code"] == "result_artifact_not_found"
    assert "2026-09-30" not in result_response.text


def test_public_routes_keep_ordinary_results_available_and_fail_closed_on_unknown_scope(
    stored_app, session_factory: SessionFactory
) -> None:
    public_session_id, public_artifact_id = _seed_result(session_factory, runtime_scope=None)
    unknown_session_id, unknown_artifact_id = _seed_result(
        session_factory, runtime_scope="unrecognized_internal_scope"
    )

    public_session = _public_request(
        stored_app, "GET", f"/v1/scenario-sessions/{public_session_id}"
    )
    public_result = _public_request(stored_app, "GET", f"/v1/results/{public_artifact_id}")
    unknown_session = _public_request(
        stored_app, "GET", f"/v1/scenario-sessions/{unknown_session_id}"
    )
    unknown_result = _public_request(stored_app, "GET", f"/v1/results/{unknown_artifact_id}")

    assert public_session.status_code == HTTPStatus.OK
    assert public_result.status_code == HTTPStatus.OK
    assert public_result.json()["output"]["values"]["deadline"] == "2026-09-30"
    assert unknown_session.status_code == HTTPStatus.NOT_FOUND
    assert unknown_result.status_code == HTTPStatus.NOT_FOUND


def test_public_start_cannot_forge_atom_lab_runtime_scope(
    stored_app, session_factory: SessionFactory
) -> None:
    before = _scenario_count(session_factory)
    response = _public_request(
        stored_app,
        "POST",
        "/v1/products/kernel_demo/scenarios/kernel_demo.single_action_smoke_v1/start",
        {
            "frontend_id": "kernel_demo_ce",
            "input": {"source_text": "test"},
            "runtime_scope": "atom_lab",
            "metadata": {"runtime_scope": "atom_lab"},
        },
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "request_validation_failed"
    assert _scenario_count(session_factory) == before


def test_public_handoff_routes_hide_lab_source_and_known_token(
    stored_app, session_factory: SessionFactory
) -> None:
    scenario_id, artifact_id = _seed_result(session_factory, runtime_scope=None)
    created = _public_request(
        stored_app,
        "POST",
        "/v1/handoffs",
        {
            "handoff_definition_id": "kernel_demo_source_to_target_v1",
            "source_scenario_session_id": scenario_id,
            "source_artifact_id": artifact_id,
        },
    )
    assert created.status_code == HTTPStatus.OK
    token = created.json()["handoff_token"]

    with transaction_boundary(session_factory) as session:
        session.execute(
            sa.update(scenario_sessions_table)
            .where(scenario_sessions_table.c.id == scenario_id)
            .values(metadata={"runtime_scope": "atom_lab"})
        )

    repeated_create = _public_request(
        stored_app,
        "POST",
        "/v1/handoffs",
        {
            "handoff_definition_id": "kernel_demo_source_to_target_v1",
            "source_scenario_session_id": scenario_id,
            "source_artifact_id": artifact_id,
        },
    )
    assert repeated_create.status_code == HTTPStatus.NOT_FOUND
    assert repeated_create.json()["error"]["code"] == "handoff_source_invalid"

    for method, suffix in (("GET", ""), ("POST", "/accept"), ("POST", "/decline")):
        response = _public_request(stored_app, method, f"/v1/handoffs/{token}{suffix}", {})
        assert response.status_code == HTTPStatus.NOT_FOUND
        assert response.json()["error"]["code"] == "handoff_not_found"


def _scenario_count(session_factory: SessionFactory) -> int:
    with transaction_boundary(session_factory) as session:
        return session.execute(
            sa.select(sa.func.count()).select_from(scenario_sessions_table)
        ).scalar_one()
