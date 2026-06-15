from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    """Base for public SDK DTOs shared across backend, CE kit, and web mirror."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(default=1, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
