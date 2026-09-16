from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from anytoolai_platform_core.events.client_events import WebClientEventType
from anytoolai_platform_core.handoffs.models import HandoffStatus
from anytoolai_platform_core.products.models import FrontendType
from anytoolai_platform_core.providers.models import (
    ModelCatalogCompatibility,
    ModelCatalogReason,
    ModelCatalogRefreshStatus,
    ReasoningEffort,
)
from anytoolai_platform_core.quotas.models import QuotaDimension, QuotaPeriod, QuotaUnit
from anytoolai_platform_core.scenarios.models import ScenarioSessionStatus
from pydantic import BaseModel, ConfigDict, Field


class RuntimeRendererHintResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    renderer: Literal["json_schema"] = "json_schema"
    schema_ref: str
    schema_version: int | None = None


class RuntimeFrontendResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frontend_id: str
    type: FrontendType
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
    unit: QuotaUnit
    limit_count: int
    period: QuotaPeriod
    dimension: QuotaDimension


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
    quota_dimension: QuotaDimension
    dimension_key: str
    scenario_id: str | None = None
    unit: QuotaUnit
    period: QuotaPeriod
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
    status: ScenarioSessionStatus
    allowed_next_actions: list[str] = Field(default_factory=list)
    result_artifact_id: str | None = None


class ClientEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: WebClientEventType
    product_id: str
    frontend_id: str
    web_session_id: str
    guest_id: str | None = None
    user_id: str | None = None
    scenario_session_id: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class ClientEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: WebClientEventType


class DemoRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    demo_id: str
    source_text: str


class AtomLabVersionedSchemaRefResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_ref: str
    version: int


class AtomLabSchemaRefsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: AtomLabVersionedSchemaRefResponse
    output: AtomLabVersionedSchemaRefResponse


class AtomLabAtomId(StrEnum):
    A01 = "A01"
    A02 = "A02"
    A03 = "A03"
    A04 = "A04"
    A05 = "A05"
    A06 = "A06"
    A07 = "A07"
    A08 = "A08"
    A09 = "A09"
    A10 = "A10"
    A11 = "A11"


class AtomLabAtomResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    atom_id: AtomLabAtomId
    action_type: str
    base_action_config_id: str
    prompt: str
    prompt_ref: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    schema_refs: AtomLabSchemaRefsResponse
    description: str
    example_input: dict[str, Any]


class AtomLabModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str
    compatibility: ModelCatalogCompatibility
    reason: ModelCatalogReason
    reasoning_supported: bool | None
    allowed_reasoning_efforts: list[ReasoningEffort] | None
    provenance: dict[str, dict[str, str]]


class AtomLabModelsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AtomLabModelResponse]
    snapshot_id: str | None
    last_success_at: datetime | None
    stale: bool
    refresh_status: ModelCatalogRefreshStatus
    error: str | None


class AtomLabModelRefreshResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str | None
    last_success_at: datetime | None
    stale: bool
    refresh_status: ModelCatalogRefreshStatus
    error: str | None


class AtomLabPresetVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=256)
    description: str = Field(max_length=4096)
    atom_id: AtomLabAtomId
    base_action_config_id: str = Field(min_length=1, max_length=128)
    schema_refs: AtomLabSchemaRefsResponse
    prompt: str = Field(min_length=1, max_length=65536)
    prompt_ref: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=256)
    reasoning_effort: ReasoningEffort | None = None
    fixed_fields: list[str] = Field(default_factory=list)
    example_input: dict[str, Any]
    source_run_id: str | None = Field(default=None, max_length=128)


class AtomLabPresetNextVersionRequest(AtomLabPresetVersionRequest):
    base_version: int = Field(ge=1)


class AtomLabPresetCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset_id: str
    version: int
    created_at: datetime


class AtomLabPresetVersionResponse(AtomLabPresetVersionRequest):
    preset_id: str
    version: int
    created_at: datetime


class AtomLabPresetSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset_id: str
    latest_version: int
    name: str
    description: str
    atom_id: AtomLabAtomId
    created_at: datetime
    updated_at: datetime


class AtomLabPresetVersionSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset_id: str
    version: int
    name: str
    description: str
    atom_id: AtomLabAtomId
    created_at: datetime


class AtomLabPresetListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AtomLabPresetSummaryResponse]
    next_cursor: str | None


class AtomLabPresetVersionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AtomLabPresetVersionSummaryResponse]
    next_cursor: str | None


class AtomLabPresetExportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format_version: Literal[1] = 1
    preset_id: str
    version: int
    configuration: AtomLabPresetVersionRequest


class ScenarioSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_session_id: str
    job_id: str | None
    status: ScenarioSessionStatus
    current_checkpoint_id: str | None = None
    allowed_next_actions: list[str] = Field(default_factory=list)
    result_artifact_id: str | None = None


class ResultArtifactResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_artifact_id: str
    scenario_session_id: str
    job_id: str
    workflow_id: str
    workflow_version: int
    schema_ref: str
    schema_version: int
    created_at: datetime
    output: dict[str, Any]


class ErrorDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorDetailResponse


class AtomLabFieldErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    message: str


class AtomLabErrorDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    field_errors: list[AtomLabFieldErrorResponse]


class AtomLabErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: AtomLabErrorDetailResponse
    request_id: str


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
    status: HandoffStatus
    expires_at: datetime


class HandoffPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff_id: str
    status: HandoffStatus
    source_product_id: str
    source_product_display_name: str
    target_product_id: str
    target_product_display_name: str
    target_scenario_id: str
    preview: dict[str, Any]
    expires_at: datetime
    target_scenario_session_id: str | None = None
    target_job_id: str | None = None
