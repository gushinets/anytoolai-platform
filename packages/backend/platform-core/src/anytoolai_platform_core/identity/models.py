from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from anytoolai_platform_core.common.ids import new_id
from anytoolai_platform_core.common.time import utc_now


@dataclass(frozen=True)
class GuestIdentityRecord:
    tenant_id: str
    region: str
    id: str = field(default_factory=lambda: new_id("guest"))
    created_at: datetime = field(default_factory=utc_now)
    last_seen_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
