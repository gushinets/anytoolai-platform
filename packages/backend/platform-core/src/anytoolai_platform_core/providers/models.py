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
class ProviderMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ProviderUsage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class ProviderRequest:
    provider_policy_id: str
    tenant_id: str
    region: str
    product_id: str
    frontend_id: str
    scenario_session_id: str
    job_id: str
    workflow_id: str
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
    provider_policy_id: str
    provider: str
    model: str
    temperature: float
    timeout_seconds: int
    max_retries: int
    structured_output_mode: StructuredOutputMode
    tenant_id: str
    region: str
    product_id: str
    frontend_id: str
    scenario_session_id: str
    job_id: str
    workflow_id: str
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
    attempt_number: int = 1
    fallback_from_policy_id: str | None = None


@dataclass(frozen=True)
class ProviderResponse:
    provider_policy_id: str
    provider: str
    model: str
    output_text: str
    status: ProviderCallStatus = ProviderCallStatus.succeeded
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    latency_ms: int = 0
    estimated_cost: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)
    error_type: str | None = None
    error_message_safe: str | None = None


@dataclass(frozen=True)
class ProviderPolicy:
    provider_policy_id: str
    provider: str
    model: str
    temperature: float = 0.3
    timeout_seconds: int = 60
    max_retries: int = 2
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
    step_id: str
    action_type: str
    action_config_id: str
    provider_policy_id: str
    provider: str
    model: str
    id: str = field(default_factory=lambda: new_id("provider_call"))
    status: ProviderCallStatus = ProviderCallStatus.created
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    estimated_cost: float = 0.0
    error_code: str | None = None
    error_message_safe: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
