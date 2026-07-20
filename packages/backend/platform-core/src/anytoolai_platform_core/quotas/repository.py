from __future__ import annotations

from dataclasses import asdict, replace

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.quotas.models import QuotaUsageRecord
from anytoolai_platform_core.storage.db import guest_quota_usage_table


def _usage_dimension_filters(
    *,
    tenant_id: str,
    region: str,
    guest_id: str,
    product_id: str,
    quota_policy_id: str,
    period_key: str,
) -> tuple[sa.ColumnElement[bool], ...]:
    return (
        guest_quota_usage_table.c.tenant_id == tenant_id,
        guest_quota_usage_table.c.region == region,
        guest_quota_usage_table.c.guest_id == guest_id,
        guest_quota_usage_table.c.product_id == product_id,
        guest_quota_usage_table.c.quota_policy_id == quota_policy_id,
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


class QuotaUsageRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

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
        return None if row is None else QuotaUsageRecord(**dict(row))

    def get_by_dimension(
        self,
        *,
        tenant_id: str,
        region: str,
        guest_id: str,
        product_id: str,
        quota_policy_id: str,
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
                        period_key=period_key,
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else QuotaUsageRecord(**dict(row))

    def ensure_usage(
        self,
        *,
        tenant_id: str,
        region: str,
        guest_id: str,
        product_id: str,
        quota_policy_id: str,
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
            period_key=period_key,
            limit_count=limit_count,
            metadata=dict(metadata or {}),
        )
        try:
            with self._session.begin_nested():
                self._session.execute(
                    sa.insert(guest_quota_usage_table).values(asdict(record))
                )
        except IntegrityError:
            pass
        self._session.flush()

        stored = self.get_by_dimension(
            tenant_id=tenant_id,
            region=region,
            guest_id=guest_id,
            product_id=product_id,
            quota_policy_id=quota_policy_id,
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
