from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from anytoolai_platform_core.common.ids import new_id
from anytoolai_platform_core.common.time import utc_now


class ActionExecutor(StrEnum):
    structured_llm = "structured_llm"


class ActionRunStatus(StrEnum):
    created = "created"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    canceled = "canceled"
    skipped = "skipped"


@dataclass(frozen=True)
class ActionDefinition:
    action_type: str
    version: int
    input_schema_ref: str
    output_schema_ref: str
    executor: ActionExecutor
    emits_events: list[str] = field(default_factory=list)
    description: str | None = None
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionConfiguration:
    action_config_id: str
    action_type: str
    prompt_ref: str
    provider_policy_ref: str
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionRunRecord:
    tenant_id: str
    region: str
    product_id: str
    frontend_id: str
    scenario_session_id: str
    job_id: str
    workflow_id: str
    step_id: str
    action_type: str
    action_config_id: str
    id: str = field(default_factory=lambda: new_id("action_run"))
    status: ActionRunStatus = ActionRunStatus.created
    input_artifact_id: str | None = None
    output_artifact_id: str | None = None
    error_code: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionResult:
    action_run_id: str
    action_type: str
    action_config_id: str
    status: ActionRunStatus
    output_payload: dict[str, Any] | list[Any] | None = None
    output_artifact_id: str | None = None
    provider_policy_ref: str | None = None
    provider: str | None = None
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
