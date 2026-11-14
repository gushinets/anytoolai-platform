"""Immutable exhaustion edges; the successful workflow transaction owns insertion."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from anytoolai_platform_core.quotas.execution_repository import PaidAllowanceUsageRepository
from anytoolai_platform_core.quotas.models import (
    ConsumptionTransition,
    ExecutionOwnerKind,
    ExhaustionDeliveryState,
)
from anytoolai_platform_core.storage.db import allowance_exhaustion_outbox_table as table
from anytoolai_platform_core.storage.transactions import SessionFactory

EXHAUSTION_EVENT = "allowance_exhausted"
DELIVERY_LEASE_SECONDS = 30
RETRY_BASE_SECONDS = 5
RETRY_MAX_SECONDS = 300


@dataclass(frozen=True)
class ExhaustionEvent:
    tenant_id: str
    region: str
    user_id: str
    allowance_id: str
    product_id: str
    metric_key: str
    unit: str
    quantity: int
    occurred_at: datetime

    def wire(self) -> dict[str, str | int]:
        return {
            "schema_version": 1,
            "event_type": EXHAUSTION_EVENT,
            "tenant_id": self.tenant_id,
            "region": self.region,
            "user_id": self.user_id,
            "allowance_id": self.allowance_id,
            "product_id": self.product_id,
            "metric_key": self.metric_key,
            "unit": self.unit,
            "quantity": self.quantity,
            "occurred_at": self.occurred_at.astimezone(UTC).isoformat(),
        }


@dataclass(frozen=True)
class ExhaustionClaim:
    id: str
    lease_owner: str
    attempt_count: int
    event: ExhaustionEvent


def enqueue_exhaustion(session: Session, transition: ConsumptionTransition) -> None:
    reservation = transition.reservation
    if (
        not transition.became_exhausted
        or reservation.owner.owner_kind is not ExecutionOwnerKind.portal_user
    ):
        return
    bucket = PaidAllowanceUsageRepository(session).get_owned(
        reservation.owner, reservation.paid_allowance_usage_id
    )
    if bucket is None or reservation.finalized_at is None:
        raise RuntimeError("Exhaustion requires its original finalized paid bucket")
    binding = bucket.allowance
    insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
    session.execute(
        insert(table)
        .values(
            id=str(uuid4()),
            tenant_id=binding.owner.tenant_id,
            region=binding.owner.region,
            user_id=binding.owner.owner_id,
            allowance_id=binding.allowance_id,
            event_type=EXHAUSTION_EVENT,
            product_id=binding.product_id,
            metric_key=binding.metric_key,
            unit=binding.unit,
            quantity=binding.quantity,
            occurred_at=reservation.finalized_at,
            state=ExhaustionDeliveryState.pending,
            next_attempt_at=reservation.finalized_at,
            attempt_count=0,
        )
        .on_conflict_do_nothing(
            index_elements=["tenant_id", "region", "user_id", "allowance_id", "event_type"]
        )
    )


def claim_exhaustion(
    factory: SessionFactory, tenant_id: str, region: str
) -> ExhaustionClaim | None:
    with factory.begin() as session:
        now = session.scalar(sa.select(sa.func.clock_timestamp()))
        row = (
            session.execute(
                sa.select(table)
                .where(
                    table.c.state == ExhaustionDeliveryState.pending,
                    table.c.tenant_id == tenant_id,
                    table.c.region == region,
                    table.c.next_attempt_at <= now,
                    sa.or_(table.c.lease_expires_at.is_(None), table.c.lease_expires_at <= now),
                )
                .order_by(table.c.next_attempt_at, table.c.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        claim = ExhaustionClaim(
            row["id"],
            str(uuid4()),
            row["attempt_count"] + 1,
            ExhaustionEvent(**{name: row[name] for name in ExhaustionEvent.__dataclass_fields__}),
        )
        session.execute(
            sa.update(table)
            .where(table.c.id == claim.id)
            .values(
                lease_owner=claim.lease_owner,
                lease_expires_at=now + timedelta(seconds=DELIVERY_LEASE_SECONDS),
                attempt_count=claim.attempt_count,
            )
        )
    # Ownership is returned only after the lease commit succeeds.
    return claim


DeliveryError = Literal["transport", "http_retryable", "http_permanent"]


def settle_exhaustion(
    factory: SessionFactory,
    claim: ExhaustionClaim,
    *,
    error: DeliveryError | None = None,
    http_status: int | None = None,
) -> bool:
    with factory.begin() as session:
        row = (
            session.execute(
                sa.select(table.c.lease_owner, table.c.lease_expires_at, table.c.state)
                .where(table.c.id == claim.id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        # Sample wall time after the row lock, including any wait for a reclaimer.
        now = session.scalar(sa.select(sa.func.clock_timestamp()))
        if (
            row is None
            or row["lease_owner"] != claim.lease_owner
            or (
                row["lease_expires_at"] is None
                or row["lease_expires_at"] <= now
                or row["state"] != ExhaustionDeliveryState.pending
            )
        ):
            return False
        result = session.execute(
            sa.update(table)
            .where(
                table.c.id == claim.id,
                table.c.lease_owner == claim.lease_owner,
                table.c.lease_expires_at > now,
                table.c.state == ExhaustionDeliveryState.pending,
            )
            .values(
                state=ExhaustionDeliveryState.delivered
                if error is None
                else ExhaustionDeliveryState.parked
                if error == "http_permanent"
                else ExhaustionDeliveryState.pending,
                lease_owner=None,
                lease_expires_at=None,
                last_error=f"{error}:{http_status}"
                if error is not None and http_status is not None
                else error,
                next_attempt_at=now
                + timedelta(
                    seconds=min(
                        RETRY_MAX_SECONDS,
                        RETRY_BASE_SECONDS * 2 ** min(claim.attempt_count - 1, 6),
                    )
                ),
            )
        )
        return result.rowcount == 1
