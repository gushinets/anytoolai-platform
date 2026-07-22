from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from anytoolai_platform_sdk.contracts.base import ContractModel


class QuotaUnit(StrEnum):
    scenario_run = "scenario_run"


class QuotaPeriod(StrEnum):
    lifetime = "lifetime"


class QuotaDimension(StrEnum):
    product = "product"
    scenario = "scenario"


class QuotaPolicy(ContractModel):
    quota_policy_id: str
    unit: QuotaUnit
    limit_count: int = Field(gt=0)
    period: QuotaPeriod
    dimension: QuotaDimension
