from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Mapping

from anytoolai_platform_core.common.ids import new_id
from anytoolai_platform_core.common.time import utc_now


class StructuredOutputMode(StrEnum):
    json_schema = "json_schema"


class ProviderCallStatus(StrEnum):
    created = "created"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    timed_out = "timed_out"


@dataclass(frozen=True)
class ProviderTransportRetryPolicy:
    owner: str = "litellm"
    max_attempts: int = 1
    litellm_num_retries_per_attempt: int = 0


@dataclass(frozen=True)
class ProviderValidationRetryPolicy:
    owner: str = "pydanticai"
    max_attempts: int = 1


@dataclass(frozen=True)
class ProviderRetryHardLimits:
    max_physical_provider_calls_per_action: int = 1


@dataclass(frozen=True)
class ProviderRetryPolicy:
    transport: ProviderTransportRetryPolicy = field(
        default_factory=ProviderTransportRetryPolicy
    )
    validation: ProviderValidationRetryPolicy = field(
        default_factory=ProviderValidationRetryPolicy
    )
    hard_limits: ProviderRetryHardLimits = field(
        default_factory=ProviderRetryHardLimits
    )


@dataclass(frozen=True)
class ProviderMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ProviderUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class ProviderRequest:
    provider_policy_ref: str
    tenant_id: str
    region: str
    product_id: str
    frontend_id: str
    scenario_session_id: str
    job_id: str
    workflow_id: str
    workflow_version: int
    step_id: str
    action_run_id: str
    action_type: str
    action_config_id: str
    prompt: str
    prompt_ref: str | None = None
    response_schema: Mapping[str, Any] | None = None
    messages: tuple[ProviderMessage, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fixture_key: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None


@dataclass(frozen=True)
class ResolvedProviderRequest:
    provider_policy_ref: str
    provider: str
    model: str
    temperature: float
    timeout_seconds: int
    retry_policy: ProviderRetryPolicy
    structured_output_mode: StructuredOutputMode
    tenant_id: str
    region: str
    product_id: str
    frontend_id: str
    scenario_session_id: str
    job_id: str
    workflow_id: str
    workflow_version: int
    step_id: str
    action_run_id: str
    action_type: str
    action_config_id: str
    prompt: str
    prompt_ref: str | None = None
    response_schema: Mapping[str, Any] | None = None
    messages: tuple[ProviderMessage, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fixture_key: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None
    semantic_attempt_index: int = 1
    transport_attempt_index: int = 1
    physical_call_index: int = 1
    pydantic_run_id: str | None = None
    fallback_from_policy_ref: str | None = None


@dataclass(frozen=True)
class ProviderResponse:
    provider_policy_ref: str
    provider: str
    model: str
    output_text: str
    status: ProviderCallStatus = ProviderCallStatus.succeeded
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    latency_ms: int = 0
    estimated_cost: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_type: str | None = None
    error_message_safe: str | None = None
    structured_output: Mapping[str, Any] | None = None
    failure_kind: str | None = None
    http_status: int | None = None
    pydantic_run_id: str | None = None
    litellm_response_id: str | None = None


@dataclass(frozen=True)
class ProviderPolicy:
    provider_policy_ref: str
    provider: str
    model: str
    temperature: float = 0.3
    timeout_seconds: int = 60
    retry_policy: ProviderRetryPolicy = field(default_factory=ProviderRetryPolicy)
    fallback_policy: str | None = None
    structured_output_mode: StructuredOutputMode = StructuredOutputMode.json_schema
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderCallRecord:
    tenant_id: str
    region: str
    product_id: str
    frontend_id: str
    scenario_session_id: str
    job_id: str
    action_run_id: str
    workflow_id: str
    workflow_version: int
    step_id: str
    action_type: str
    action_config_id: str
    provider_policy_ref: str
    provider: str
    model: str
    gateway_backend: str
    gateway_model: str
    semantic_attempt_index: int
    transport_attempt_index: int
    physical_call_index: int
    id: str = field(default_factory=lambda: new_id("provider_call"))
    status: ProviderCallStatus = ProviderCallStatus.created
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    estimated_cost: float = 0.0
    error_code: str | None = None
    error_message_safe: str | None = None
    failure_kind: str | None = None
    http_status: int | None = None
    pydantic_run_id: str | None = None
    litellm_response_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
