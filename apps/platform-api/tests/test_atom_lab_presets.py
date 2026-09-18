from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx
import pytest
import sqlalchemy as sa
from anytoolai_platform_actions.structured_llm.cross_validation import (
    ValidatorRefNotFoundError,
)
from anytoolai_platform_api.dependencies import get_atom_lab_session_factory
from anytoolai_platform_api.main import create_app
from anytoolai_platform_api.routers import atom_lab as atom_lab_router
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.atom_lab.repository import AtomLabRunRepository
from anytoolai_platform_core.atom_lab.snapshots import (
    AtomLabSnapshotRequest,
    build_atom_lab_run_record,
)
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.providers.models import ReasoningEffort
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.db import provider_calls_table, runtime_metadata
from anytoolai_platform_core.storage.transactions import (
    SessionFactory,
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.workflows.models import JobRecord
from anytoolai_platform_core.workflows.repository import JobRepository
from fastapi import FastAPI

from tests.support.sqlite_harness import build_sqlite_runtime_engine

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
ACCESS_CODE = "atom-lab-presets-test-code"
SECOND_VERSION = 2


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[FastAPI]:
    monkeypatch.setenv("ANYTOOLAI_ATOM_LAB_ACCESS_CODE", ACCESS_CODE)
    engine = build_sqlite_runtime_engine(
        tmp_path / "main.sqlite3",
        tmp_path / "platform.sqlite3",
    )
    runtime_metadata.create_all(engine)
    session_factory = build_session_factory(engine)
    application = create_app(config_root=CONFIG_ROOT)
    application.dependency_overrides[get_atom_lab_session_factory] = lambda: session_factory
    try:
        yield application
    finally:
        engine.dispose()


async def _request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        return await client.request(
            method,
            path,
            headers={"X-Atom-Lab-Access-Code": ACCESS_CODE},
            json=json,
        )


async def _request_raw_json(
    app: FastAPI,
    method: str,
    path: str,
    payload: dict[str, Any],
) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        return await client.request(
            method,
            path,
            headers={
                "Content-Type": "application/json",
                "X-Atom-Lab-Access-Code": ACCESS_CODE,
            },
            content=json.dumps(payload).encode("ascii"),
        )


def _version_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": "Извлечение реквизитов",
        "description": "Рабочий вариант извлечения полей из брифа.",
        "atom_id": "A01",
        "base_action_config_id": "kernel_demo.extract_structured_fields_live_v1",
        "schema_refs": {
            "input": {"schema_ref": "kernel.schemas.extract_input_v1", "version": 1},
            "output": {"schema_ref": "kernel.schemas.extract_output_v1", "version": 1},
        },
        "prompt": "Извлеки перечисленные поля строго по контракту.",
        "prompt_ref": "kernel_demo.extract_structured_fields.v1",
        "model_id": "openai/gpt-5.4-mini",
        "reasoning_effort": "high",
        "fixed_fields": ["fields", "strict"],
        "example_input": {
            "source_text": "Срок — 30 сентября, бюджет — 120 000 рублей.",
            "fields": [
                {
                    "name": "deadline",
                    "type": "date",
                    "description": "Срок завершения проекта.",
                    "required": True,
                }
            ],
            "strict": True,
        },
    }
    payload.update(overrides)
    return payload


def _version_payload_for_atom(app: FastAPI, atom_id: str) -> dict[str, Any]:
    response = asyncio.run(_request(app, "GET", f"/v1/atom-lab/atoms/{atom_id}"))
    assert response.status_code == HTTPStatus.OK
    atom = response.json()
    return _version_payload(
        atom_id=atom_id,
        base_action_config_id=atom["base_action_config_id"],
        schema_refs=atom["schema_refs"],
        prompt=atom["prompt"],
        prompt_ref=atom["prompt_ref"],
        fixed_fields=[],
        example_input=atom["example_input"],
    )


def _session_factory(app: FastAPI) -> SessionFactory:
    return app.dependency_overrides[get_atom_lab_session_factory]()


def _provider_call_count(app: FastAPI) -> int:
    with transaction_boundary(_session_factory(app)) as session:
        return int(
            session.scalar(sa.select(sa.func.count()).select_from(provider_calls_table)) or 0
        )


def _seed_lab_run(
    app: FastAPI,
    *,
    tenant_id: str,
    region: str,
    suffix: str,
) -> str:
    input_payload = _version_payload()["example_input"]
    session_factory = _session_factory(app)
    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).create(
            ScenarioSessionRecord(
                id=f"scenario_session_lab_{suffix}",
                tenant_id=tenant_id,
                region=region,
                product_id="kernel_demo",
                frontend_id="kernel_demo_web",
                scenario_id="kernel_demo.atom_lab_a01_v1",
                scenario_version=1,
                metadata={"runtime_scope": "atom_lab", "input": input_payload},
            )
        )
        job = JobRepository(session).create(
            JobRecord(
                id=f"job_lab_{suffix}",
                tenant_id=tenant_id,
                region=region,
                product_id=scenario.product_id,
                frontend_id=scenario.frontend_id,
                scenario_session_id=scenario.id,
                workflow_id="kernel_demo.atom_lab_a01_v1",
                workflow_version=1,
            )
        )

    run = build_atom_lab_run_record(
        build_config_registry(CONFIG_ROOT),
        scenario=scenario,
        job=job,
        request=AtomLabSnapshotRequest(
            atom_id="A01",
            input_payload=input_payload,
            prompt=_version_payload()["prompt"],
            model_id="openai/gpt-5.4-mini",
            reasoning_effort=ReasoningEffort.high,
            capability_snapshot_id=f"capability_snapshot_{suffix}",
            capability_provenance={},
        ),
    )
    with transaction_boundary(session_factory) as session:
        return AtomLabRunRepository(session).create(run).id


def test_create_read_list_version_and_export_preserves_immutable_payload(app: FastAPI) -> None:
    created = asyncio.run(
        _request(app, "POST", "/v1/atom-lab/presets", json=_version_payload())
    )

    assert created.status_code == HTTPStatus.CREATED
    created_payload = created.json()
    assert set(created_payload) == {"preset_id", "version", "created_at"}
    assert created_payload["version"] == 1
    preset_id = created_payload["preset_id"]

    detail = asyncio.run(
        _request(app, "GET", f"/v1/atom-lab/presets/{preset_id}/versions/1")
    )
    assert detail.status_code == HTTPStatus.OK
    assert detail.json() == {
        "preset_id": preset_id,
        "version": 1,
        "created_at": created_payload["created_at"],
        **_version_payload(),
        "source_run_id": None,
    }

    identities = asyncio.run(_request(app, "GET", "/v1/atom-lab/presets"))
    assert identities.status_code == HTTPStatus.OK
    assert identities.json()["next_cursor"] is None
    assert identities.json()["items"] == [
        {
            "preset_id": preset_id,
            "latest_version": 1,
            "name": "Извлечение реквизитов",
            "description": "Рабочий вариант извлечения полей из брифа.",
            "atom_id": "A01",
            "created_at": created_payload["created_at"],
            "updated_at": created_payload["created_at"],
        }
    ]

    versions = asyncio.run(
        _request(app, "GET", f"/v1/atom-lab/presets/{preset_id}/versions")
    )
    assert versions.status_code == HTTPStatus.OK
    assert versions.json() == {
        "items": [
            {
                "preset_id": preset_id,
                "version": 1,
                "name": "Извлечение реквизитов",
                "description": "Рабочий вариант извлечения полей из брифа.",
                "atom_id": "A01",
                "created_at": created_payload["created_at"],
            }
        ],
        "next_cursor": None,
    }

    exported = asyncio.run(
        _request(app, "GET", f"/v1/atom-lab/presets/{preset_id}/versions/1/export")
    )
    assert exported.status_code == HTTPStatus.OK
    assert exported.json() == {
        "format_version": 1,
        "preset_id": preset_id,
        "version": 1,
        "configuration": {**_version_payload(), "source_run_id": None},
    }
    assert "credential" not in exported.text.lower()
    assert "base_url" not in exported.text.lower()


def test_saving_preset_versions_does_not_invoke_provider(app: FastAPI) -> None:
    assert _provider_call_count(app) == 0

    created = asyncio.run(
        _request(app, "POST", "/v1/atom-lab/presets", json=_version_payload())
    )
    assert created.status_code == HTTPStatus.CREATED

    versioned = asyncio.run(
        _request(
            app,
            "POST",
            f"/v1/atom-lab/presets/{created.json()['preset_id']}/versions",
            json={"base_version": 1, **_version_payload(name="Вторая версия")},
        )
    )
    assert versioned.status_code == HTTPStatus.CREATED
    assert _provider_call_count(app) == 0


def test_new_version_is_append_only_and_rejects_stale_base(app: FastAPI) -> None:
    created = asyncio.run(
        _request(app, "POST", "/v1/atom-lab/presets", json=_version_payload())
    ).json()
    preset_id = created["preset_id"]

    next_payload = _version_payload(
        name="Извлечение реквизитов v2",
        prompt="Извлеки поля и не додумывай отсутствующие значения.",
    )
    version_two = asyncio.run(
        _request(
            app,
            "POST",
            f"/v1/atom-lab/presets/{preset_id}/versions",
            json={"base_version": 1, **next_payload},
        )
    )
    assert version_two.status_code == HTTPStatus.CREATED
    assert version_two.json()["version"] == SECOND_VERSION

    conflict = asyncio.run(
        _request(
            app,
            "POST",
            f"/v1/atom-lab/presets/{preset_id}/versions",
            json={"base_version": 1, **next_payload},
        )
    )
    assert conflict.status_code == HTTPStatus.CONFLICT
    assert conflict.json()["error"]["code"] == "preset_version_conflict"

    original = asyncio.run(
        _request(app, "GET", f"/v1/atom-lab/presets/{preset_id}/versions/1")
    )
    assert original.json()["name"] == "Извлечение реквизитов"
    assert original.json()["prompt"] == _version_payload()["prompt"]


@pytest.mark.parametrize(
    ("overrides", "expected_path"),
    [
        ({"fixed_fields": ["fields", "fields"]}, "fixed_fields"),
        ({"fixed_fields": ["fields.items"]}, "fixed_fields.0"),
        ({"fixed_fields": ["missing"]}, "fixed_fields.0"),
        (
            {
                "base_action_config_id": "kernel_demo.compose_reply_live_v1",
            },
            "base_action_config_id",
        ),
        (
            {
                "fixed_fields": [],
                "example_input": {"source_text": "incomplete"},
            },
            "example_input",
        ),
        (
            {
                "example_input": {
                    "source_text": "duplicate semantic field names",
                    "fields": [
                        {
                            "name": "deadline",
                            "type": "date",
                            "description": "First deadline.",
                            "required": True,
                        },
                        {
                            "name": "deadline",
                            "type": "string",
                            "description": "Conflicting deadline.",
                            "required": False,
                        },
                    ],
                    "strict": False,
                }
            },
            "example_input",
        ),
    ],
)
def test_create_rejects_invalid_contract_and_fixed_fields(
    app: FastAPI,
    overrides: dict[str, Any],
    expected_path: str,
) -> None:
    response = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/atom-lab/presets",
            json=_version_payload(**overrides),
        )
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    payload = response.json()
    assert payload["error"]["code"] == "preset_contract_invalid"
    assert payload["error"]["field_errors"] == [
        {"path": expected_path, "message": "Недопустимое значение."}
    ]


def test_create_rejects_unknown_closed_atom_id_at_request_boundary(app: FastAPI) -> None:
    response = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/atom-lab/presets",
            json=_version_payload(atom_id="A12"),
        )
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "request_validation_failed"
    assert [item["path"] for item in response.json()["error"]["field_errors"]] == ["atom_id"]


def test_create_rejects_model_id_that_runtime_cannot_address(app: FastAPI) -> None:
    response = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/atom-lab/presets",
            json=_version_payload(model_id="gpt-5.4-mini"),
        )
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "preset_contract_invalid"
    assert response.json()["error"]["field_errors"] == [
        {"path": "model_id", "message": "Недопустимое значение."}
    ]


def test_create_rejects_example_input_larger_than_256_kib(app: FastAPI) -> None:
    response = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/atom-lab/presets",
            json=_version_payload(
                example_input={
                    "source_text": "x" * 262_144,
                    "fields": [
                        {
                            "name": "deadline",
                            "type": "date",
                            "description": "Срок выполнения",
                            "required": True,
                        }
                    ],
                    "strict": False,
                },
            ),
        )
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "preset_contract_invalid"
    assert response.json()["error"]["field_errors"] == [
        {"path": "example_input", "message": "Недопустимое значение."}
    ]


def test_create_rejects_example_input_with_invalid_unicode(app: FastAPI) -> None:
    example_input = dict(_version_payload()["example_input"])
    example_input["source_text"] = "\ud800"
    response = asyncio.run(
        _request_raw_json(
            app,
            "POST",
            "/v1/atom-lab/presets",
            _version_payload(example_input=example_input),
        )
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "preset_contract_invalid"
    assert response.json()["error"]["field_errors"] == [
        {"path": "example_input", "message": "Недопустимое значение."}
    ]


@pytest.mark.parametrize(
    "invalid_number",
    [
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="positive-infinity"),
        pytest.param(float("-inf"), id="negative-infinity"),
    ],
)
def test_create_rejects_non_finite_numbers_in_example_input(
    app: FastAPI,
    invalid_number: float,
) -> None:
    payload = _version_payload_for_atom(app, "A06")
    example_input = dict(payload["example_input"])
    example_input["context"] = {"invalid_number": invalid_number}
    response = asyncio.run(
        _request_raw_json(
            app,
            "POST",
            "/v1/atom-lab/presets",
            {**payload, "example_input": example_input},
        )
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "preset_contract_invalid"
    assert response.json()["error"]["field_errors"] == [
        {"path": "example_input", "message": "Недопустимое значение."}
    ]


@pytest.mark.parametrize("field_name", ["name", "prompt"])
def test_create_rejects_whitespace_only_required_text(
    app: FastAPI,
    field_name: str,
) -> None:
    response = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/atom-lab/presets",
            json=_version_payload(**{field_name: " \t "}),
        )
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "preset_contract_invalid"
    assert response.json()["error"]["field_errors"] == [
        {"path": field_name, "message": "Недопустимое значение."}
    ]


def test_create_maps_unresolved_input_validator_to_catalog_unavailable(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = ValidatorRefNotFoundError(
        ref="missing.validator",
        field_name="input_validator_ref",
        action_type="text.extract_structured_fields",
    )
    monkeypatch.setattr(
        atom_lab_router,
        "build_input_validator",
        lambda _definition: (_ for _ in ()).throw(error),
    )

    response = asyncio.run(
        _request(app, "POST", "/v1/atom-lab/presets", json=_version_payload())
    )

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()["error"]["code"] == "atom_lab_catalog_unavailable"


def test_preset_routes_require_atom_lab_access(app: FastAPI) -> None:
    async def request_without_access() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.get("/v1/atom-lab/presets")

    response = asyncio.run(request_without_access())

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["error"]["code"] == "atom_lab_access_denied"


def test_preset_list_cursor_is_stable_and_invalid_cursor_is_safe(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 9, 17, 8, 0, tzinfo=UTC)
    monkeypatch.setattr(atom_lab_router, "utc_now", lambda: fixed_now)
    created_ids = []
    for index in range(3):
        response = asyncio.run(
            _request(
                app,
                "POST",
                "/v1/atom-lab/presets",
                json=_version_payload(name=f"Preset {index}"),
            )
        )
        assert response.status_code == HTTPStatus.CREATED
        created_ids.append(response.json()["preset_id"])

    first_page = asyncio.run(_request(app, "GET", "/v1/atom-lab/presets?limit=2"))
    assert first_page.status_code == HTTPStatus.OK
    first_payload = first_page.json()
    assert len(first_payload["items"]) == SECOND_VERSION
    assert first_payload["next_cursor"] is not None

    second_page = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/atom-lab/presets?limit=2&cursor={first_payload['next_cursor']}",
        )
    )
    assert second_page.status_code == HTTPStatus.OK
    returned_ids = [item["preset_id"] for item in first_payload["items"]]
    returned_ids.extend(item["preset_id"] for item in second_page.json()["items"])
    assert returned_ids == sorted(created_ids, reverse=True)
    assert second_page.json()["next_cursor"] is None

    invalid = asyncio.run(
        _request(app, "GET", "/v1/atom-lab/presets?cursor=not-a-valid-cursor")
    )
    assert invalid.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert invalid.json()["error"]["code"] == "invalid_cursor"
    assert invalid.json()["error"]["field_errors"] == [
        {"path": "cursor", "message": "Недопустимое значение."}
    ]

    naive_cursor = base64.urlsafe_b64encode(
        json.dumps(["2026-09-17T08:00:00", "preset-id"]).encode("utf-8")
    ).decode("ascii")
    naive = asyncio.run(
        _request(app, "GET", f"/v1/atom-lab/presets?cursor={naive_cursor}")
    )
    assert naive.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert naive.json()["error"]["code"] == "invalid_cursor"


@pytest.mark.parametrize(
    "cursor",
    [
        "!"
        + base64.urlsafe_b64encode(
            json.dumps(["2026-09-17T08:00:00+00:00", "preset-id"]).encode("utf-8")
        ).decode("ascii"),
        base64.urlsafe_b64encode(
            json.dumps(["2026-09-17T08:00:00+00:00", "p" * 129]).encode("utf-8")
        ).decode("ascii"),
        base64.urlsafe_b64encode(
            json.dumps(
                ["0001-01-01T00:00:00+23:59", "preset-id"],
                separators=(",", ":"),
            ).encode("utf-8")
        ).decode("ascii"),
        base64.urlsafe_b64encode(
            json.dumps(
                ["2026-09-17T08:00:00+00:00", "࠾"],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        .decode("ascii")
        .replace("-", "%2B"),
    ],
)
def test_preset_list_rejects_noncanonical_or_out_of_domain_cursor(
    app: FastAPI,
    cursor: str,
) -> None:
    response = asyncio.run(_request(app, "GET", f"/v1/atom-lab/presets?cursor={cursor}"))

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "invalid_cursor"


def test_version_list_cursor_and_missing_preset_paths(app: FastAPI) -> None:
    created = asyncio.run(
        _request(app, "POST", "/v1/atom-lab/presets", json=_version_payload())
    ).json()
    preset_id = created["preset_id"]
    for base_version in (1, 2):
        response = asyncio.run(
            _request(
                app,
                "POST",
                f"/v1/atom-lab/presets/{preset_id}/versions",
                json={
                    "base_version": base_version,
                    **_version_payload(name=f"Version {base_version + 1}"),
                },
            )
        )
        assert response.status_code == HTTPStatus.CREATED

    first = asyncio.run(
        _request(app, "GET", f"/v1/atom-lab/presets/{preset_id}/versions?limit=2")
    ).json()
    second = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/atom-lab/presets/{preset_id}/versions?limit=2&cursor={first['next_cursor']}",
        )
    ).json()
    assert [item["version"] for item in first["items"] + second["items"]] == [3, 2, 1]
    assert second["next_cursor"] is None

    invalid = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/atom-lab/presets/{preset_id}/versions?cursor=invalid",
        )
    )
    assert invalid.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert invalid.json()["error"]["code"] == "invalid_cursor"

    missing_id = "atom_lab_preset_missing"
    for method, path, body in (
        ("GET", f"/v1/atom-lab/presets/{missing_id}/versions/1", None),
        ("GET", f"/v1/atom-lab/presets/{missing_id}/versions/1/export", None),
        (
            "POST",
            f"/v1/atom-lab/presets/{missing_id}/versions",
            {"base_version": 1, **_version_payload()},
        ),
    ):
        response = asyncio.run(_request(app, method, path, json=body))
        assert response.status_code == HTTPStatus.NOT_FOUND
        assert response.json()["error"]["code"] == "preset_not_found"


@pytest.mark.parametrize("raw_version", ["0", "01", "2147483648"])
def test_version_list_rejects_noncanonical_or_out_of_domain_cursor(
    app: FastAPI,
    raw_version: str,
) -> None:
    cursor = base64.urlsafe_b64encode(raw_version.encode("ascii")).decode("ascii")
    response = asyncio.run(
        _request(app, "GET", f"/v1/atom-lab/presets/missing/versions?cursor={cursor}")
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "invalid_cursor"


def test_reasoning_effort_null_round_trips(app: FastAPI) -> None:
    created = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/atom-lab/presets",
            json=_version_payload(reasoning_effort=None),
        )
    ).json()
    detail = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/atom-lab/presets/{created['preset_id']}/versions/1",
        )
    )
    assert detail.status_code == HTTPStatus.OK
    assert detail.json()["reasoning_effort"] is None


def test_new_version_cannot_switch_preset_atom(app: FastAPI) -> None:
    created = asyncio.run(
        _request(app, "POST", "/v1/atom-lab/presets", json=_version_payload())
    ).json()
    preset_id = created["preset_id"]

    response = asyncio.run(
        _request(
            app,
            "POST",
            f"/v1/atom-lab/presets/{preset_id}/versions",
            json={"base_version": 1, **_version_payload_for_atom(app, "A02")},
        )
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "preset_contract_invalid"
    assert response.json()["error"]["field_errors"] == [
        {"path": "atom_id", "message": "Недопустимое значение."}
    ]

    versions = asyncio.run(
        _request(app, "GET", f"/v1/atom-lab/presets/{preset_id}/versions")
    )
    assert [item["version"] for item in versions.json()["items"]] == [1]


def test_source_run_must_exist_in_matching_lab_scope(app: FastAPI) -> None:
    response = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/atom-lab/presets",
            json=_version_payload(source_run_id="atom_lab_run_missing"),
        )
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "preset_source_run_invalid"
    assert response.json()["error"]["field_errors"] == [
        {"path": "source_run_id", "message": "Недопустимое значение."}
    ]


def test_source_run_accepts_default_scope_and_rejects_cross_scope(app: FastAPI) -> None:
    settings = Settings()
    source_run_id = _seed_lab_run(
        app,
        tenant_id=settings.default_tenant_id,
        region=settings.default_region,
        suffix="default_scope",
    )

    created = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/atom-lab/presets",
            json=_version_payload(source_run_id=source_run_id),
        )
    )
    assert created.status_code == HTTPStatus.CREATED
    detail = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/atom-lab/presets/{created.json()['preset_id']}/versions/1",
        )
    )
    assert detail.status_code == HTTPStatus.OK
    assert detail.json()["source_run_id"] == source_run_id

    cross_scope_run_id = _seed_lab_run(
        app,
        tenant_id="other_tenant",
        region=settings.default_region,
        suffix="cross_scope",
    )
    rejected = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/atom-lab/presets",
            json=_version_payload(source_run_id=cross_scope_run_id),
        )
    )
    assert rejected.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert rejected.json()["error"]["code"] == "preset_source_run_invalid"
