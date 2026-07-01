from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RuntimeRendererHintResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    renderer: Literal["json_schema"] = "json_schema"
    schema_ref: str
    schema_version: int | None = None


class RuntimeFrontendResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frontend_id: str
    type: str
    enabled: bool


class RuntimeScenarioResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    version: int
    allowed_next_actions: list[str] = Field(default_factory=list)
    input_renderer_hint: RuntimeRendererHintResponse
    output_renderer_hint: RuntimeRendererHintResponse


class RuntimeQuotaSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quota_policy_id: str
    unit: str
    limit_count: int
    period: str


class RuntimeConfigResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    frontend_ids: list[str]
    frontends: list[RuntimeFrontendResponse]
    scenario_ids: list[str]
    scenarios: list[RuntimeScenarioResponse]
    quota_summary: RuntimeQuotaSummaryResponse | None
    allowed_ui_capabilities: list[str]


class ErrorDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorDetailResponse
