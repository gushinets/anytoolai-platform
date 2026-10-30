from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any

from pydantic import Field, StrictBool, StringConstraints

from anytoolai_platform_sdk.contracts.base import ContractModel


class FrontendType(StrEnum):
    chrome_extension = "chrome_extension"
    web = "web"


class FrontendDefinition(ContractModel):
    frontend_id: str
    type: FrontendType
    enabled: bool = True


class UsageMetricDefinition(ContractModel):
    metric_key: Annotated[str, StringConstraints(strict=True, pattern=r"\S")]
    unit: Annotated[str, StringConstraints(strict=True, pattern=r"\S")]
    enabled: StrictBool


class ProductDefinition(ContractModel):
    product_id: Annotated[str, StringConstraints(strict=True, pattern=r"\S")]
    product_platform: str
    display_name: str
    commercial_admission_enabled: StrictBool
    usage_metrics: list[UsageMetricDefinition]
    frontends: list[FrontendDefinition] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)
    quota_policy_ref: str | None = None
    analytics: dict[str, Any] = Field(default_factory=dict)
