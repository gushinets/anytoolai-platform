from __future__ import annotations

import asyncio
from collections.abc import Iterator
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx
import pytest
from anytoolai_platform_api.dependencies import get_atom_lab_session_factory
from anytoolai_platform_api.main import create_app
from anytoolai_platform_core.storage.db import runtime_metadata
from anytoolai_platform_core.storage.transactions import build_session_factory
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
        ({"atom_id": "A12"}, "atom_id"),
        (
            {
                "base_action_config_id": "kernel_demo.compose_reply_live_v1",
            },
            "base_action_config_id",
        ),
        ({"example_input": {"source_text": "incomplete"}}, "example_input"),
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
    assert payload["error"]["code"] in {
        "request_validation_failed",
        "preset_contract_invalid",
    }
    assert expected_path in {item["path"] for item in payload["error"]["field_errors"]}


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


def test_preset_list_cursor_is_stable_and_invalid_cursor_is_safe(app: FastAPI) -> None:
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
    assert set(returned_ids) == set(created_ids)
    assert second_page.json()["next_cursor"] is None

    invalid = asyncio.run(
        _request(app, "GET", "/v1/atom-lab/presets?cursor=not-a-valid-cursor")
    )
    assert invalid.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert invalid.json()["error"]["code"] == "invalid_cursor"
    assert invalid.json()["error"]["field_errors"] == [
        {"path": "cursor", "message": "Недопустимое значение."}
    ]


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
