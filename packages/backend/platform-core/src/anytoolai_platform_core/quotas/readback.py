from __future__ import annotations

from sqlalchemy.orm import Session

from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.quotas.execution_repository import PaidAllowanceUsageRepository
from anytoolai_platform_core.quotas.models import (
    ConsumptionReadback,
    ExecutionOwner,
    ExecutionOwnerKind,
    PaidAllowanceUsageRecord,
    QuotaUsageRecord,
)
from anytoolai_platform_core.quotas.repository import QuotaUsageRepository


def consumption_from_bucket(
    owner: ExecutionOwner, bucket: QuotaUsageRecord | PaidAllowanceUsageRecord
) -> ConsumptionReadback:
    """Derive every counter from the same row snapshot, preserving historical debits."""
    if isinstance(bucket, QuotaUsageRecord):
        quantity, legacy = bucket.limit_count, bucket.legacy_used_count
    else:
        quantity, legacy = bucket.allowance.quantity, 0
    return ConsumptionReadback(
        owner=owner,
        bucket=bucket,
        quantity=quantity,
        used=bucket.used_count,
        successful_used=bucket.used_count - legacy,
        legacy_used=legacy,
        reserved=bucket.reserved_count,
        remaining=max(quantity - bucket.used_count, 0),
        available=max(quantity - bucket.used_count - bucket.reserved_count, 0),
        read_at=utc_now(),
    )


def read_consumption(
    session: Session, owner: ExecutionOwner, bucket: str
) -> ConsumptionReadback | None:
    """Read an original usage-row ID in one query, without creating or locking a bucket.

    Paid callers resolve an allowance ID to its original usage-row ID through the paid
    repository. Unknown or foreign buckets are unobserved; storage errors propagate.
    """
    if owner.owner_kind is ExecutionOwnerKind.portal_user:
        record = PaidAllowanceUsageRepository(session).get_owned(owner, bucket)
    else:
        record = QuotaUsageRepository(session).get_owned(owner, bucket)
    return None if record is None else consumption_from_bucket(owner, record)
