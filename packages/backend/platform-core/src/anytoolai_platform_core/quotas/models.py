from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class QuotaUnit(StrEnum):
    scenario_run = "scenario_run"


class QuotaPeriod(StrEnum):
    lifetime = "lifetime"


@dataclass(frozen=True)
class QuotaPolicy:
    quota_policy_id: str
    unit: QuotaUnit
    limit_count: int
    period: QuotaPeriod
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
