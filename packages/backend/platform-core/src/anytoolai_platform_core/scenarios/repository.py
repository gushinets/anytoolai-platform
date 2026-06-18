from __future__ import annotations

from dataclasses import asdict

import sqlalchemy as sa
from sqlalchemy.orm import Session

from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.storage.db import scenario_sessions_table


def _require_stored_scenario_session(
    stored: ScenarioSessionRecord | None, record_id: str, operation: str
) -> ScenarioSessionRecord:
    if stored is None:
        raise RuntimeError(
            f"scenario session round-trip failed after {operation}: {record_id}"
        )
    return stored


class ScenarioSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, record: ScenarioSessionRecord) -> ScenarioSessionRecord:
        self._session.execute(sa.insert(scenario_sessions_table).values(asdict(record)))
        self._session.flush()
        stored = self.get(record.id)
        return _require_stored_scenario_session(stored, record.id, "create")

    def get(self, scenario_session_id: str) -> ScenarioSessionRecord | None:
        row = (
            self._session.execute(
                sa.select(scenario_sessions_table).where(
                    scenario_sessions_table.c.id == scenario_session_id
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else ScenarioSessionRecord(**dict(row))

    def update(self, record: ScenarioSessionRecord) -> ScenarioSessionRecord:
        values = asdict(record)
        values.pop("id")
        result = self._session.execute(
            sa.update(scenario_sessions_table)
            .where(scenario_sessions_table.c.id == record.id)
            .values(values)
        )
        if result.rowcount == 0:
            raise LookupError(f"scenario session not found: {record.id}")
        self._session.flush()
        stored = self.get(record.id)
        return _require_stored_scenario_session(stored, record.id, "update")
