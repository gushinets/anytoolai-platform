from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from anytoolai_platform_core.common.ids import new_id
from anytoolai_platform_core.common.time import utc_now


class StructuredOutputMode(StrEnum):
    json_schema = "json_schema"


class TransportRetryOwner(StrEnum):
    provider_gateway_litellm_sdk = "provider_gateway_litellm_sdk"


class ValidationRetryOwner(StrEnum):
    pydantic_ai = "pydantic_ai"


class ProviderCallStatus(StrEnum):
    created = "created"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    timed_out = "timed_out"


@dataclass(frozen=True)
class ProviderTransportRetryPolicy:
    owner: TransportRetryOwner
    max_attempts: int
    litellm_num_retries_per_attempt: int = 0
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderValidationRetryPolicy:
    owner: ValidationRetryOwner
    max_attempts: int
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderRetryHardLimits:
    max_physical_provider_calls_per_action: int
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderRetryPolicy:
    transport: ProviderTransportRetryPolicy
    validation: ProviderValidationRetryPolicy
    hard_limits: ProviderRetryHardLimits
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderPolicy:
    provider_policy_id: str
    provider: str
    model: str
    retry_policy: ProviderRetryPolicy
    structured_output_mode: StructuredOutputMode
    temperature: float = 0.3
    timeout_seconds: int = 60
    fallback_policy: str | None = None
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
    provider_policy_id: str
    gateway_backend: str
    gateway_model: str
    provider: str
    model: str
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
    failure_kind: str | None = None
    error_code: str | None = None
    http_status: int | None = None
    pydantic_run_id: str | None = None
    litellm_response_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
