from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from anytoolai_platform_core.common.ids import new_id
from anytoolai_platform_core.common.time import utc_now


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


@dataclass(frozen=True)
class QuotaUsageRecord:
    tenant_id: str
    region: str
    guest_id: str
    product_id: str
    quota_policy_id: str
    period_key: str
    limit_count: int
    id: str = field(default_factory=lambda: new_id("guest_quota_usage"))
    used_count: int = 0
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QuotaState:
    guest_id: str
    product_id: str
    quota_policy_id: str
    unit: QuotaUnit
    period: QuotaPeriod
    period_key: str
    limit_count: int
    used_count: int
    remaining_count: int
    exhausted: bool
