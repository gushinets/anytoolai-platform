from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class FrontendType(StrEnum):
    chrome_extension = "chrome_extension"
    web = "web"


@dataclass(frozen=True)
class FrontendDefinition:
    frontend_id: str
    type: FrontendType
    enabled: bool = True
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProductDefinition:
    product_id: str
    product_platform: str
    display_name: str
    frontends: tuple[FrontendDefinition, ...] = field(default_factory=tuple)
    scenarios: tuple[str, ...] = field(default_factory=tuple)
    quota_policy_ref: str | None = None
    analytics: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "frontends", tuple(self.frontends))
        object.__setattr__(self, "scenarios", tuple(self.scenarios))
