from __future__ import annotations

from dataclasses import asdict

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.quotas.models import (
    ExecutionOwner,
    ExecutionOwnerKind,
    ExecutionReplayNamespace,
    ExecutionReservation,
    PaidAllowance,
    PaidAllowanceUsageRecord,
    QuotaDimension,
    ReservationState,
)
from anytoolai_platform_core.storage.db import (
    execution_reservations_table,
    guest_quota_usage_table,
    jobs_table,
    paid_allowance_usage_table,
    scenario_sessions_table,
)
from anytoolai_platform_core.storage.db_errors import (
    is_expected_unique_violation,
    unique_constraint_columns,
)
from anytoolai_platform_core.workflows.models import JobConsumptionMode

REPLAY_CONSTRAINT = "uq_execution_reservations_owner_replay"


def is_expected_execution_replay_race(error: IntegrityError) -> bool:
    return is_expected_unique_violation(
        error,
        constraint_name=REPLAY_CONSTRAINT,
        table_name=execution_reservations_table.name,
        columns=unique_constraint_columns(execution_reservations_table, REPLAY_CONSTRAINT),
    )


class PaidAllowanceConflictError(ValueError):
    pass


def _owner_values(owner: ExecutionOwner) -> dict[str, str]:
    return asdict(owner)


def _paid_record(row: sa.RowMapping) -> PaidAllowanceUsageRecord:
    values = dict(row)
    owner = ExecutionOwner(
        tenant_id=values.pop("tenant_id"),
        region=values.pop("region"),
        owner_kind=ExecutionOwnerKind.portal_user,
        owner_id=values.pop("owner_id"),
    )
    allowance = PaidAllowance(
        owner=owner,
        **{
            name: values.pop(name)
            for name in (
                "allowance_id",
                "product_id",
                "metric_key",
                "unit",
                "quantity",
            )
        },
    )
    return PaidAllowanceUsageRecord(allowance=allowance, **values)


def _reservation_record(row: sa.RowMapping) -> ExecutionReservation:
    values = dict(row)
    owner = ExecutionOwner(
        tenant_id=values.pop("tenant_id"),
        region=values.pop("region"),
        owner_kind=ExecutionOwnerKind(values.pop("owner_kind")),
        owner_id=values.pop("owner_id"),
    )
    values["state"] = ReservationState(values["state"])
    if values["replay_namespace"] is not None:
        values["replay_namespace"] = ExecutionReplayNamespace(values["replay_namespace"])
    return ExecutionReservation(owner=owner, **values)


class PaidAllowanceUsageRepository:
    """First binding is immutable. The caller owns commit and rollback."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(
        self,
        *,
        tenant_id: str,
        region: str,
        allowance_id: str,
    ) -> PaidAllowanceUsageRecord | None:
        row = (
            self._session.execute(
                sa.select(paid_allowance_usage_table).where(
                    paid_allowance_usage_table.c.tenant_id == tenant_id,
                    paid_allowance_usage_table.c.region == region,
                    paid_allowance_usage_table.c.allowance_id == allowance_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _paid_record(row)

    def get_owned(self, owner: ExecutionOwner, bucket_id: str) -> PaidAllowanceUsageRecord | None:
        row = (
            self._session.execute(
                sa.select(paid_allowance_usage_table).where(
                    paid_allowance_usage_table.c.id == bucket_id,
                    paid_allowance_usage_table.c.tenant_id == owner.tenant_id,
                    paid_allowance_usage_table.c.region == owner.region,
                    paid_allowance_usage_table.c.owner_id == owner.owner_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _paid_record(row)

    def ensure_usage(self, allowance: PaidAllowance) -> PaidAllowanceUsageRecord:
        record = PaidAllowanceUsageRecord(allowance=allowance)
        values = asdict(record)
        values.pop("allowance")
        binding = asdict(allowance)
        binding.pop("owner")
        owner = _owner_values(allowance.owner)
        owner.pop("owner_kind")
        self._session.execute(
            postgresql.insert(paid_allowance_usage_table)
            .values(**values, **binding, **owner)
            .on_conflict_do_nothing(constraint="uq_paid_allowance_usage_scope_allowance")
        )
        self._session.flush()
        stored = self.get(
            tenant_id=allowance.owner.tenant_id,
            region=allowance.owner.region,
            allowance_id=allowance.allowance_id,
        )
        if stored is None:
            raise RuntimeError("paid allowance round-trip failed after ensure")
        if stored.allowance != allowance:
            raise PaidAllowanceConflictError("paid allowance binding cannot change")
        return stored

    def reserve_if_available(self, record: PaidAllowanceUsageRecord) -> bool:
        # Reservation FK checks hold KEY SHARE; FOR UPDATE would deadlock on lock upgrades.
        self._session.execute(
            sa.select(paid_allowance_usage_table.c.id)
            .where(paid_allowance_usage_table.c.id == record.id)
            .with_for_update(key_share=True)
        ).scalar_one()
        table = paid_allowance_usage_table
        result = self._session.execute(
            sa.update(table)
            .where(
                table.c.id == record.id,
                table.c.used_count + table.c.reserved_count < table.c.quantity,
            )
            .values(reserved_count=table.c.reserved_count + 1, updated_at=utc_now())
        )
        return result.rowcount == 1


class ExecutionReservationRepository:
    """Reservation storage; lifecycle counter changes belong to the metering service."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, record: ExecutionReservation) -> ExecutionReservation:
        if record.state is not ReservationState.reserved:
            raise ValueError("new execution reservation must be reserved")
        self.validate_links(record)
        values = asdict(record)
        values.pop("owner")
        self._session.execute(
            sa.insert(execution_reservations_table).values(**values, **_owner_values(record.owner))
        )
        self._session.flush()
        stored = self.get_by_job(record.job_id)
        if stored is None:
            raise RuntimeError("execution reservation round-trip failed after create")
        return stored

    def get_by_job(self, job_id: str) -> ExecutionReservation | None:
        row = (
            self._session.execute(
                sa.select(execution_reservations_table).where(
                    execution_reservations_table.c.job_id == job_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _reservation_record(row)

    def find_replay(
        self,
        *,
        owner: ExecutionOwner,
        product_id: str,
        scenario_id: str,
        namespace: ExecutionReplayNamespace,
        replay_key: str,
    ) -> ExecutionReservation | None:
        row = (
            self._session.execute(
                sa.select(execution_reservations_table).where(
                    *(
                        execution_reservations_table.c[name] == value
                        for name, value in _owner_values(owner).items()
                    ),
                    execution_reservations_table.c.product_id == product_id,
                    execution_reservations_table.c.scenario_id == scenario_id,
                    execution_reservations_table.c.replay_namespace == namespace,
                    execution_reservations_table.c.replay_key == replay_key,
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else _reservation_record(row)

    def validate_links(self, record: ExecutionReservation) -> None:
        self._require_execution_link(record)
        self._require_bucket_link(record)

    def _require_execution_link(self, record: ExecutionReservation) -> None:
        linked = self._session.execute(
            sa.select(jobs_table.c.id)
            .join(
                scenario_sessions_table,
                jobs_table.c.scenario_session_id == scenario_sessions_table.c.id,
            )
            .where(
                jobs_table.c.id == record.job_id,
                jobs_table.c.scenario_session_id == record.scenario_session_id,
                jobs_table.c.consumption_mode == JobConsumptionMode.reserved,
                jobs_table.c.tenant_id == record.owner.tenant_id,
                jobs_table.c.region == record.owner.region,
                jobs_table.c.product_id == record.product_id,
                jobs_table.c.frontend_id == record.frontend_id,
                scenario_sessions_table.c.tenant_id == record.owner.tenant_id,
                scenario_sessions_table.c.region == record.owner.region,
                scenario_sessions_table.c.product_id == record.product_id,
                scenario_sessions_table.c.frontend_id == record.frontend_id,
                scenario_sessions_table.c.scenario_id == record.scenario_id,
            )
        ).scalar_one_or_none()
        if linked is None:
            raise ValueError("reservation requires a reserved job and matching scenario dimensions")
        if record.owner.owner_kind is ExecutionOwnerKind.guest:
            guest_id = self._session.execute(
                sa.select(scenario_sessions_table.c.guest_id).where(
                    scenario_sessions_table.c.id == record.scenario_session_id,
                )
            ).scalar_one()
            if guest_id != record.owner.owner_id:
                raise ValueError("reservation guest must match the scenario owner")

    def _require_bucket_link(self, record: ExecutionReservation) -> None:
        if record.owner.owner_kind is ExecutionOwnerKind.guest:
            table = guest_quota_usage_table
            predicates = (
                table.c.id == record.guest_quota_usage_id,
                table.c.guest_id == record.owner.owner_id,
                sa.or_(
                    table.c.quota_dimension == QuotaDimension.product,
                    table.c.scenario_id == record.scenario_id,
                ),
            )
            valid_kind = record.paid_allowance_usage_id is None
        else:
            table = paid_allowance_usage_table
            predicates = (
                table.c.id == record.paid_allowance_usage_id,
                table.c.owner_id == record.owner.owner_id,
            )
            valid_kind = record.guest_quota_usage_id is None
        linked = self._session.execute(
            sa.select(table.c.id).where(
                *predicates,
                table.c.tenant_id == record.owner.tenant_id,
                table.c.region == record.owner.region,
                table.c.product_id == record.product_id,
            )
        ).scalar_one_or_none()
        if not valid_kind or linked is None:
            raise ValueError("reservation bucket must match owner, scope and product")
