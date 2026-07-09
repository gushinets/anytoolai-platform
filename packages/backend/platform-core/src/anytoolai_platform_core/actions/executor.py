from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class ActionExecutorRequest:
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
    action_type: str = ""
    action_config_id: str = ""
    input_payload: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    guest_id: str | None = None
    user_id: str | None = None
    fixture_key: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None


@dataclass(frozen=True)
class ProviderCallInfo:
    provider_policy_ref: str
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    estimated_cost: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionExecutorResponse:
    structured_output: Mapping[str, Any] | None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    provider_call: ProviderCallInfo | None = None


class ActionExecutor(Protocol):
    executor_id: str

    async def execute(
        self,
        request: ActionExecutorRequest,
        *,
        session: Any,
    ) -> ActionExecutorResponse: ...
