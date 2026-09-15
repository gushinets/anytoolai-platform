from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.orm import Session

from anytoolai_platform_core.common.ids import new_id
from anytoolai_platform_core.providers.catalog import (
    ModelCatalogItem,
    deserialize_catalog_item,
    serialize_catalog_item,
)
from anytoolai_platform_core.providers.models import ModelCatalogRefreshStatus
from anytoolai_platform_core.storage.db import model_catalog_state_table


@dataclass(frozen=True)
class ModelCatalogLease:
    account_scope: str
    lease_id: str


@dataclass(frozen=True)
class ModelCatalogState:
    account_scope: str
    snapshot_id: str | None
    items: tuple[ModelCatalogItem, ...]
    due_at: datetime
    refresh_requested_at: datetime | None
    lease_id: str | None
    lease_until: datetime | None
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None

    def refresh_status(self, now: datetime) -> ModelCatalogRefreshStatus:
        if self.lease_id is not None and self.lease_until is not None and self.lease_until > now:
            return ModelCatalogRefreshStatus.running
        if self.refresh_requested_at is not None:
            return ModelCatalogRefreshStatus.pending
        if self.due_at <= now:
            return ModelCatalogRefreshStatus.pending
        return ModelCatalogRefreshStatus.current

    def is_stale(self, now: datetime) -> bool:
        return self.snapshot_id is None or self.last_error is not None or self.due_at <= now


class ModelCatalogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, account_scope: str) -> ModelCatalogState | None:
        row = (
            self._session.execute(
                sa.select(model_catalog_state_table).where(
                    model_catalog_state_table.c.account_scope == account_scope
                )
            )
            .mappings()
            .one_or_none()
        )
        return self._from_row(row)

    def request_refresh(
        self, account_scope: str, *, now: datetime, cooldown: timedelta
    ) -> ModelCatalogState:
        row = self._get_or_create_for_update(account_scope, now=now)
        active_lease = row["lease_until"] is not None and row["lease_until"] > now
        cooling_down = (
            row["last_attempt_at"] is not None and row["last_attempt_at"] + cooldown > now
        )
        if not active_lease and row["refresh_requested_at"] is None and not cooling_down:
            self._session.execute(
                sa.update(model_catalog_state_table)
                .where(model_catalog_state_table.c.account_scope == account_scope)
                .values(refresh_requested_at=now, updated_at=now)
            )
            row = self._select_for_update(account_scope)
        state = self._from_row(row)
        if state is None:  # pragma: no cover - insert/select invariant
            raise RuntimeError("model catalog state disappeared")
        return state

    def claim_refresh(
        self, account_scope: str, *, now: datetime, lease_duration: timedelta
    ) -> ModelCatalogLease | None:
        row = self._get_or_create_for_update(account_scope, now=now)
        if row["lease_until"] is not None and row["lease_until"] > now:
            return None
        if row["refresh_requested_at"] is None and row["due_at"] > now:
            return None
        lease_id = new_id("model_catalog_lease")
        self._session.execute(
            sa.update(model_catalog_state_table)
            .where(model_catalog_state_table.c.account_scope == account_scope)
            .values(
                lease_id=lease_id,
                lease_until=now + lease_duration,
                last_attempt_at=now,
                updated_at=now,
            )
        )
        return ModelCatalogLease(account_scope=account_scope, lease_id=lease_id)

    def complete_refresh(
        self,
        lease: ModelCatalogLease,
        *,
        snapshot_id: str,
        items: tuple[ModelCatalogItem, ...],
        now: datetime,
        ttl: timedelta,
        source_snapshot: Mapping[str, Any] | None = None,
    ) -> None:
        result = self._session.execute(
            sa.update(model_catalog_state_table)
            .where(
                model_catalog_state_table.c.account_scope == lease.account_scope,
                model_catalog_state_table.c.lease_id == lease.lease_id,
                model_catalog_state_table.c.lease_until > sa.func.clock_timestamp(),
            )
            .values(
                snapshot_id=snapshot_id,
                snapshot={
                    "items": [serialize_catalog_item(item) for item in items],
                    "sources": dict(source_snapshot or {}),
                },
                due_at=now + ttl,
                refresh_requested_at=None,
                lease_id=None,
                lease_until=None,
                last_success_at=now,
                last_error=None,
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            raise ValueError("model catalog refresh lease is no longer owned")

    def fail_refresh(
        self,
        lease: ModelCatalogLease,
        *,
        error: str,
        now: datetime,
        retry_after: timedelta,
    ) -> None:
        result = self._session.execute(
            sa.update(model_catalog_state_table)
            .where(
                model_catalog_state_table.c.account_scope == lease.account_scope,
                model_catalog_state_table.c.lease_id == lease.lease_id,
                model_catalog_state_table.c.lease_until > sa.func.clock_timestamp(),
            )
            .values(
                due_at=now + retry_after,
                refresh_requested_at=None,
                lease_id=None,
                lease_until=None,
                last_error=error[:512],
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            raise ValueError("model catalog refresh lease is no longer owned")

    def _get_or_create_for_update(self, account_scope: str, *, now: datetime) -> sa.RowMapping:
        if not account_scope.strip():
            raise ValueError("model catalog account_scope must not be blank")
        self._session.execute(
            postgresql_insert(model_catalog_state_table)
            .values(
                account_scope=account_scope,
                due_at=now,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=[model_catalog_state_table.c.account_scope])
        )
        return self._select_for_update(account_scope)

    def _select_for_update(self, account_scope: str) -> sa.RowMapping:
        return (
            self._session.execute(
                sa.select(model_catalog_state_table)
                .where(model_catalog_state_table.c.account_scope == account_scope)
                .with_for_update()
            )
            .mappings()
            .one()
        )

    @staticmethod
    def _from_row(row: sa.RowMapping | None) -> ModelCatalogState | None:
        if row is None:
            return None
        snapshot = row["snapshot"]
        raw_items: list[Any] = []
        if isinstance(snapshot, dict) and isinstance(snapshot.get("items"), list):
            raw_items = snapshot["items"]
        return ModelCatalogState(
            account_scope=row["account_scope"],
            snapshot_id=row["snapshot_id"],
            items=tuple(
                deserialize_catalog_item(item) for item in raw_items if isinstance(item, dict)
            ),
            due_at=row["due_at"],
            refresh_requested_at=row["refresh_requested_at"],
            lease_id=row["lease_id"],
            lease_until=row["lease_until"],
            last_attempt_at=row["last_attempt_at"],
            last_success_at=row["last_success_at"],
            last_error=row["last_error"],
        )
