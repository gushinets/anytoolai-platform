from __future__ import annotations

from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.identity.models import GuestIdentityRecord
from anytoolai_platform_core.identity.repository import GuestIdentityRepository


class GuestIdentityNotFoundError(PlatformError):
    def __init__(self) -> None:
        super().__init__("guest_identity_not_found", "Guest identity not found.")


class GuestIdentityService:
    def __init__(
        self,
        repository: GuestIdentityRepository,
        event_emitter: EventEmitter,
    ) -> None:
        self._repository = repository
        self._event_emitter = event_emitter

    def create_guest(
        self,
        *,
        tenant_id: str,
        region: str,
        metadata: dict[str, object] | None = None,
    ) -> GuestIdentityRecord:
        record = self._repository.create(
            GuestIdentityRecord(
                tenant_id=tenant_id,
                region=region,
                metadata=dict(metadata or {}),
            )
        )
        self._event_emitter.emit(
            "guest.created",
            ExecutionContext(
                tenant_id=record.tenant_id,
                region=record.region,
                product_id="",
                frontend_id="",
                guest_id=record.id,
            ),
            properties={"guest_id": record.id},
        )
        return record

    def require_guest(
        self,
        guest_id: str,
        *,
        tenant_id: str,
        region: str,
        touch: bool = True,
    ) -> GuestIdentityRecord:
        record = self._repository.get(
            guest_id,
            tenant_id=tenant_id,
            region=region,
        )
        if record is None:
            raise GuestIdentityNotFoundError()
        if not touch:
            return record
        return self._repository.touch(record)
