from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


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
    input_mapping: dict[str, Any] = field(default_factory=dict)
    output_mapping: dict[str, Any] = field(default_factory=dict)
    when: str | None = None
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
