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


def _scenario_session_scope_filters(
    *,
    tenant_id: str,
    region: str,
    product_id: str,
    frontend_id: str,
) -> tuple[sa.ColumnElement[bool], ...]:
    return (
        scenario_sessions_table.c.tenant_id == tenant_id,
        scenario_sessions_table.c.region == region,
        scenario_sessions_table.c.product_id == product_id,
        scenario_sessions_table.c.frontend_id == frontend_id,
    )


class ScenarioSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, record: ScenarioSessionRecord) -> ScenarioSessionRecord:
        self._session.execute(sa.insert(scenario_sessions_table).values(asdict(record)))
        self._session.flush()
        stored = self.get(
            record.id,
            tenant_id=record.tenant_id,
            region=record.region,
            product_id=record.product_id,
            frontend_id=record.frontend_id,
        )
        return _require_stored_scenario_session(stored, record.id, "create")

    def get(
        self,
        scenario_session_id: str,
        *,
        tenant_id: str,
        region: str,
        product_id: str,
        frontend_id: str,
    ) -> ScenarioSessionRecord | None:
        row = (
            self._session.execute(
                sa.select(scenario_sessions_table).where(
                    scenario_sessions_table.c.id == scenario_session_id,
                    *_scenario_session_scope_filters(
                        tenant_id=tenant_id,
                        region=region,
                        product_id=product_id,
                        frontend_id=frontend_id,
                    ),
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else ScenarioSessionRecord(**dict(row))

    def update(
        self,
        record: ScenarioSessionRecord,
        *,
        tenant_id: str,
        region: str,
        product_id: str,
        frontend_id: str,
    ) -> ScenarioSessionRecord:
        existing = self.get(
            record.id,
            tenant_id=tenant_id,
            region=region,
            product_id=product_id,
            frontend_id=frontend_id,
        )
        if existing is None:
            raise LookupError(f"scenario session not found: {record.id}")

        values = asdict(record)
        values.pop("id")
        values.pop("tenant_id")
        values.pop("region")
        values.pop("product_id")
        values.pop("frontend_id")
        result = self._session.execute(
            sa.update(scenario_sessions_table)
            .where(
                scenario_sessions_table.c.id == record.id,
                *_scenario_session_scope_filters(
                    tenant_id=tenant_id,
                    region=region,
                    product_id=product_id,
                    frontend_id=frontend_id,
                ),
            )
            .values(values)
        )
        if result.rowcount == 0:
            raise LookupError(f"scenario session not found: {record.id}")
        self._session.flush()
        stored = self.get(
            record.id,
            tenant_id=existing.tenant_id,
            region=existing.region,
            product_id=existing.product_id,
            frontend_id=existing.frontend_id,
        )
        return _require_stored_scenario_session(stored, record.id, "update")
