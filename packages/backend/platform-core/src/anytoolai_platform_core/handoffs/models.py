from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from anytoolai_platform_core.common.ids import new_id
from anytoolai_platform_core.common.time import utc_now


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


@dataclass(frozen=True)
class HandoffDefinition:
    handoff_id: str
    source_product_id: str
    source_scenario_id: str
    target_product_id: str
    target_frontend_id: str
    target_scenario_id: str
    target_start_policy: HandoffStartPolicy
    consent_required: bool
    context_mapping: dict[str, str] = field(default_factory=dict)
    preview_mapping: dict[str, str] = field(default_factory=dict)
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HandoffRecord:
    handoff_definition_id: str
    tenant_id: str
    region: str
    token_hash: str
    source_product_id: str
    source_frontend_id: str
    source_scenario_id: str
    source_scenario_session_id: str
    source_job_id: str
    source_artifact_id: str
    target_product_id: str
    target_frontend_id: str
    target_scenario_id: str
    scenario_chain_id: str
    consent_required: bool
    target_start_policy: HandoffStartPolicy
    context_payload: dict[str, Any]
    preview_payload: dict[str, Any]
    expires_at: datetime
    id: str = field(default_factory=lambda: new_id("handoff"))
    status: HandoffStatus = HandoffStatus.created
    target_scenario_session_id: str | None = None
    target_job_id: str | None = None
    created_by_guest_id: str | None = None
    accepted_by_guest_id: str | None = None
    accepted_from_frontend_instance_id: str | None = None
    error_code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    viewed_at: datetime | None = None
    accepted_at: datetime | None = None
    declined_at: datetime | None = None
    consumed_at: datetime | None = None
    expired_at: datetime | None = None
    failed_at: datetime | None = None


@dataclass(frozen=True)
class CreateHandoffCommand:
    tenant_id: str
    region: str
    handoff_definition_id: str
    source_scenario_session_id: str
    source_artifact_id: str


@dataclass(frozen=True)
class AcceptHandoffCommand:
    tenant_id: str
    region: str
    guest_id: str | None = None
    source_frontend_instance_id: str | None = None


@dataclass(frozen=True)
class HandoffPreview:
    handoff_id: str
    status: HandoffStatus
    source_product_id: str
    source_product_display_name: str
    target_product_id: str
    target_product_display_name: str
    target_scenario_id: str
    preview: dict[str, Any]
    expires_at: datetime
    target_scenario_session_id: str | None = None
    target_job_id: str | None = None


@dataclass(frozen=True)
class HandoffCreated:
    preview: HandoffPreview
    handoff_token: str


@dataclass(frozen=True)
class HandoffAccepted:
    preview: HandoffPreview


@dataclass(frozen=True)
class HandoffTransitionResult:
    record: HandoffRecord
    changed: bool
