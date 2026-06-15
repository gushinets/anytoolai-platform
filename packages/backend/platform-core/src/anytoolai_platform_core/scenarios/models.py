from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ScenarioSessionStatus(StrEnum):
    started = "started"
    waiting_for_user = "waiting_for_user"
    running = "running"
    completed = "completed"
    failed = "failed"
    expired = "expired"


@dataclass(frozen=True)
class ScenarioDefinition:
    scenario_id: str
    version: int
    workflow_id: str
    allowed_next_actions: list[str] = field(default_factory=list)
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
