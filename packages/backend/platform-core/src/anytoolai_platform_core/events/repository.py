from __future__ import annotations

from dataclasses import asdict

import sqlalchemy as sa
from sqlalchemy.orm import Session

from anytoolai_platform_core.events.envelope import EventEnvelope
from anytoolai_platform_core.storage.db import event_log_table


def _require_stored_event(
    stored: EventEnvelope | None, record_id: str, operation: str
) -> EventEnvelope:
    if stored is None:
        raise RuntimeError(f"event round-trip failed after {operation}: {record_id}")
    return stored


class EventLogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, record: EventEnvelope) -> EventEnvelope:
        values = asdict(record)
        values.pop("schema_version", None)
        values.pop("metadata", None)
        self._session.execute(sa.insert(event_log_table).values(values))
        self._session.flush()
        stored = self.get(record.event_id)
        return _require_stored_event(stored, record.event_id, "create")

    def get(self, event_id: str) -> EventEnvelope | None:
        row = (
            self._session.execute(
                sa.select(event_log_table).where(event_log_table.c.event_id == event_id)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else EventEnvelope(**dict(row))
