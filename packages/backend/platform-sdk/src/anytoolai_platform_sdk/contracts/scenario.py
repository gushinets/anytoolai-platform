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
    # ANY-221: mirrors anytoolai_platform_core.scenarios.models.ScenarioDefinition.internal_only
    # -- see its own docstring. Kept in the SDK contract (not core-only) so any consumer holding a
    # ScenarioDefinition can tell an internal-only (live-canary) scenario apart from a normal one.
    internal_only: bool = False
