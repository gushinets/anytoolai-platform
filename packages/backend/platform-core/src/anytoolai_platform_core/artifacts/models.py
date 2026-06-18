from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from anytoolai_platform_core.common.ids import new_id
from anytoolai_platform_core.common.time import utc_now


class ArtifactStatus(StrEnum):
    created = "created"
    stored = "stored"
    failed = "failed"


@dataclass(frozen=True)
class ArtifactRecord:
    tenant_id: str
    region: str
    product_id: str
    frontend_id: str
    scenario_session_id: str
    artifact_type: str
    id: str = field(default_factory=lambda: new_id("artifact"))
    status: ArtifactStatus = ArtifactStatus.created
    job_id: str | None = None
    action_run_id: str | None = None
    content_text: str | None = None
    content_json: Any | None = None
    object_storage_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
