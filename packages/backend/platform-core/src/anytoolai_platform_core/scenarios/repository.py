from __future__ import annotations

from dataclasses import asdict

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.storage.db import scenario_sessions_table
from anytoolai_platform_core.storage.db_errors import is_expected_unique_violation


def _unique_constraint_columns(table: sa.Table, constraint_name: str) -> tuple[str, ...]:
    for constraint in table.constraints:
        if isinstance(constraint, sa.UniqueConstraint) and constraint.name == constraint_name:
            return tuple(constraint.columns.keys())
    raise LookupError(f"unique constraint not found on {table.name}: {constraint_name}")


EXPECTED_IDEMPOTENCY_KEY_CONSTRAINT = "uq_scenario_sessions_idempotency_key"
# Derived from the table's own constraint definition (storage/db.py) instead of a
# third hardcoded copy (the constraint itself and migration 0009's CONSTRAINT_COLUMNS
# are the other two) -- this can never silently drift out of sync with the real
# constraint's column list.
SQLITE_IDEMPOTENCY_KEY_COLUMNS: tuple[str, ...] = _unique_constraint_columns(
    scenario_sessions_table, EXPECTED_IDEMPOTENCY_KEY_CONSTRAINT
)
# Read from the column itself so this can never drift from the actual VARCHAR(256)
# limit in storage/db.py / migration 0009.
MAX_IDEMPOTENCY_KEY_LENGTH: int = scenario_sessions_table.c.idempotency_key.type.length


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


def _idempotency_key_filters(
    *,
    tenant_id: str,
    region: str,
    product_id: str,
    scenario_id: str,
    guest_id: str | None,
    idempotency_key: str,
) -> tuple[sa.ColumnElement[bool], ...]:
    return (
        scenario_sessions_table.c.tenant_id == tenant_id,
        scenario_sessions_table.c.region == region,
        scenario_sessions_table.c.product_id == product_id,
        scenario_sessions_table.c.scenario_id == scenario_id,
        scenario_sessions_table.c.guest_id == guest_id,
        scenario_sessions_table.c.idempotency_key == idempotency_key,
    )


def is_expected_idempotency_race(error: IntegrityError) -> bool:
    return is_expected_unique_violation(
        error,
        constraint_name=EXPECTED_IDEMPOTENCY_KEY_CONSTRAINT,
        table_name="scenario_sessions",
        columns=SQLITE_IDEMPOTENCY_KEY_COLUMNS,
    )


class ScenarioSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        return self._session

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

    def get_by_idempotency_key(
        self,
        *,
        tenant_id: str,
        region: str,
        product_id: str,
        scenario_id: str,
        guest_id: str | None,
        idempotency_key: str,
    ) -> ScenarioSessionRecord | None:
        # guest_id IS NULL is a documented, accepted gap in the uniqueness constraint
        # (NULL is distinct from itself), so more than one row can legitimately match
        # this filter when guest_id is None. order_by + limit(1) picks the oldest
        # (the original request) deterministically instead of letting a second
        # matching row raise MultipleResultsFound from .one_or_none().
        row = (
            self._session.execute(
                sa.select(scenario_sessions_table)
                .where(
                    *_idempotency_key_filters(
                        tenant_id=tenant_id,
                        region=region,
                        product_id=product_id,
                        scenario_id=scenario_id,
                        guest_id=guest_id,
                        idempotency_key=idempotency_key,
                    )
                )
                .order_by(
                    scenario_sessions_table.c.created_at.asc(),
                    scenario_sessions_table.c.id.asc(),
                )
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else ScenarioSessionRecord(**dict(row))

    def get_in_scope(
        self,
        scenario_session_id: str,
        *,
        tenant_id: str,
        region: str,
    ) -> ScenarioSessionRecord | None:
        row = (
            self._session.execute(
                sa.select(scenario_sessions_table).where(
                    scenario_sessions_table.c.id == scenario_session_id,
                    scenario_sessions_table.c.tenant_id == tenant_id,
                    scenario_sessions_table.c.region == region,
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
