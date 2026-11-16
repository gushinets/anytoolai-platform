"""Execution ownership is reservation-backed, never a historical body user_id."""

from dataclasses import asdict

import sqlalchemy as sa
from sqlalchemy.orm import Session

from anytoolai_platform_core.quotas.models import ExecutionOwner, ExecutionOwnerKind
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.storage.db import execution_reservations_table


def paid_session_owner(session: Session, record: ScenarioSessionRecord) -> ExecutionOwner | None:
    row = (
        session.execute(
            sa.select(execution_reservations_table).where(
                execution_reservations_table.c.scenario_session_id == record.id,
                execution_reservations_table.c.owner_kind == ExecutionOwnerKind.portal_user,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is not None:
        return ExecutionOwner(
            row["tenant_id"], row["region"], ExecutionOwnerKind.portal_user, row["owner_id"]
        )
    stored = record.metadata.get("execution_owner")
    if stored is not None:
        owner = ExecutionOwner(**{**stored, "owner_kind": ExecutionOwnerKind(stored["owner_kind"])})
        if (
            asdict(owner) != stored
            or (owner.tenant_id, owner.region) != (record.tenant_id, record.region)
            or owner.owner_kind is not ExecutionOwnerKind.portal_user
        ):
            raise ValueError("Invalid server-written deferred execution owner")
        return owner
    return None


def session_owner_matches(
    session: Session, record: ScenarioSessionRecord, owner: ExecutionOwner | None
) -> bool:
    paid_owner = paid_session_owner(session, record)
    return paid_owner == owner if paid_owner is not None or owner is not None else True
