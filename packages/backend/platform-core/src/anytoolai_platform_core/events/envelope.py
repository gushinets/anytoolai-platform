from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class EventEnvelope:
    event_id: str
    event_type: str
    timestamp: datetime
    tenant_id: str
    region: str
    product_id: str | None = None
    frontend_id: str | None = None
    guest_id: str | None = None
    user_id: str | None = None
    scenario_session_id: str | None = None
    scenario_chain_id: str | None = None
    job_id: str | None = None
    workflow_id: str | None = None
    workflow_version: int | None = None
    action_run_id: str | None = None
    action_type: str | None = None
    action_config_id: str | None = None
    provider_policy_ref: str | None = None
    provider_call_id: str | None = None
    provider: str | None = None
    model: str | None = None
    physical_call_index: int | None = None
    pydantic_run_id: str | None = None
    litellm_response_id: str | None = None
    artifact_id: str | None = None
    handoff_id: str | None = None
    result_status: str | None = None
    error_code: str | None = None
    acquisition_source: str | None = None
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
    properties: dict[str, Any] = field(default_factory=dict)
