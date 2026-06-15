from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from anytoolai_platform_sdk.contracts.base import ContractModel


class ScenarioSessionStatus(StrEnum):
    started = "started"
    waiting_for_user = "waiting_for_user"
    running = "running"
    completed = "completed"
    failed = "failed"
    expired = "expired"


class ScenarioDefinition(ContractModel):
    scenario_id: str
    version: int = Field(ge=1)
    workflow_id: str
    allowed_next_actions: list[str] = Field(default_factory=list)
