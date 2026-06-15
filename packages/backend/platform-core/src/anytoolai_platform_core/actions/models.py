from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ActionExecutor(StrEnum):
    structured_llm = "structured_llm"


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
