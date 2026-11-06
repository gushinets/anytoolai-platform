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
from anytoolai_platform_core.identity.models import GuestIdentityRecord
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord, ScenarioSessionStatus
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.db import event_log_table, scenario_sessions_table
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
    raise_app_exceptions: bool = True,
    base_url: str = "http://testserver",
    origin: str | None = None,
) -> httpx.Response:
    headers = {"X-Request-ID": request_id}
    if origin is not None:
        headers["Origin"] = origin
    if access_code is not None:
        headers["X-Atom-Lab-Access-Code"] = access_code
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=raise_app_exceptions),
        base_url=base_url,
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


@pytest.mark.parametrize(
    "base_url", ["http://127.0.0.1:8000", "http://localhost:8000", "http://[::1]:8000"]
)
def test_explicit_local_open_access_loads_catalog_without_code(app, monkeypatch, base_url) -> None:
    monkeypatch.setenv("ANYTOOLAI_ATOM_LAB_AUTH_DISABLED", "true")
    monkeypatch.delenv("ANYTOOLAI_ATOM_LAB_ACCESS_CODE")
    catalog = asyncio.run(_request(app, "/v1/atom-lab/atoms", base_url=base_url, origin=base_url))
    assert catalog.status_code == HTTPStatus.OK
    assert len(catalog.json()) == 11
    cli_catalog = asyncio.run(_request(app, "/v1/atom-lab/atoms", base_url=base_url))
    assert cli_catalog.status_code == HTTPStatus.OK
    page = asyncio.run(_request(app, "/atom-lab"))
    assert 'id="access-panel" data-auto-open="true" hidden' in page.text
    assert page.headers["cache-control"] == "no-store"
    invalid_run = asyncio.run(_request(
        app, "/v1/atom-lab/runs", method="POST", json={}, base_url=base_url, origin=base_url,
    ))
    assert invalid_run.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.parametrize("base_url,origin", [
    ("http://127.0.0.1:8000", "chrome-extension://" + "a" * 32),
    ("http://127.0.0.1:8000", "https://untrusted.example"),
    ("http://127.0.0.1:8000", "http://127.0.0.1:9000"),
    ("http://127.0.0.1:8000", "http://localhost:8000"),
    ("http://127.0.0.1:8000", "null"),
    ("http://rebound.example:8000", None),
    ("http://rebound.example:8000", "http://rebound.example:8000"),
    ("http://localhost.untrusted.example", None),
])
@pytest.mark.parametrize("method,path", [
    ("GET", "/v1/atom-lab/atoms"),
    ("GET", "/v1/atom-lab/atoms/A07/prompts"),
    ("GET", "/v1/atom-lab/runs"),
    ("POST", "/v1/atom-lab/runs"),
    ("POST", "/v1/atom-lab/presets"),
    ("POST", "/v1/atom-lab/atoms/A07/prompts"),
])
def test_local_open_access_rejects_untrusted_host_or_origin(
    app, monkeypatch, base_url, origin, method, path,
) -> None:
    monkeypatch.setenv("ANYTOOLAI_ATOM_LAB_AUTH_DISABLED", "true")
    response = asyncio.run(_request(
        app, path, method=method, json={} if method == "POST" else None,
        base_url=base_url, origin=origin,
    ))
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["error"]["code"] == (
        "access_denied" if path == "/v1/atom-lab/runs" else "atom_lab_access_denied"
    )
    assert "prompt_ref" not in response.text


def test_code_protected_remote_access_keeps_working(app) -> None:
    response = asyncio.run(_request(
        app, "/v1/atom-lab/atoms", access_code=ACCESS_CODE,
        base_url="https://lab.example", origin="https://lab.example",
    ))
    assert response.status_code == HTTPStatus.OK


@pytest.mark.parametrize("content_length", [None, "1048576"])
@pytest.mark.parametrize("malformed", [False, True])
@pytest.mark.parametrize("access_mode", [
    "missing-code", "wrong-code", "untrusted-host", "untrusted-origin",
])
def test_saved_prompt_denies_access_without_consuming_body(
    app, monkeypatch, content_length, malformed, access_mode,
) -> None:
    consumed = []
    headers = {"Content-Type": "application/json"}
    base_url = "http://127.0.0.1:8000"
    if content_length is not None:
        headers["Content-Length"] = content_length
    if access_mode == "wrong-code":
        headers["X-Atom-Lab-Access-Code"] = "wrong"
    if access_mode.startswith("untrusted-"):
        monkeypatch.setenv("ANYTOOLAI_ATOM_LAB_AUTH_DISABLED", "true")
        if access_mode == "untrusted-host":
            base_url = "http://rebound.example:8000"
        else:
            headers["Origin"] = "https://untrusted.example"

    async def request():
        async def body():
            for chunk in (b"{" if malformed else b'{"prompt":"', b"a" * 1048576, b'"}'):
                consumed.append(len(chunk))
                yield chunk

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=base_url,
        ) as client:
            return await client.post(
                "/v1/atom-lab/atoms/A07/prompts", headers=headers, content=body(),
            )

    response = asyncio.run(request())
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["error"]["code"] == "atom_lab_access_denied"
    assert consumed == []


def test_saved_prompt_bounded_body_preserves_openapi_contract(app) -> None:
    operation = app.openapi()["paths"]["/v1/atom-lab/atoms/{atom_id}/prompts"]["post"]
    assert operation["requestBody"] == {
        "required": True,
        "content": {"application/json": {"schema": {
            "title": "AtomLabPromptCreateRequest", "type": "object", "additionalProperties": False,
            "required": ["name", "prompt", "source_ref"],
            "properties": {
                "name": {"title": "Name", "type": "string", "minLength": 1, "maxLength": 80},
                "prompt": {"title": "Prompt", "type": "string", "minLength": 1},
                "source_ref": {
                    "title": "Source Ref", "type": "string", "minLength": 1, "maxLength": 128,
                    "pattern": "^[A-Za-z0-9_.-]+$",
                },
                "source_run_id": {
                    "title": "Source Run Id",
                    "anyOf": [
                        {"type": "string", "maxLength": 128, "pattern": "^[A-Za-z0-9_-]+$"},
                        {"type": "null"},
                    ],
                },
            },
        }}},
    }
    assert operation["responses"]["413"] == {
        "description": "Atom Lab payload is too large.",
        "content": {"application/json": {"schema": {
            "$ref": "#/components/schemas/AtomLabErrorResponse",
        }}},
    }


@pytest.mark.parametrize("value", ["false", "", "TRUE"])
def test_open_access_requires_explicit_true(app, monkeypatch, value) -> None:
    monkeypatch.setenv("ANYTOOLAI_ATOM_LAB_AUTH_DISABLED", value)
    assert asyncio.run(_request(app, "/v1/atom-lab/atoms")).status_code == HTTPStatus.UNAUTHORIZED


def test_atom_lab_models_use_atom_lab_error_envelope_when_storage_is_unavailable(app) -> None:
    response = asyncio.run(
        _request(
            app,
            "/v1/atom-lab/models",
            access_code=ACCESS_CODE,
            request_id="req_models_no_storage",
        )
    )

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json() == {
        "error": {
            "code": "runtime_storage_unavailable",
            "message": "Runtime storage is unavailable.",
            "field_errors": [],
        },
        "request_id": "req_models_no_storage",
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


@pytest.mark.parametrize(
    ("access_code", "expected_status"),
    [(ACCESS_CODE, HTTPStatus.OK), (None, HTTPStatus.UNAUTHORIZED)],
)
def test_atom_lab_protected_responses_are_not_stored_by_caches(
    app,
    access_code: str | None,
    expected_status: HTTPStatus,
) -> None:
    response = asyncio.run(_request(app, "/v1/atom-lab/atoms", access_code=access_code))

    assert response.status_code == expected_status
    assert response.headers["Cache-Control"] == "no-store"


def test_atom_lab_unhandled_error_response_is_not_stored_by_caches(app) -> None:
    @app.get("/v1/atom-lab/failure-probe")
    def failure_probe() -> None:
        raise RuntimeError("probe failure")

    response = asyncio.run(
        _request(
            app,
            "/v1/atom-lab/failure-probe",
            access_code=ACCESS_CODE,
            raise_app_exceptions=False,
        )
    )

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "Внутренняя ошибка сервера.",
            "field_errors": [],
        },
        "request_id": "req_atom_lab",
    }
    assert response.headers["Cache-Control"] == "no-store"


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


@pytest.mark.parametrize("auth_disabled", [False, True])
def test_atom_lab_shell_is_public_but_contains_no_protected_catalog_data(
    app, monkeypatch, auth_disabled,
) -> None:
    if auth_disabled:
        monkeypatch.setenv("ANYTOOLAI_ATOM_LAB_AUTH_DISABLED", "true")
    page = asyncio.run(_request(app, "/atom-lab"))
    styles = asyncio.run(_request(app, "/atom-lab/atom_lab.css"))
    script = asyncio.run(_request(app, "/atom-lab/atom_lab.mjs"))

    assert page.status_code == HTTPStatus.OK
    assert page.headers["Content-Security-Policy"] == "frame-ancestors 'none'"
    assert page.headers["Cache-Control"] == "no-store"
    assert styles.status_code == HTTPStatus.OK
    assert script.status_code == HTTPStatus.OK
    assert '<input id="access-code" type="password"' in page.text
    assert '<script src="/atom-lab/atom_lab.mjs" type="module"></script>' in page.text
    assert "X-Atom-Lab-Access-Code" in script.text
    assert "textContent" in script.text
    assert 'id="atom-navigation"' in page.text
    assert 'id="atom-passport"' in page.text
    assert 'id="input-editor"' in page.text
    assert 'id="prompt-editor"' in page.text
    assert 'id="input-schema"' in page.text
    assert 'id="output-schema"' in page.text
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


def test_atom_lab_error_schema_requires_field_errors(app) -> None:
    schema = app.openapi()["components"]["schemas"]["AtomLabErrorDetailResponse"]

    assert "field_errors" in schema["required"]


def test_atom_lab_openapi_preserves_the_finite_atom_id_contract(app) -> None:
    openapi = app.openapi()
    atom_id_schema = openapi["components"]["schemas"]["AtomLabAtomResponse"]["properties"][
        "atom_id"
    ]

    assert atom_id_schema == {"$ref": "#/components/schemas/AtomLabAtomId"}
    assert openapi["components"]["schemas"]["AtomLabAtomId"]["enum"] == [
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


@pytest.mark.parametrize(
    "path",
    ["/v1/atom-lab/atoms", "/v1/atom-lab/atoms/{atom_id}"],
)
def test_atom_lab_catalog_routes_document_the_safe_422_envelope(app, path: str) -> None:
    response_schema = app.openapi()["paths"][path]["get"]["responses"]["422"]["content"][
        "application/json"
    ]["schema"]

    assert response_schema == {"$ref": "#/components/schemas/AtomLabErrorResponse"}


def _seed_result(session_factory: SessionFactory, *, runtime_scope: str | None) -> tuple[str, str]:
    metadata = {} if runtime_scope is None else {"runtime_scope": runtime_scope}
    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).create(
            ScenarioSessionRecord(
                tenant_id="anytoolai",
                region="ru",
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


def _seed_client_event_session(
    session_factory: SessionFactory, *, runtime_scope: str | None
) -> str:
    metadata = {} if runtime_scope is None else {"runtime_scope": runtime_scope}
    with transaction_boundary(session_factory) as session:
        guest = GuestIdentityRepository(session).create(
            GuestIdentityRecord(
                id="guest_client_event_scope",
                tenant_id="anytoolai",
                region="ru",
            )
        )
        scenario = ScenarioSessionRepository(session).create(
            ScenarioSessionRecord(
                tenant_id="anytoolai",
                region="ru",
                product_id="kernel_demo",
                frontend_id="web_mirror",
                scenario_id="kernel_demo.single_action_smoke_v1",
                scenario_version=1,
                guest_id=guest.id,
                metadata=metadata,
            )
        )
        return scenario.id


def _client_event_count(session_factory: SessionFactory, scenario_session_id: str) -> int:
    with transaction_boundary(session_factory) as session:
        return session.execute(
            sa.select(sa.func.count())
            .select_from(event_log_table)
            .where(event_log_table.c.scenario_session_id == scenario_session_id)
        ).scalar_one()


def _client_event_payload(scenario_session_id: str) -> dict[str, object]:
    return {
        "event_id": "11111111-1111-4111-8111-111111111111",
        "event_type": "web.result_viewed",
        "product_id": "kernel_demo",
        "frontend_id": "web_mirror",
        "web_session_id": "22222222-2222-4222-8222-222222222222",
        "scenario_session_id": scenario_session_id,
    }


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


@pytest.mark.parametrize("runtime_scope", ["atom_lab", "unrecognized_internal_scope"])
def test_public_client_events_hide_non_public_sessions_without_recording(
    stored_app,
    session_factory: SessionFactory,
    runtime_scope: str,
) -> None:
    scenario_id = _seed_client_event_session(session_factory, runtime_scope=runtime_scope)

    response = _public_request(
        stored_app,
        "POST",
        "/v1/client-events",
        _client_event_payload(scenario_id),
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "scenario_session_not_found"
    assert _client_event_count(session_factory, scenario_id) == 0


def test_public_client_events_keep_ordinary_sessions_available(
    stored_app, session_factory: SessionFactory
) -> None:
    scenario_id = _seed_client_event_session(session_factory, runtime_scope=None)

    response = _public_request(
        stored_app,
        "POST",
        "/v1/client-events",
        _client_event_payload(scenario_id),
    )

    assert response.status_code == HTTPStatus.OK
    assert _client_event_count(session_factory, scenario_id) == 1


def test_public_result_route_hides_artifact_when_source_session_is_missing(
    stored_app, session_factory: SessionFactory
) -> None:
    scenario_id, artifact_id = _seed_result(session_factory, runtime_scope=None)
    with transaction_boundary(session_factory) as session:
        session.execute(
            sa.delete(scenario_sessions_table).where(scenario_sessions_table.c.id == scenario_id)
        )

    response = _public_request(stored_app, "GET", f"/v1/results/{artifact_id}")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "result_artifact_not_found"
    assert "2026-09-30" not in response.text


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
