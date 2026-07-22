from __future__ import annotations

from dataclasses import asdict, replace

import sqlalchemy as sa
from sqlalchemy.orm import Session

from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.identity.models import GuestIdentityRecord
from anytoolai_platform_core.storage.db import guest_identities_table


def _require_stored_guest(
    stored: GuestIdentityRecord | None,
    record_id: str,
    operation: str,
) -> GuestIdentityRecord:
    if stored is None:
        raise RuntimeError(f"guest identity round-trip failed after {operation}: {record_id}")
    return stored


class GuestIdentityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, record: GuestIdentityRecord) -> GuestIdentityRecord:
        self._session.execute(sa.insert(guest_identities_table).values(asdict(record)))
        self._session.flush()
        stored = self.get(record.id, tenant_id=record.tenant_id, region=record.region)
        return _require_stored_guest(stored, record.id, "create")

    def get(
        self,
        guest_id: str,
        *,
        tenant_id: str,
        region: str,
    ) -> GuestIdentityRecord | None:
        row = (
            self._session.execute(
                sa.select(guest_identities_table).where(
                    guest_identities_table.c.id == guest_id,
                    guest_identities_table.c.tenant_id == tenant_id,
                    guest_identities_table.c.region == region,
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else GuestIdentityRecord(**dict(row))

    def touch(
        self,
        record: GuestIdentityRecord,
    ) -> GuestIdentityRecord:
        touched = replace(record, last_seen_at=utc_now())
        result = self._session.execute(
            sa.update(guest_identities_table)
            .where(
                guest_identities_table.c.id == touched.id,
                guest_identities_table.c.tenant_id == touched.tenant_id,
                guest_identities_table.c.region == touched.region,
            )
            .values(last_seen_at=touched.last_seen_at)
        )
        if result.rowcount == 0:
            raise LookupError(f"guest identity not found: {record.id}")
        self._session.flush()
        stored = self.get(touched.id, tenant_id=touched.tenant_id, region=touched.region)
        return _require_stored_guest(stored, touched.id, "touch")
