from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from anytoolai_platform_sdk.contracts.base import ContractModel


class HandoffStatus(StrEnum):
    created = "created"
    viewed = "viewed"
    accepted = "accepted"
    declined = "declined"
    consumed = "consumed"
    expired = "expired"
    failed = "failed"


class HandoffDefinition(ContractModel):
    handoff_id: str
    source_product_id: str
    source_scenario_id: str
    target_product_id: str
    target_scenario_id: str
    consent_required: bool = True
    context_mapping: dict[str, str] = Field(default_factory=dict)
