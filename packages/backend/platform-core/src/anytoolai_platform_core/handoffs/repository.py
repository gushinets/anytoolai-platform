from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from anytoolai_platform_core.handoffs.models import (
    HandoffRecord,
    HandoffStatus,
    HandoffTransitionResult,
)
from anytoolai_platform_core.storage.db import (
    jobs_table,
    product_handoffs_table,
    scenario_sessions_table,
)


class HandoffRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        return self._session

    def create(self, record: HandoffRecord) -> HandoffRecord:
        if record.status is not HandoffStatus.created:
            raise ValueError("handoff creation requires status=created")
        self._session.execute(sa.insert(product_handoffs_table).values(asdict(record)))
        self._session.flush()
        stored = self.get_by_id(record.id, tenant_id=record.tenant_id, region=record.region)
        if stored is None:
            raise RuntimeError(f"handoff round-trip failed after create: {record.id}")
        return stored

    def get_by_id(
        self,
        handoff_id: str,
        *,
        tenant_id: str,
        region: str,
    ) -> HandoffRecord | None:
        return self._one(
            product_handoffs_table.c.id == handoff_id,
            product_handoffs_table.c.tenant_id == tenant_id,
            product_handoffs_table.c.region == region,
        )

    def get_by_token_hash(
        self,
        token_hash: str,
        *,
        tenant_id: str,
        region: str,
    ) -> HandoffRecord | None:
        return self._one(
            product_handoffs_table.c.token_hash == token_hash,
            product_handoffs_table.c.tenant_id == tenant_id,
            product_handoffs_table.c.region == region,
        )

    def mark_viewed(self, handoff_id: str, now: datetime) -> HandoffTransitionResult:
        changed = self._transition(
            handoff_id,
            from_statuses=(HandoffStatus.created,),
            to_status=HandoffStatus.viewed,
            values={"viewed_at": now, "updated_at": now},
            extra_conditions=(
                product_handoffs_table.c.expires_at > now,
                _failure_not_reserved(),
            ),
        )
        return HandoffTransitionResult(self._require(handoff_id), changed)

    def claim_accept(
        self,
        handoff_id: str,
        now: datetime,
        *,
        accepted_by_guest_id: str | None,
        accepted_from_frontend_instance_id: str | None,
    ) -> HandoffRecord | None:
        result = self._session.execute(
            sa.update(product_handoffs_table)
            .where(
                product_handoffs_table.c.id == handoff_id,
                product_handoffs_table.c.status.in_([HandoffStatus.created, HandoffStatus.viewed]),
                product_handoffs_table.c.expires_at > now,
                _failure_not_reserved(),
            )
            .values(
                status=HandoffStatus.accepted,
                accepted_at=now,
                accepted_by_guest_id=accepted_by_guest_id,
                accepted_from_frontend_instance_id=accepted_from_frontend_instance_id,
                updated_at=now,
            )
        )
        if result.rowcount == 0:
            return None
        self._session.flush()
        return self._require(handoff_id)

    def reserve_quota_failure_recovery(
        self,
        handoff_id: str,
        *,
        error_code: str,
        now: datetime,
    ) -> bool:
        """Reserve quota rollback recovery without changing lifecycle status."""
        result = self._session.execute(
            sa.update(product_handoffs_table)
            .where(
                product_handoffs_table.c.id == handoff_id,
                product_handoffs_table.c.status.in_([HandoffStatus.created, HandoffStatus.viewed]),
                _failure_not_reserved(),
            )
            .values(error_code=error_code, updated_at=now)
        )
        changed = result.rowcount > 0
        if changed:
            self._session.flush()
        return changed

    def attach_target(
        self,
        handoff_id: str,
        *,
        target_scenario_session_id: str,
        target_job_id: str | None,
        now: datetime,
    ) -> HandoffRecord:
        self._require_target_rows(handoff_id, target_scenario_session_id, target_job_id)
        result = self._session.execute(
            sa.update(product_handoffs_table)
            .where(
                product_handoffs_table.c.id == handoff_id,
                product_handoffs_table.c.status == HandoffStatus.accepted,
                product_handoffs_table.c.target_scenario_session_id.is_(None),
            )
            .values(
                target_scenario_session_id=target_scenario_session_id,
                target_job_id=target_job_id,
                updated_at=now,
            )
        )
        if result.rowcount == 0:
            raise RuntimeError(f"handoff target cannot be attached: {handoff_id}")
        self._session.flush()
        return self._require(handoff_id)

    def decline(self, handoff_id: str, now: datetime) -> HandoffTransitionResult:
        changed = self._transition(
            handoff_id,
            from_statuses=(HandoffStatus.created, HandoffStatus.viewed),
            to_status=HandoffStatus.declined,
            values={"declined_at": now, "updated_at": now},
            extra_conditions=(
                product_handoffs_table.c.expires_at > now,
                _failure_not_reserved(),
            ),
        )
        return HandoffTransitionResult(self._require(handoff_id), changed)

    def expire_if_due(self, handoff_id: str, now: datetime) -> HandoffTransitionResult:
        result = self._session.execute(
            sa.update(product_handoffs_table)
            .where(
                product_handoffs_table.c.id == handoff_id,
                product_handoffs_table.c.status.in_([HandoffStatus.created, HandoffStatus.viewed]),
                product_handoffs_table.c.expires_at <= now,
                _failure_not_reserved(),
            )
            .values(
                status=HandoffStatus.expired,
                expired_at=now,
                updated_at=now,
            )
        )
        changed = result.rowcount > 0
        if changed:
            self._session.flush()
        return HandoffTransitionResult(self._require(handoff_id), changed)

    def consume(
        self,
        handoff_id: str,
        *,
        target_job_id: str,
        now: datetime,
    ) -> HandoffTransitionResult:
        record = self._require(handoff_id)
        if record.target_job_id != target_job_id:
            raise ValueError("handoff consume requires its linked target job")
        changed = self._transition(
            handoff_id,
            from_statuses=(HandoffStatus.accepted,),
            to_status=HandoffStatus.consumed,
            values={"consumed_at": now, "updated_at": now},
        )
        return HandoffTransitionResult(self._require(handoff_id), changed)

    def mark_failed(
        self,
        handoff_id: str,
        *,
        error_code: str,
        now: datetime,
    ) -> HandoffTransitionResult:
        changed = self._transition(
            handoff_id,
            from_statuses=(HandoffStatus.created, HandoffStatus.viewed),
            to_status=HandoffStatus.failed,
            values={"failed_at": now, "error_code": error_code, "updated_at": now},
        )
        return HandoffTransitionResult(self._require(handoff_id), changed)

    def _transition(
        self,
        handoff_id: str,
        *,
        from_statuses: tuple[HandoffStatus, ...],
        to_status: HandoffStatus,
        values: dict[str, object],
        extra_conditions: tuple[sa.ColumnElement[bool], ...] = (),
    ) -> bool:
        result = self._session.execute(
            sa.update(product_handoffs_table)
            .where(
                product_handoffs_table.c.id == handoff_id,
                product_handoffs_table.c.status.in_(from_statuses),
                *extra_conditions,
            )
            .values(status=to_status, **values)
        )
        changed = result.rowcount > 0
        if changed:
            self._session.flush()
        return changed

    def _require_target_rows(
        self,
        handoff_id: str,
        target_scenario_session_id: str,
        target_job_id: str | None,
    ) -> None:
        handoff = self._require(handoff_id)
        target_session = (
            self._session.execute(
                sa.select(scenario_sessions_table).where(
                    scenario_sessions_table.c.id == target_scenario_session_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if target_session is None:
            raise LookupError("target scenario session not found")
        if (
            target_session["tenant_id"] != handoff.tenant_id
            or target_session["region"] != handoff.region
            or target_session["product_id"] != handoff.target_product_id
            or target_session["frontend_id"] != handoff.target_frontend_id
            or target_session["scenario_id"] != handoff.target_scenario_id
            or target_session["parent_scenario_session_id"] != handoff.source_scenario_session_id
        ):
            raise ValueError("target scenario session does not match handoff")
        if target_job_id is None:
            return
        target_job = (
            self._session.execute(sa.select(jobs_table).where(jobs_table.c.id == target_job_id))
            .mappings()
            .one_or_none()
        )
        if target_job is None or (
            target_job["scenario_session_id"] != target_scenario_session_id
            or target_job["tenant_id"] != handoff.tenant_id
            or target_job["region"] != handoff.region
            or target_job["product_id"] != handoff.target_product_id
            or target_job["frontend_id"] != handoff.target_frontend_id
        ):
            raise ValueError("target job must belong to target scenario session")

    def _require(self, handoff_id: str) -> HandoffRecord:
        row = self._one(product_handoffs_table.c.id == handoff_id)
        if row is None:
            raise LookupError(f"handoff not found: {handoff_id}")
        return row

    def _one(self, *conditions: sa.ColumnElement[bool]) -> HandoffRecord | None:
        row = (
            self._session.execute(sa.select(product_handoffs_table).where(*conditions))
            .mappings()
            .one_or_none()
        )
        return None if row is None else HandoffRecord(**dict(row))


def _failure_not_reserved() -> sa.ColumnElement[bool]:
    return product_handoffs_table.c.error_code.is_(None)
