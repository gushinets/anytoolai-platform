from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from anytoolai_platform_core.common.ids import new_id
from anytoolai_platform_core.common.time import utc_now


class JobStatus(StrEnum):
    created = "created"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    canceled = "canceled"


@dataclass(frozen=True)
class WorkflowStepDefinition:
    step_id: str
    action_config_id: str
    input_mapping: dict[str, str] = field(default_factory=dict)
    output_mapping: dict[str, str] = field(default_factory=dict)
    when: str | None = None
    retry_count: int = 0
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowDefinition:
    workflow_id: str
    version: int
    input_schema_ref: str
    output_schema_ref: str
    steps: list[WorkflowStepDefinition]
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class JobRecord:
    tenant_id: str
    region: str
    product_id: str
    frontend_id: str
    scenario_session_id: str
    workflow_id: str
    workflow_version: int
    id: str = field(default_factory=lambda: new_id("job"))
    status: JobStatus = JobStatus.created
    input_artifact_id: str | None = None
    result_artifact_id: str | None = None
    error_code: str | None = None
    error_message_safe: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowRunResult:
    job_id: str
    workflow_id: str
    workflow_version: int
    status: JobStatus
    output_payload: dict[str, Any] | list[Any] | None = None
    result_artifact_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
