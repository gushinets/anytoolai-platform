from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from anytoolai_platform_sdk.contracts.base import ContractModel


class FrontendType(StrEnum):
    chrome_extension = "chrome_extension"
    web = "web"


class FrontendDefinition(ContractModel):
    frontend_id: str
    type: FrontendType
    enabled: bool = True


class ProductDefinition(ContractModel):
    product_id: str
    product_platform: str
    display_name: str
    frontends: list[FrontendDefinition] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)
    quota_policy_ref: str | None = None
    analytics: dict[str, Any] = Field(default_factory=dict)
