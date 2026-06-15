from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class StructuredOutputMode(StrEnum):
    json_schema = "json_schema"


@dataclass(frozen=True)
class ProviderPolicy:
    provider_policy_id: str
    provider: str
    model: str
    temperature: float = 0.3
    timeout_seconds: int = 60
    max_retries: int = 2
    fallback_policy: str | None = None
    structured_output_mode: StructuredOutputMode = StructuredOutputMode.json_schema
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
