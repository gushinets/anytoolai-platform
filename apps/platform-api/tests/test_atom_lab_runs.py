from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from dataclasses import replace
from datetime import timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest
import sqlalchemy as sa
from anytoolai_platform_api.atom_lab.catalog import get_atom_catalog_entry
from anytoolai_platform_api.dependencies import (
    get_atom_lab_run_settings,
    get_atom_lab_session_factory,
    get_config_registry,
)
from anytoolai_platform_api.main import create_app
from anytoolai_platform_api.routers.atom_lab import get_atom_lab_run_session_factory
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.atom_lab.models import (
    AtomLabPresetIdentityRecord,
    AtomLabPresetVersionRecord,
)
from anytoolai_platform_core.atom_lab.repository import (
    AtomLabPresetRepository,
    AtomLabRunRepository,
)
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.db import (
    atom_lab_admission_scopes_table,
    atom_lab_runs_table,
    guest_identities_table,
    jobs_table,
    model_catalog_state_table,
    runtime_metadata,
    scenario_sessions_table,
)
from anytoolai_platform_core.storage.transactions import build_session_factory, transaction_boundary
from anytoolai_platform_core.workflows.mappings import resolve_step_input
from anytoolai_platform_core.workflows.repository import JobRepository
from fastapi import FastAPI
from psycopg.types.string import StrDumper
from pydantic import ValidationError

from tests.support.sqlite_harness import build_sqlite_runtime_engine

CONFIG_ROOT = Path(__file__).resolve().parents[3] / "configs" / "kernel"
ACCESS_CODE = "private-access-code"
LIVE_TOKEN = "server-only-live-token"
MODEL_ID = "openai/gpt-5.4-mini"
INPUTS = {
    "A01": {
        "source_text": "Срок 30 сентября",
        "fields": [{"name": "date", "type": "date", "description": "Срок", "required": False}],
        "strict": False,
    },
    "A02": {
        "text_a": "Бриф",
        "text_b": "Предложение",
        "rubric": [{"id": "match", "description": "Совпадение", "weight": 2}],
    },
    "A03": {"text": "План", "axes": [{"id": "clarity", "description": "Ясность"}]},
    "A04": {"source_text": "Бриф", "context": "", "taxonomy": []},
    "A05": {
        "issues": [{"category": "Срок", "description": "Не задан", "severity": "low"}],
        "context": "Проект",
        "target_audience": "Клиент",
        "max_questions": 2,
    },
    "A06": {
        "context": {"nested": {"zero": 0, "unset": None, "false": False}},
        "objective": "Пилот",
        "audience": "Команда",
        "angle": "Скорость",
        "constraints": {"tone": "firm", "length": 200, "language": "ru", "format": "html"},
    },
    "A07": {
        "situation": "Запрос",
        "intent": "Ответ",
        "tone": "warm",
        "constraints": {"language": "ru", "max_length": 500, "output_format": "markdown"},
    },
    "A08": {"source_text": "План", "gap": "Срок", "style": "bold"},
    "A09": {
        "signals": [
            {"id": "missing", "label": "Нет данных", "value": None},
            {"id": "zero", "label": "Ноль", "value": 0},
        ],
        "objective": "Оценка",
        "options": [],
    },
    "A10": {
        "template_ref": "custom_v2",
        "data": {"nested": [None, False, 0], "custom": "значение"},
    },
    "A11": {
        "subject_text": "Пилот",
        "reference_text": "Бриф",
        "categories": ["да", "нет"],
        "criteria": [{"id": "scope", "description": "Объём"}],
    },
}


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[FastAPI]:
    monkeypatch.setenv("ANYTOOLAI_ATOM_LAB_ACCESS_CODE", ACCESS_CODE)
    monkeypatch.setenv("ANYTOOLAI_LIVE_CANARY_TOKEN", LIVE_TOKEN)
    engine = build_sqlite_runtime_engine(tmp_path / "main.db", tmp_path / "platform.db")
    runtime_metadata.create_all(engine)
    factory = build_session_factory(engine)
    application = create_app(config_root=CONFIG_ROOT)
    application.dependency_overrides[get_atom_lab_session_factory] = lambda: factory
    application.dependency_overrides[get_atom_lab_run_session_factory] = lambda: factory
    now = utc_now()
    with transaction_boundary(factory) as session:
        session.execute(
            sa.insert(model_catalog_state_table).values(
                account_scope=application.state.runtime.model_catalog_settings.account_scope,
                snapshot_id="snapshot-api-1",
                due_at=now + timedelta(days=1),
                last_success_at=now,
                created_at=now,
                updated_at=now,
                snapshot={
                    "items": [
                        {
                            "model_id": "gpt-5.4-mini",
                            "compatibility": "compatible",
                            "reason": "confirmed_openai_text_gpt",
                            "reasoning_supported": True,
                            "allowed_reasoning_efforts": ["high"],
                            "provenance": {"availability": {"source": "openai_models_api"}},
                        }
                    ]
                },
            )
        )
    try:
        yield application
    finally:
        engine.dispose()


def _factory(app: FastAPI):
    return app.dependency_overrides[get_atom_lab_session_factory]()


def _payload(atom_id: str = "A01", **updates: Any) -> dict[str, Any]:
    return {
        "atom_id": atom_id,
        "input": INPUTS[atom_id],
        "prompt": "Точный промпт",
        "model_id": MODEL_ID,
        "reasoning_effort": "high",
        **updates,
    }


def _post(
    app: FastAPI,
    payload: Any = None,
    *,
    key: str | None = "key-1",
    access: str | None = ACCESS_CODE,
    content: bytes | None = None,
) -> httpx.Response:
    async def request():
        headers = {"Content-Type": "application/json"}
        if key is not None:
            headers["Idempotency-Key"] = key
        if access is not None:
            headers["X-Atom-Lab-Access-Code"] = access
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post(
                "/v1/atom-lab/runs",
                headers=headers,
                content=content
                if content is not None
                else json.dumps(payload, ensure_ascii=True).encode(),
            )

    return asyncio.run(request())


def _counts(app: FastAPI) -> tuple[int, ...]:
    with transaction_boundary(_factory(app)) as session:
        return tuple(
            session.scalar(sa.select(sa.func.count()).select_from(table))
            for table in (
                guest_identities_table,
                scenario_sessions_table,
                jobs_table,
                atom_lab_runs_table,
                atom_lab_admission_scopes_table,
            )
        )


def _error(response: httpx.Response, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error", "request_id"}
    assert set(body["error"]) == {"code", "message", "field_errors"}
    assert body["error"]["code"] == code
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert ACCESS_CODE not in response.text
    assert LIVE_TOKEN not in response.text
    assert "Точный промпт" not in response.text


@pytest.mark.parametrize("atom_id", list(INPUTS))
def test_run_preserves_every_atom_payload_through_real_workflow_mapping(app, atom_id):
    payload = _payload(atom_id)
    response = _post(app, payload)
    assert response.status_code == HTTPStatus.ACCEPTED, response.text
    wire = response.json()
    assert set(wire) == {"run_id", "scenario_session_id", "job_id", "status"}
    assert wire["status"] == "queued"
    with transaction_boundary(_factory(app)) as session:
        run = AtomLabRunRepository(session).get(wire["run_id"])
        scenario = ScenarioSessionRepository(session).get(
            wire["scenario_session_id"],
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            frontend_id="kernel_demo_web",
        )
        job = JobRepository(session).get(wire["job_id"])
    assert run.input_payload == payload["input"] == scenario.metadata["input"]
    assert run.prompt == payload["prompt"]
    assert run.model_id == MODEL_ID
    assert run.capability_snapshot_id == "snapshot-api-1"
    assert run.capability_provenance == {"availability": {"source": "openai_models_api"}}
    registry = app.state.runtime.config_registry
    definition = registry.get_scenario(scenario.scenario_id)
    assert definition.internal_only
    workflow = registry.get_workflow(job.workflow_id)
    assert len(workflow.steps) == 1
    assert (
        resolve_step_input(
            input_mapping=workflow.steps[0].input_mapping,
            scenario_input=scenario.metadata["input"],
            step_outputs={},
            context={},
        )
        == payload["input"]
    )
    assert _counts(app) == (1, 1, 1, 1, 1)


@pytest.mark.parametrize("access", [None, "wrong"])
def test_auth_precedes_idempotency_lookup_even_with_malformed_body(app, monkeypatch, access):
    def forbidden(*args, **kwargs):
        raise AssertionError("unauthenticated idempotency lookup")

    monkeypatch.setattr(AtomLabRunRepository, "get_by_idempotency_key", forbidden)
    _error(_post(app, access=access, content=b"{"), 401, "access_denied")
    assert _counts(app) == (0, 0, 0, 0, 0)


@pytest.mark.parametrize("key", [None, "", " ", "x" * 129])
def test_missing_blank_or_oversized_idempotency_key_rejected(app, key):
    _error(_post(app, _payload(), key=key), 422, "input_invalid")
    assert _counts(app) == (0, 0, 0, 0, 0)


@pytest.mark.parametrize(
    "field", ["scenario_id", "provider", "base_url", "credentials", "schema", "live_canary_token"]
)
def test_client_cannot_override_server_execution_boundaries(app, field):
    _error(_post(app, _payload(**{field: "secret-value"})), 422, "input_invalid")


@pytest.mark.parametrize(
    "content", [b"{", b"[]", b"null", b'{"input": NaN}', b"\xff", b'{"prompt":"\\ud800"}']
)
def test_malformed_requests_have_safe_envelope(app, content):
    _error(_post(app, content=content), 422, "input_invalid")


@pytest.mark.parametrize("effort", ["omitted", "invalid", 1])
def test_effort_must_be_present_and_a_known_value_or_null(app, effort):
    payload = _payload(reasoning_effort=effort)
    if effort == "omitted":
        payload.pop("reasoning_effort")
    _error(_post(app, payload), 422, "input_invalid")


@pytest.mark.parametrize(
    "updates",
    [
        {"prompt": "  "},
        {"input": []},
        {"input": {}},
        {"input": {**INPUTS["A01"], "strict": "false"}},
        {"input": {**INPUTS["A01"], "fields": INPUTS["A01"]["fields"] * 2}},
    ],
)
def test_invalid_contract_or_semantic_input_cannot_create_admission(app, updates):
    _error(_post(app, _payload(**updates)), 422, "input_invalid")
    assert _counts(app) == (0, 0, 0, 0, 0)


def test_raw_limit_precedes_json_parsing(app):
    _error(_post(app, content=b"{" + b" " * (384 * 1024)), 413, "payload_too_large")
    assert _counts(app) == (0, 0, 0, 0, 0)


@pytest.mark.parametrize("field,limit", [("input", 256 * 1024), ("prompt", 64 * 1024)])
def test_decoded_utf8_limits_reject_one_byte_over_and_accept_boundary(app, field, limit):
    payload = _payload("A04")
    if field == "input":
        overhead = len(b'{"source_text":""}')
        payload[field] = {"source_text": "\u00e9" * ((limit - overhead) // 2)}
        while (
            len(json.dumps(payload[field], ensure_ascii=False, separators=(",", ":")).encode())
            < limit
        ):
            payload[field]["source_text"] += "x"
    else:
        payload[field] = "\u00e9" * (limit // 2)
    raw = json.dumps(payload, ensure_ascii=False).encode()
    assert _post(app, content=raw).status_code == HTTPStatus.ACCEPTED
    if field == "input":
        payload[field]["source_text"] += "x"
    else:
        payload[field] += "x"
    _error(
        _post(app, content=json.dumps(payload, ensure_ascii=False).encode(), key="too-big"),
        413,
        "payload_too_large",
    )


def test_canonical_input_size_counts_json_escaping_not_only_string_bytes(app):
    app.dependency_overrides[get_atom_lab_run_settings] = lambda: Settings(
        atom_lab_run_input_max_bytes=40
    )
    _error(_post(app, _payload("A04", input={"source_text": "\n" * 20})), 413, "payload_too_large")


def _change_catalog(app, **changes):
    with transaction_boundary(_factory(app)) as session:
        row = session.execute(sa.select(model_catalog_state_table)).mappings().one()
        snapshot = row["snapshot"]
        snapshot["items"][0].update(changes)
        session.execute(sa.update(model_catalog_state_table).values(snapshot=snapshot))


@pytest.mark.parametrize(
    "updates",
    [
        {"model_id": "openai/missing"},
        {"model_id": "anthropic/claude"},
        {"model_id": "gpt-5.4-mini"},
    ],
)
def test_model_must_be_present_addressable_and_compatible(app, updates):
    _error(_post(app, _payload(**updates)), 422, "model_not_allowed")


@pytest.mark.parametrize("compatibility", ["unknown", "unsupported"])
def test_unconfirmed_model_compatibility_blocks_admission(app, compatibility):
    _change_catalog(app, compatibility=compatibility)
    _error(_post(app, _payload()), 422, "model_not_allowed")


@pytest.mark.parametrize(
    "updates",
    [
        {"reasoning_supported": False},
        {"reasoning_supported": None},
        {"allowed_reasoning_efforts": None},
        {"allowed_reasoning_efforts": ["low"]},
    ],
)
def test_effort_requires_explicit_support_and_confirmed_allowed_values(app, updates):
    _change_catalog(app, **updates)
    _error(_post(app, _payload()), 422, "reasoning_not_allowed")


def test_null_effort_works_without_reasoning_capability(app):
    _change_catalog(app, reasoning_supported=False, allowed_reasoning_efforts=None)
    assert _post(app, _payload(reasoning_effort=None)).status_code == HTTPStatus.ACCEPTED


def test_empty_initial_catalog_is_unavailable(app):
    with transaction_boundary(_factory(app)) as session:
        session.execute(sa.delete(model_catalog_state_table))
    _error(_post(app, _payload()), 503, "catalog_unavailable")


def test_last_good_stale_catalog_can_still_admit_known_model(app):
    with transaction_boundary(_factory(app)) as session:
        session.execute(
            sa.update(model_catalog_state_table).values(
                due_at=utc_now() - timedelta(days=1), last_error="refresh failed"
            )
        )
    assert _post(app, _payload()).status_code == HTTPStatus.ACCEPTED


def test_missing_server_token_rejects_new_admission_before_writes(app, monkeypatch):
    monkeypatch.delenv("ANYTOOLAI_LIVE_CANARY_TOKEN")
    _error(_post(app, _payload()), 503, "lab_unavailable")
    assert _counts(app) == (0, 0, 0, 0, 0)


def test_missing_server_access_config_fails_closed(app, monkeypatch):
    monkeypatch.delenv("ANYTOOLAI_ATOM_LAB_ACCESS_CODE")
    _error(_post(app, _payload()), 503, "lab_unavailable")


def test_replay_ignores_later_model_token_and_quota_changes_but_conflicts_on_body(app, monkeypatch):
    first = _post(app, _payload())
    assert first.status_code == HTTPStatus.ACCEPTED
    with transaction_boundary(_factory(app)) as session:
        session.execute(sa.delete(model_catalog_state_table))
    monkeypatch.delenv("ANYTOOLAI_LIVE_CANARY_TOKEN")
    replay = _post(app, _payload())
    assert replay.status_code == HTTPStatus.ACCEPTED
    assert replay.json() == first.json()
    _error(_post(app, _payload(prompt="Изменено")), 409, "idempotency_conflict")
    assert _counts(app) == (1, 1, 1, 1, 1)


@pytest.mark.parametrize(
    "limit,code",
    [
        ("atom_lab_run_active_limit", "lab_busy"),
        ("atom_lab_run_daily_limit", "daily_limit_exhausted"),
    ],
)
def test_admission_limits_return_safe_errors_without_second_run(app, limit, code):
    app.dependency_overrides[get_atom_lab_run_settings] = lambda: Settings(**{limit: 1})
    assert _post(app, _payload()).status_code == HTTPStatus.ACCEPTED
    _error(_post(app, _payload(), key="new-key"), 429, code)
    assert _counts(app) == (1, 1, 1, 1, 1)


def test_missing_preset_version_is_not_found(app):
    _error(
        _post(app, _payload(preset_ref={"preset_id": "absent", "version": 1})),
        404,
        "preset_not_found",
    )


@pytest.mark.parametrize(
    "preset_id",
    ["private\x00id", "private\n", "private\t", "private\x1f", "private\x7f",
     "private\x9b", "../private", "private/id", "private id", "private\u202e", "", "x" * 129],
)
def test_malformed_preset_id_is_rejected_before_any_repository_lookup(app, monkeypatch, preset_id):
    def forbidden(*args, **kwargs):
        raise AssertionError("malformed preset ID reached a repository")

    monkeypatch.setattr(AtomLabRunRepository, "get_by_idempotency_key", forbidden)
    monkeypatch.setattr(AtomLabPresetRepository, "get_version", forbidden)
    payload = _payload(preset_ref={"preset_id": preset_id, "version": 1})
    response = _post(app, payload)
    _error(response, 422, "input_invalid")
    assert response.json()["error"]["field_errors"] == [
        {"path": "preset_ref.preset_id", "message": "Недопустимое значение."}
    ]
    assert "private" not in response.text
    _error(_post(app, payload, access="wrong"), 401, "access_denied")
    assert _counts(app) == (0, 0, 0, 0, 0)


def test_bounded_preset_id_is_safe_for_postgresql_lookup(app):
    preset_id = "x" * 128
    assert StrDumper(str).dump(preset_id) == b"x" * 128
    _error(_post(app, _payload(preset_ref={"preset_id": preset_id, "version": 1})),
           404, "preset_not_found")


def test_preset_reference_is_provenance_and_never_merges_saved_payload(app):
    atom = get_atom_catalog_entry(app.state.runtime.config_registry, "A01")

    identity = AtomLabPresetIdentityRecord(tenant_id="anytoolai", region="default", atom_id="A01")
    version = AtomLabPresetVersionRecord(
        preset_id=identity.id,
        version=1,
        tenant_id="anytoolai",
        region="default",
        name="Preset",
        description="",
        atom_id="A01",
        base_action_config_id=atom.base_action_config_id,
        input_schema_ref=atom.schema_refs.input.schema_ref,
        input_schema_version=1,
        output_schema_ref=atom.schema_refs.output.schema_ref,
        output_schema_version=1,
        prompt="Saved prompt",
        prompt_ref=atom.prompt_ref,
        model_id=MODEL_ID,
        reasoning_effort=None,
        fixed_fields=("strict",),
        example_input=atom.example_input,
    )
    with transaction_boundary(_factory(app)) as session:
        AtomLabPresetRepository(session).create(identity, version)
    response = _post(app, _payload(preset_ref={"preset_id": identity.id, "version": 1}))
    assert response.status_code == HTTPStatus.ACCEPTED, response.text
    with transaction_boundary(_factory(app)) as session:
        run = AtomLabRunRepository(session).get(response.json()["run_id"])
    assert run.input_payload == INPUTS["A01"]
    assert run.prompt == "Точный промпт"
    assert run.preset_id == identity.id
    _error(
        _post(
            app,
            _payload("A02", preset_ref={"preset_id": identity.id, "version": 1}),
            key="wrong-atom",
        ),
        409,
        "preset_mismatch",
    )


def test_unconfigured_storage_returns_run_specific_unavailable_code(monkeypatch):
    monkeypatch.setenv("ANYTOOLAI_ATOM_LAB_ACCESS_CODE", ACCESS_CODE)
    monkeypatch.delenv("ANYTOOLAI_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    application = create_app(config_root=CONFIG_ROOT)
    _error(_post(application, _payload()), 503, "lab_unavailable")


def test_openapi_requires_idempotency_and_documents_actual_strict_body(app):
    operation = app.openapi()["paths"]["/v1/atom-lab/runs"]["post"]
    key = next(item for item in operation["parameters"] if item["name"] == "Idempotency-Key")
    assert key["required"] is True
    schema = operation["requestBody"]["content"]["application/json"]["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"atom_id", "input", "prompt", "model_id", "reasoning_effort"}


def test_openapi_payload_limit_description_is_python_version_independent(app):
    operation = app.openapi()["paths"]["/v1/atom-lab/runs"]["post"]
    assert operation["responses"]["413"]["description"] == "Atom Lab payload is too large."


@pytest.mark.parametrize("version", [True, "1", 0, 2_147_483_648])
def test_preset_version_is_a_strict_positive_database_integer(app, version):
    _error(
        _post(app, _payload(preset_ref={"preset_id": "preset", "version": version})),
        422,
        "input_invalid",
    )


@pytest.mark.parametrize(
    "field",
    [
        "atom_lab_run_body_max_bytes",
        "atom_lab_run_input_max_bytes",
        "atom_lab_run_prompt_max_bytes",
        "atom_lab_run_daily_limit",
        "atom_lab_run_active_limit",
    ],
)
def test_run_limits_reject_nonpositive_configuration(field):
    with pytest.raises(ValidationError):
        Settings(**{field: 0})


def test_schema_drift_fails_as_contract_unavailable_without_partial_writes(app):
    registry = app.state.runtime.config_registry
    workflows = dict(registry.workflows)
    workflow_id = "kernel_demo.atom_lab_a01_v1"
    workflows[workflow_id] = replace(workflows[workflow_id], input_schema_ref="missing")
    app.dependency_overrides[get_config_registry] = lambda: replace(registry, workflows=workflows)
    _error(_post(app, _payload()), 409, "contract_unavailable")
    assert _counts(app) == (0, 0, 0, 0, 0)


def test_rejected_input_does_not_consume_idempotency_key_or_daily_limit(app):
    app.dependency_overrides[get_atom_lab_run_settings] = lambda: Settings(
        atom_lab_run_daily_limit=1
    )
    _error(_post(app, _payload(input={})), 422, "input_invalid")
    assert _post(app, _payload()).status_code == HTTPStatus.ACCEPTED


def test_errors_and_request_logs_never_echo_untrusted_values(app, caplog):
    secret = "sensitive-user-data-marker"
    response = _post(app, _payload(input={secret: secret}, prompt=secret, credentials=secret))
    _error(response, 422, "input_invalid")
    assert secret not in response.text
    assert secret not in caplog.text
    assert ACCESS_CODE not in caplog.text
    assert LIVE_TOKEN not in caplog.text


@pytest.mark.parametrize("field", ["input", "prompt"])
def test_accepted_replay_bypasses_later_decoded_limit_tightening(app, field):
    first = _post(app, _payload())
    assert first.status_code == HTTPStatus.ACCEPTED
    app.dependency_overrides[get_atom_lab_run_settings] = lambda: Settings(
        **{f"atom_lab_run_{field}_max_bytes": 1}
    )
    replay = _post(app, _payload())
    assert replay.status_code == HTTPStatus.ACCEPTED, replay.text
    assert replay.json() == first.json()
    _error(_post(app, _payload(), key="new-key"), 413, "payload_too_large")
    assert _counts(app) == (1, 1, 1, 1, 1)


RUN_LIMIT_ENV = {
    "ANYTOOLAI_ATOM_LAB_RUN_BODY_MAX_BYTES": "atom_lab_run_body_max_bytes",
    "ANYTOOLAI_ATOM_LAB_RUN_INPUT_MAX_BYTES": "atom_lab_run_input_max_bytes",
    "ANYTOOLAI_ATOM_LAB_RUN_PROMPT_MAX_BYTES": "atom_lab_run_prompt_max_bytes",
    "ANYTOOLAI_ATOM_LAB_RUN_DAILY_LIMIT": "atom_lab_run_daily_limit",
    "ANYTOOLAI_ATOM_LAB_RUN_ACTIVE_LIMIT": "atom_lab_run_active_limit",
}


@pytest.mark.parametrize("env_name,field", RUN_LIMIT_ENV.items())
def test_run_settings_load_named_limit_environment(monkeypatch, env_name, field):
    configured_limit = 7
    monkeypatch.setenv(env_name, str(configured_limit))
    assert getattr(Settings.from_env(), field) == configured_limit


@pytest.mark.parametrize("value", ["0", "-1", "invalid", "1.5"])
@pytest.mark.parametrize("env_name", RUN_LIMIT_ENV)
def test_run_settings_reject_invalid_limit_environment(monkeypatch, env_name, value):
    monkeypatch.setenv(env_name, value)
    with pytest.raises(ValidationError):
        Settings.from_env()


def test_invalid_run_limit_environment_does_not_break_unrelated_routes(app, monkeypatch):
    monkeypatch.setenv("ANYTOOLAI_ATOM_LAB_RUN_DAILY_LIMIT", "invalid")
    monkeypatch.setenv("ANYTOOLAI_DEMO_ACCESS_CODE", "demo-access")

    async def request() -> tuple[httpx.Response, httpx.Response]:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            health = await client.get("/health")
            demo = await client.post(
                "/v1/demo/runs",
                json={"demo_id": "analyze", "source_text": "Тестовый текст"},
                headers={"X-Demo-Access-Code": "demo-access"},
            )
            return health, demo

    health, demo = asyncio.run(request())
    assert health.status_code == HTTPStatus.OK
    assert demo.status_code == HTTPStatus.SERVICE_UNAVAILABLE, demo.text
    assert demo.json()["error"]["code"] == "demo_unavailable"


def test_invalid_run_limit_environment_fails_run_endpoint_safely(app, monkeypatch):
    monkeypatch.setenv("ANYTOOLAI_ATOM_LAB_RUN_DAILY_LIMIT", "invalid")

    async def request() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            return await client.post(
                "/v1/atom-lab/runs",
                json=_payload(),
                headers={
                    "Idempotency-Key": "invalid-settings",
                    "X-Atom-Lab-Access-Code": ACCESS_CODE,
                },
            )

    _error(asyncio.run(request()), 503, "lab_unavailable")


def test_deployment_environment_limits_apply_and_dependency_overrides_remain_supported(
    app, monkeypatch
):
    monkeypatch.setenv("ANYTOOLAI_ATOM_LAB_RUN_BODY_MAX_BYTES", "1")
    _error(_post(app, _payload()), 413, "payload_too_large")

    def default_settings() -> Settings:
        return Settings()

    app.dependency_overrides[get_atom_lab_run_settings] = default_settings
    assert _post(app, _payload()).status_code == HTTPStatus.ACCEPTED


@pytest.mark.parametrize("event_name", ["before_cursor_execute", "commit"])
def test_database_connectivity_failure_returns_safe_unavailable_and_rolls_back(
    app, event_name, caplog
):
    engine = _factory(app).kw["bind"]
    secret = "database-private-host-and-credentials"

    def fail(*args, **kwargs):
        raise sa.exc.OperationalError("SELECT private", {}, Exception(secret))

    sa.event.listen(engine, event_name, fail)
    try:
        response = _post(app, _payload())
    finally:
        sa.event.remove(engine, event_name, fail)
    _error(response, 503, "lab_unavailable")
    assert secret not in response.text
    assert secret not in caplog.text
    assert _counts(app) == (0, 0, 0, 0, 0)


def test_database_programming_failure_returns_safe_error_without_logging_parameters(app, caplog):
    engine = _factory(app).kw["bind"]
    secret = "atom-lab-private-input-marker"

    def fail(*args, **kwargs):
        raise sa.exc.ProgrammingError(
            "INSERT INTO atom_lab_runs (prompt) VALUES (:prompt)",
            {"prompt": secret},
            Exception("fixture programming error"),
        )

    sa.event.listen(engine, "before_cursor_execute", fail)
    try:
        response = _post(app, _payload(prompt=secret))
    finally:
        sa.event.remove(engine, "before_cursor_execute", fail)
    _error(response, 503, "lab_unavailable")
    assert "atom_lab.run_database_error" in caplog.text
    assert secret not in response.text
    assert secret not in caplog.text
    assert _counts(app) == (0, 0, 0, 0, 0)


@pytest.mark.parametrize(
    "updates,path",
    [
        ({"prompt": "private\x00prompt"}, "prompt"),
        ({"input": {"template_ref": "custom", "data": {"nested": ["private\x00value"]}}}, "input"),
        (
            {"input": {"template_ref": "custom", "data": {"nested": [{"private\x00key": 1}]}}},
            "input",
        ),
    ],
)
def test_postgresql_unrepresentable_nul_is_rejected_before_persistence(app, updates, path):
    response = _post(app, _payload("A10", **updates))
    _error(response, 422, "input_invalid")
    assert response.json()["error"]["field_errors"] == [
        {"path": path, "message": "Недопустимое значение."}
    ]
    assert "private" not in response.text
    assert _counts(app) == (0, 0, 0, 0, 0)


def test_real_postgresql_text_driver_rejects_nul_that_sqlite_accepts():
    # Actual psycopg text adaptation; a server is not needed for this binding failure.
    with pytest.raises(psycopg.DataError, match="cannot contain NUL"):
        StrDumper(str).dump("text\x00value")
