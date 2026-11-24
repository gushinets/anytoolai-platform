from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from anytoolai_platform_sdk.contracts.base import ContractModel


class JobStatus(StrEnum):
    created = "created"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    canceled = "canceled"


class WorkflowStepDefinition(ContractModel):
    step_id: str
    action_config_id: str
    input_mapping: dict[str, str] = Field(default_factory=dict)
    output_mapping: dict[str, str] = Field(default_factory=dict)
    when: str | None = None
    retry_count: int = Field(default=0, ge=0)


class WorkflowDefinition(ContractModel):
    workflow_id: str
    version: int = Field(ge=1)
    input_schema_ref: str
    output_schema_ref: str
    steps: list[WorkflowStepDefinition]
