from __future__ import annotations

from dataclasses import asdict

import sqlalchemy as sa
from sqlalchemy.orm import Session

from anytoolai_platform_core.actions.models import ActionRunRecord
from anytoolai_platform_core.storage.db import action_runs_table


def _require_stored_action_run(
    stored: ActionRunRecord | None, record_id: str, operation: str
) -> ActionRunRecord:
    if stored is None:
        raise RuntimeError(f"action run round-trip failed after {operation}: {record_id}")
    return stored


class ActionRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, record: ActionRunRecord) -> ActionRunRecord:
        self._session.execute(sa.insert(action_runs_table).values(asdict(record)))
        self._session.flush()
        stored = self.get(record.id)
        return _require_stored_action_run(stored, record.id, "create")

    def get(self, action_run_id: str) -> ActionRunRecord | None:
        row = (
            self._session.execute(
                sa.select(action_runs_table).where(action_runs_table.c.id == action_run_id)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else ActionRunRecord(**dict(row))

    def update(self, record: ActionRunRecord) -> ActionRunRecord:
        values = asdict(record)
        values.pop("id")
        result = self._session.execute(
            sa.update(action_runs_table)
            .where(action_runs_table.c.id == record.id)
            .values(values)
        )
        if result.rowcount == 0:
            raise LookupError(f"action run not found: {record.id}")
        self._session.flush()
        stored = self.get(record.id)
        return _require_stored_action_run(stored, record.id, "update")

    def list_for_job_step(self, job_id: str, step_id: str) -> list[ActionRunRecord]:
        rows = self._session.execute(
            sa.select(action_runs_table)
            .where(action_runs_table.c.job_id == job_id)
            .where(action_runs_table.c.step_id == step_id)
            .order_by(
                action_runs_table.c.created_at.asc(),
                action_runs_table.c.started_at.asc().nullslast(),
                action_runs_table.c.completed_at.asc().nullslast(),
                action_runs_table.c.id.asc(),
            )
        ).mappings()
        return [ActionRunRecord(**dict(row)) for row in rows]
