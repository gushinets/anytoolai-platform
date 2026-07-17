from __future__ import annotations

from dataclasses import asdict
from typing import Any

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

    def exists_event(
        self,
        *,
        event_type: str,
        job_id: str | None = None,
        action_run_id: str | None = None,
        provider_call_id: str | None = None,
        artifact_id: str | None = None,
        step_id: str | None = None,
    ) -> bool:
        conditions = [event_log_table.c.event_type == event_type]
        if job_id is not None:
            conditions.append(event_log_table.c.job_id == job_id)
        if action_run_id is not None:
            conditions.append(event_log_table.c.action_run_id == action_run_id)
        if provider_call_id is not None:
            conditions.append(event_log_table.c.provider_call_id == provider_call_id)
        if artifact_id is not None:
            conditions.append(event_log_table.c.artifact_id == artifact_id)

        rows = self._session.execute(
            sa.select(event_log_table.c.properties).where(*conditions)
        ).scalars()
        if step_id is None:
            return rows.first() is not None

        for properties in rows:
            if _event_properties_step_id(properties) == step_id:
                return True
        return False


def _event_properties_step_id(properties: Any) -> str | None:
    if not isinstance(properties, dict):
        return None
    step_id = properties.get("step_id")
    return step_id if isinstance(step_id, str) and step_id else None
