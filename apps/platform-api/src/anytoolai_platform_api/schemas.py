from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

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
    dimension: str


class RuntimeConfigResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    frontend_ids: list[str]
    frontends: list[RuntimeFrontendResponse]
    scenario_ids: list[str]
    scenarios: list[RuntimeScenarioResponse]
    quota_summary: RuntimeQuotaSummaryResponse | None
    allowed_ui_capabilities: list[str]


class GuestIdentityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guest_id: str


class QuotaStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guest_id: str
    product_id: str
    quota_policy_id: str
    quota_dimension: str
    dimension_key: str
    scenario_id: str | None = None
    unit: str
    period: str
    limit_count: int
    used_count: int
    remaining_count: int
    exhausted: bool


class ScenarioStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frontend_id: str
    input: Any
    guest_id: str | None = None
    user_id: str | None = None
    source_frontend_instance_id: str | None = None


class ScenarioNextActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checkpoint_id: str


class ScenarioStartResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_session_id: str
    job_id: str
    status: str
    allowed_next_actions: list[str] = Field(default_factory=list)
    result_artifact_id: str | None = None


class ScenarioSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_session_id: str
    job_id: str | None
    status: str
    current_checkpoint_id: str | None = None
    allowed_next_actions: list[str] = Field(default_factory=list)
    result_artifact_id: str | None = None


class ErrorDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorDetailResponse


class HandoffCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff_definition_id: str
    source_scenario_session_id: str
    source_artifact_id: str


class HandoffAcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guest_id: str | None = None
    source_frontend_instance_id: str | None = None


class HandoffCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff_id: str
    handoff_token: str
    status: str
    expires_at: datetime


class HandoffPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff_id: str
    status: str
    source_product_id: str
    source_product_display_name: str
    target_product_id: str
    target_product_display_name: str
    target_scenario_id: str
    preview: dict[str, Any]
    expires_at: datetime
    target_scenario_session_id: str | None = None
    target_job_id: str | None = None
