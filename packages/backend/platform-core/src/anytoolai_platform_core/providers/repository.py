from __future__ import annotations

from dataclasses import asdict

import sqlalchemy as sa
from sqlalchemy.orm import Session

from anytoolai_platform_core.providers.models import ProviderCallRecord
from anytoolai_platform_core.storage.db import provider_calls_table


def _require_stored_provider_call(
    stored: ProviderCallRecord | None, record_id: str, operation: str
) -> ProviderCallRecord:
    if stored is None:
        raise RuntimeError(
            f"provider call round-trip failed after {operation}: {record_id}"
        )
    return stored


class ProviderCallRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, record: ProviderCallRecord) -> ProviderCallRecord:
        self._session.execute(sa.insert(provider_calls_table).values(asdict(record)))
        self._session.flush()
        stored = self.get(record.id)
        return _require_stored_provider_call(stored, record.id, "create")

    def get(self, provider_call_id: str) -> ProviderCallRecord | None:
        row = (
            self._session.execute(
                sa.select(provider_calls_table).where(provider_calls_table.c.id == provider_call_id)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else ProviderCallRecord(**dict(row))

    def update(self, record: ProviderCallRecord) -> ProviderCallRecord:
        values = asdict(record)
        values.pop("id")
        result = self._session.execute(
            sa.update(provider_calls_table)
            .where(provider_calls_table.c.id == record.id)
            .values(values)
        )
        if result.rowcount == 0:
            raise LookupError(f"provider call not found: {record.id}")
        self._session.flush()
        stored = self.get(record.id)
        return _require_stored_provider_call(stored, record.id, "update")
