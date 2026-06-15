from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from anytoolai_platform_sdk.contracts.base import ContractModel


class EventEnvelope(ContractModel):
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
    action_type: str | None = None
    action_config_id: str | None = None
    provider: str | None = None
    model: str | None = None
    artifact_id: str | None = None
    handoff_id: str | None = None
    result_status: str | None = None
    error_code: str | None = None
    acquisition_source: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
