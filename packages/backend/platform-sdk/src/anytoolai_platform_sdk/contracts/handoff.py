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


class HandoffStartPolicy(StrEnum):
    immediate = "immediate"
    deferred = "deferred"


class HandoffDefinition(ContractModel):
    handoff_id: str
    source_product_id: str
    source_scenario_id: str
    target_product_id: str
    target_frontend_id: str
    target_scenario_id: str
    target_start_policy: HandoffStartPolicy
    consent_required: bool
    context_mapping: dict[str, str] = Field(default_factory=dict)
    preview_mapping: dict[str, str] = Field(default_factory=dict)
