from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from anytoolai_platform_sdk.contracts.base import ContractModel


class ActionExecutor(StrEnum):
    structured_llm = "structured_llm"


class ActionDefinition(ContractModel):
    action_type: str
    version: int = Field(ge=1)
    input_schema_ref: str
    output_schema_ref: str
    executor: ActionExecutor
    emits_events: list[str] = Field(default_factory=list)
    description: str | None = None


class ActionConfiguration(ContractModel):
    action_config_id: str
    action_type: str
    prompt_ref: str
    provider_policy_ref: str
