from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from anytoolai_platform_core.common.ids import new_id
from anytoolai_platform_core.common.time import utc_now


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


@dataclass(frozen=True)
class ScenarioSessionRecord:
    tenant_id: str
    region: str
    product_id: str
    frontend_id: str
    scenario_id: str
    scenario_version: int
    id: str = field(default_factory=lambda: new_id("scenario_session"))
    guest_id: str | None = None
    user_id: str | None = None
    status: ScenarioSessionStatus = ScenarioSessionStatus.started
    current_checkpoint_id: str | None = None
    current_step: str | None = None
    scenario_chain_id: str | None = None
    parent_scenario_session_id: str | None = None
    source_frontend_instance_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime = field(default_factory=utc_now)
    last_event_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True)
class ScenarioSessionSnapshot:
    scenario_session_id: str
    job_id: str
    status: ScenarioSessionStatus
    allowed_next_actions: tuple[str, ...] = field(default_factory=tuple)
    result_artifact_id: str | None = None
    current_checkpoint_id: str | None = None
