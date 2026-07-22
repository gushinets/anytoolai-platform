from __future__ import annotations

import asyncio
from http import HTTPStatus
from typing import Any

import httpx

from anytoolai_platform_api.main import create_app

EXPECTED_QUOTA_LIMIT = 3
CHROME_EXTENSION_ID_LENGTH = 32
FORBIDDEN_RESPONSE_TOKENS = (
    "prompt",
    "system_prompt",
    "provider_policy",
    "provider",
    "model",
    "_file_path",
    "secret",
)


def _collect_response_keys(payload: Any) -> set[str]:
    if isinstance(payload, dict):
        keys = {str(key).lower() for key in payload}
        for value in payload.values():
            keys.update(_collect_response_keys(value))
        return keys

    if isinstance(payload, list):
        keys: set[str] = set()
        for item in payload:
            keys.update(_collect_response_keys(item))
        return keys

    return set()


async def _runtime_config_response(product_id: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(
            f"/v1/products/{product_id}/runtime-config",
            headers={"X-Request-ID": "req_runtime_config_test"},
        )


def test_runtime_config_returns_frontend_safe_metadata() -> None:
    response = asyncio.run(_runtime_config_response("kernel_demo"))

    assert response.status_code == HTTPStatus.OK
    data = response.json()

    assert data["product_id"] == "kernel_demo"
    assert data["frontend_ids"] == ["kernel_demo_ce", "web_mirror"]
    assert data["scenario_ids"] == [
        "kernel_demo.single_action_smoke_v1",
        "kernel_demo.multi_step_workflow_smoke_v1",
        "kernel_demo.quota_exhausted_smoke_v1",
        "kernel_demo.handoff_smoke_source_v1",
        "kernel_demo.handoff_smoke_target_v1",
    ]
    assert data["quota_summary"] == {
        "quota_policy_id": "kernel_demo.guest_quota_v1",
        "unit": "scenario_run",
        "limit_count": EXPECTED_QUOTA_LIMIT,
        "period": "lifetime",
        "dimension": "product",
    }
    assert {
        "capture_email",
        "continue_to_target",
        "copy_result",
        "create_handoff",
        "render_input",
        "render_output",
        "view_paywall",
    }.issubset(data["allowed_ui_capabilities"])

    first_scenario = data["scenarios"][0]
    assert first_scenario["input_renderer_hint"]["renderer"] == "json_schema"
    assert first_scenario["input_renderer_hint"]["schema_ref"].startswith("kernel_demo.")
    assert first_scenario["output_renderer_hint"]["renderer"] == "json_schema"
    assert first_scenario["output_renderer_hint"]["schema_ref"].startswith("kernel_demo.")

    response_keys = _collect_response_keys(data)
    for forbidden_token in FORBIDDEN_RESPONSE_TOKENS:
        assert forbidden_token not in response_keys


def test_unknown_runtime_config_product_returns_safe_404() -> None:
    response = asyncio.run(_runtime_config_response("missing_product"))

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.headers["x-request-id"] == "req_runtime_config_test"
    assert response.json() == {
        "error": {
            "code": "product_not_found",
            "message": "Product not found",
            "request_id": "req_runtime_config_test",
        }
    }
    assert "missing_product" not in response.text


async def _cors_preflight_response() -> httpx.Response:
    extension_origin = "chrome-extension://" + ("a" * CHROME_EXTENSION_ID_LENGTH)
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.options(
            "/v1/products/kernel_demo/runtime-config",
            headers={
                "Origin": extension_origin,
                "Access-Control-Request-Method": "GET",
            },
        )


def test_runtime_config_allows_chrome_extension_cors_origin() -> None:
    response = asyncio.run(_cors_preflight_response())

    assert response.status_code == HTTPStatus.OK
    assert response.headers["access-control-allow-origin"].startswith("chrome-extension://")


def test_openapi_contains_runtime_config_endpoint() -> None:
    app = create_app()
    operation = app.openapi()["paths"]["/v1/products/{product_id}/runtime-config"]["get"]

    assert operation["responses"]["200"]["content"]["application/json"]["example"]["product_id"] == "kernel_demo"
    assert operation["responses"]["404"]["content"]["application/json"]["example"]["error"]["code"] == "product_not_found"
