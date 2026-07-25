from __future__ import annotations

from dataclasses import asdict, replace

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.quotas.models import QuotaDimension, QuotaUsageRecord
from anytoolai_platform_core.storage.db import guest_quota_usage_table

EXPECTED_USAGE_DIMENSION_CONSTRAINT = "uq_guest_quota_usage_dimension"
SQLITE_USAGE_DIMENSION_COLUMNS = (
    "tenant_id",
    "region",
    "guest_id",
    "product_id",
    "quota_policy_id",
    "quota_dimension",
    "dimension_key",
    "period_key",
)


def _usage_dimension_filters(
    *,
    tenant_id: str,
    region: str,
    guest_id: str,
    product_id: str,
    quota_policy_id: str,
    quota_dimension: QuotaDimension,
    dimension_key: str,
    period_key: str,
) -> tuple[sa.ColumnElement[bool], ...]:
    return (
        guest_quota_usage_table.c.tenant_id == tenant_id,
        guest_quota_usage_table.c.region == region,
        guest_quota_usage_table.c.guest_id == guest_id,
        guest_quota_usage_table.c.product_id == product_id,
        guest_quota_usage_table.c.quota_policy_id == quota_policy_id,
        guest_quota_usage_table.c.quota_dimension == quota_dimension.value,
        guest_quota_usage_table.c.dimension_key == dimension_key,
        guest_quota_usage_table.c.period_key == period_key,
    )


def _require_stored_usage(
    stored: QuotaUsageRecord | None,
    record_id: str,
    operation: str,
) -> QuotaUsageRecord:
    if stored is None:
        raise RuntimeError(f"quota usage round-trip failed after {operation}: {record_id}")
    return stored


def _record_from_row(row: sa.RowMapping) -> QuotaUsageRecord:
    data = dict(row)
    data["quota_dimension"] = QuotaDimension(data["quota_dimension"])
    return QuotaUsageRecord(**data)


def _is_expected_usage_dimension_race(error: IntegrityError) -> bool:
    constraint_name = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
    if constraint_name == EXPECTED_USAGE_DIMENSION_CONSTRAINT:
        return True

    message = str(error.orig)
    if EXPECTED_USAGE_DIMENSION_CONSTRAINT in message:
        return True
    if "UNIQUE constraint failed" not in message:
        return False
    return all(
        f"guest_quota_usage.{column}" in message
        for column in SQLITE_USAGE_DIMENSION_COLUMNS
    )


class QuotaUsageRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        return self._session

    def get(self, usage_id: str) -> QuotaUsageRecord | None:
        row = (
            self._session.execute(
                sa.select(guest_quota_usage_table).where(
                    guest_quota_usage_table.c.id == usage_id
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _record_from_row(row)

    def get_by_dimension(
        self,
        *,
        tenant_id: str,
        region: str,
        guest_id: str,
        product_id: str,
        quota_policy_id: str,
        quota_dimension: QuotaDimension,
        dimension_key: str,
        period_key: str,
    ) -> QuotaUsageRecord | None:
        row = (
            self._session.execute(
                sa.select(guest_quota_usage_table).where(
                    *_usage_dimension_filters(
                        tenant_id=tenant_id,
                        region=region,
                        guest_id=guest_id,
                        product_id=product_id,
                        quota_policy_id=quota_policy_id,
                        quota_dimension=quota_dimension,
                        dimension_key=dimension_key,
                        period_key=period_key,
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _record_from_row(row)

    def ensure_usage(
        self,
        *,
        tenant_id: str,
        region: str,
        guest_id: str,
        product_id: str,
        quota_policy_id: str,
        quota_dimension: QuotaDimension,
        dimension_key: str,
        scenario_id: str | None,
        period_key: str,
        limit_count: int,
        metadata: dict[str, object] | None = None,
    ) -> QuotaUsageRecord:
        existing = self.get_by_dimension(
            tenant_id=tenant_id,
            region=region,
            guest_id=guest_id,
            product_id=product_id,
            quota_policy_id=quota_policy_id,
            quota_dimension=quota_dimension,
            dimension_key=dimension_key,
            period_key=period_key,
        )
        if existing is not None:
            return self._sync_limit(existing, limit_count=limit_count)

        record = QuotaUsageRecord(
            tenant_id=tenant_id,
            region=region,
            guest_id=guest_id,
            product_id=product_id,
            quota_policy_id=quota_policy_id,
            quota_dimension=quota_dimension,
            dimension_key=dimension_key,
            scenario_id=scenario_id,
            period_key=period_key,
            limit_count=limit_count,
            metadata=dict(metadata or {}),
        )
        try:
            with self._session.begin_nested():
                self._session.execute(
                    sa.insert(guest_quota_usage_table).values(asdict(record))
                )
        except IntegrityError as exc:
            if not _is_expected_usage_dimension_race(exc):
                raise
        self._session.flush()

        stored = self.get_by_dimension(
            tenant_id=tenant_id,
            region=region,
            guest_id=guest_id,
            product_id=product_id,
            quota_policy_id=quota_policy_id,
            quota_dimension=quota_dimension,
            dimension_key=dimension_key,
            period_key=period_key,
        )
        return _require_stored_usage(stored, record.id, "ensure")

    def consume_if_available(self, record: QuotaUsageRecord) -> QuotaUsageRecord | None:
        result = self._session.execute(
            sa.update(guest_quota_usage_table)
            .where(
                guest_quota_usage_table.c.id == record.id,
                guest_quota_usage_table.c.used_count
                < guest_quota_usage_table.c.limit_count,
            )
            .values(
                used_count=guest_quota_usage_table.c.used_count + 1,
                updated_at=utc_now(),
            )
        )
        if result.rowcount == 0:
            self._session.flush()
            return None
        self._session.flush()
        stored = self.get(record.id)
        return _require_stored_usage(stored, record.id, "consume")

    def _sync_limit(
        self,
        record: QuotaUsageRecord,
        *,
        limit_count: int,
    ) -> QuotaUsageRecord:
        if record.limit_count == limit_count:
            return record

        updated = replace(record, limit_count=limit_count, updated_at=utc_now())
        result = self._session.execute(
            sa.update(guest_quota_usage_table)
            .where(guest_quota_usage_table.c.id == record.id)
            .values(limit_count=updated.limit_count, updated_at=updated.updated_at)
        )
        if result.rowcount == 0:
            raise LookupError(f"quota usage not found: {record.id}")
        self._session.flush()
        stored = self.get(record.id)
        return _require_stored_usage(stored, record.id, "sync_limit")
