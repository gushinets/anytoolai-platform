from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class HandoffStatus(StrEnum):
    created = "created"
    viewed = "viewed"
    accepted = "accepted"
    declined = "declined"
    consumed = "consumed"
    expired = "expired"
    failed = "failed"


@dataclass(frozen=True)
class HandoffDefinition:
    handoff_id: str
    source_product_id: str
    source_scenario_id: str
    target_product_id: str
    target_scenario_id: str
    consent_required: bool = True
    context_mapping: dict[str, str] = field(default_factory=dict)
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
