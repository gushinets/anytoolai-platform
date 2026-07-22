from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends

from anytoolai_platform_api.dependencies import get_config_registry
from anytoolai_platform_api.errors import ApiError
from anytoolai_platform_api.schemas import ErrorResponse, RuntimeConfigResponse
from anytoolai_platform_core.bootstrap.runtime_config import build_product_runtime_config
from anytoolai_platform_core.config.registry import ConfigRegistry

router = APIRouter(prefix="/v1/products", tags=["runtime-config"])

RUNTIME_CONFIG_EXAMPLE = {
    "product_id": "kernel_demo",
    "frontend_ids": ["kernel_demo_ce", "web_mirror"],
    "frontends": [
        {"frontend_id": "kernel_demo_ce", "type": "chrome_extension", "enabled": True},
        {"frontend_id": "web_mirror", "type": "web", "enabled": True},
    ],
    "scenario_ids": [
        "kernel_demo.single_action_smoke_v1",
        "kernel_demo.multi_step_workflow_smoke_v1",
        "kernel_demo.quota_exhausted_smoke_v1",
        "kernel_demo.handoff_smoke_source_v1",
        "kernel_demo.handoff_smoke_target_v1",
    ],
    "scenarios": [
        {
            "scenario_id": "kernel_demo.single_action_smoke_v1",
            "version": 1,
            "allowed_next_actions": ["copy_result", "create_handoff"],
            "input_renderer_hint": {
                "renderer": "json_schema",
                "schema_ref": "kernel_demo.generic_text_input_v1",
                "schema_version": 1,
            },
            "output_renderer_hint": {
                "renderer": "json_schema",
                "schema_ref": "kernel_demo.extract_output_v1",
                "schema_version": 1,
            },
        },
        {
            "scenario_id": "kernel_demo.multi_step_workflow_smoke_v1",
            "version": 1,
            "allowed_next_actions": ["copy_result", "create_handoff"],
            "input_renderer_hint": {
                "renderer": "json_schema",
                "schema_ref": "kernel_demo.generic_text_input_v1",
                "schema_version": 1,
            },
            "output_renderer_hint": {
                "renderer": "json_schema",
                "schema_ref": "kernel_demo.report_output_v1",
                "schema_version": 1,
            },
        },
        {
            "scenario_id": "kernel_demo.quota_exhausted_smoke_v1",
            "version": 1,
            "allowed_next_actions": ["capture_email", "view_paywall"],
            "input_renderer_hint": {
                "renderer": "json_schema",
                "schema_ref": "kernel_demo.generic_text_input_v1",
                "schema_version": 1,
            },
            "output_renderer_hint": {
                "renderer": "json_schema",
                "schema_ref": "kernel_demo.extract_output_v1",
                "schema_version": 1,
            },
        },
        {
            "scenario_id": "kernel_demo.handoff_smoke_source_v1",
            "version": 1,
            "allowed_next_actions": ["continue_to_target"],
            "input_renderer_hint": {
                "renderer": "json_schema",
                "schema_ref": "kernel_demo.generic_text_input_v1",
                "schema_version": 1,
            },
            "output_renderer_hint": {
                "renderer": "json_schema",
                "schema_ref": "kernel_demo.extract_output_v1",
                "schema_version": 1,
            },
        },
        {
            "scenario_id": "kernel_demo.handoff_smoke_target_v1",
            "version": 1,
            "allowed_next_actions": ["copy_result"],
            "input_renderer_hint": {
                "renderer": "json_schema",
                "schema_ref": "kernel_demo.generic_text_input_v1",
                "schema_version": 1,
            },
            "output_renderer_hint": {
                "renderer": "json_schema",
                "schema_ref": "kernel_demo.extract_output_v1",
                "schema_version": 1,
            },
        },
    ],
    "quota_summary": {
        "quota_policy_id": "kernel_demo.guest_quota_v1",
        "unit": "scenario_run",
        "limit_count": 3,
        "period": "lifetime",
        "dimension": "product",
    },
    "allowed_ui_capabilities": [
        "capture_email",
        "continue_to_target",
        "copy_result",
        "create_handoff",
        "render_input",
        "render_output",
        "view_paywall",
    ],
}


@router.get(
    "/{product_id}/runtime-config",
    response_model=RuntimeConfigResponse,
    summary="Get frontend-safe product runtime config",
    responses={
        200: {
            "description": "Frontend-safe runtime metadata for a configured product.",
            "content": {"application/json": {"example": RUNTIME_CONFIG_EXAMPLE}},
        },
        404: {
            "model": ErrorResponse,
            "description": "Safe not-found response when the product is unknown.",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "product_not_found",
                            "message": "Product not found",
                            "request_id": "req_123",
                        }
                    }
                }
            },
        },
    },
)
def get_runtime_config(
    product_id: str,
    registry: Annotated[ConfigRegistry, Depends(get_config_registry)],
) -> RuntimeConfigResponse:
    runtime_config = build_product_runtime_config(registry, product_id)
    if runtime_config is None:
        raise ApiError(
            status_code=404,
            code="product_not_found",
            message="Product not found",
        )

    return RuntimeConfigResponse.model_validate(asdict(runtime_config))
