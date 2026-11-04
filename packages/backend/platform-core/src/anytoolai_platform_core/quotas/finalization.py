from __future__ import annotations

from dataclasses import replace

import sqlalchemy as sa
from sqlalchemy.orm import Session

from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.artifacts.service import ArtifactService
from anytoolai_platform_core.common.metadata import metadata_str
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.quotas.events import ExecutionQuotaEvent, emit_execution_quota_event
from anytoolai_platform_core.quotas.execution_repository import ExecutionReservationRepository
from anytoolai_platform_core.quotas.models import (
    ConsumptionTransition,
    ExecutionOwnerKind,
    ExecutionReservation,
    FinalExecutionResult,
    ReservationState,
)
from anytoolai_platform_core.results.validation import resolve_available_workflow_result
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord, ScenarioSessionStatus
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.scenarios.service import ScenarioSessionService
from anytoolai_platform_core.storage.db import (
    execution_reservations_table,
    guest_quota_usage_table,
    paid_allowance_usage_table,
)
from anytoolai_platform_core.workflows.models import JobConsumptionMode, JobRecord, JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository

SCENARIO_TERMINAL_ERROR = "scenario_terminal_before_publication"


def _lock_execution(
    session: Session, job_id: str
) -> tuple[JobRecord, ScenarioSessionRecord | None, ExecutionReservation]:
    """Existing-row order: job -> scenario -> reservation -> original bucket."""
    job = JobRepository(session).get(job_id, for_update=True)
    if job is None or job.consumption_mode is not JobConsumptionMode.reserved:
        raise ValueError("metered terminal transition requires a reserved job")
    reservations = ExecutionReservationRepository(session)
    original = reservations.get_by_job(job_id)
    if original is None:
        raise RuntimeError(f"reserved job lacks its reservation: {job_id}")
    # Use the reservation's original scope even when terminalizing a poison job.
    scenario = ScenarioSessionRepository(session).get(
        original.scenario_session_id,
        tenant_id=original.owner.tenant_id,
        region=original.owner.region,
        product_id=original.product_id,
        frontend_id=original.frontend_id,
        for_update=True,
    )
    session.execute(
        sa.select(execution_reservations_table.c.id)
        .where(execution_reservations_table.c.id == original.id)
        .with_for_update()
    ).scalar_one()
    reservation = reservations.get_by_job(job_id)
    assert reservation is not None
    table, bucket_id, _ = _bucket(reservation)
    session.execute(
        sa.select(table.c.id).where(table.c.id == bucket_id).with_for_update(key_share=True)
    ).scalar_one()
    return job, scenario, reservation


def _bucket(reservation: ExecutionReservation) -> tuple[sa.Table, str, sa.Column]:
    if reservation.owner.owner_kind is ExecutionOwnerKind.guest:
        table = guest_quota_usage_table
        bucket_id = reservation.guest_quota_usage_id
        quantity = table.c.limit_count
    else:
        table = paid_allowance_usage_table
        bucket_id = reservation.paid_allowance_usage_id
        quantity = table.c.quantity
    if bucket_id is None:
        raise RuntimeError("reservation lacks its original bucket")
    return table, bucket_id, quantity


def _context(
    job: JobRecord, scenario: ScenarioSessionRecord | None, reservation: ExecutionReservation
) -> ExecutionContext:
    return ExecutionContext(
        tenant_id=reservation.owner.tenant_id,
        region=reservation.owner.region,
        product_id=reservation.product_id,
        frontend_id=reservation.frontend_id,
        scenario_session_id=reservation.scenario_session_id,
        scenario_chain_id=None if scenario is None else scenario.scenario_chain_id,
        job_id=job.id,
        workflow_id=job.workflow_id,
        workflow_version=job.workflow_version,
        guest_id=(
            reservation.owner.owner_id
            if reservation.owner.owner_kind is ExecutionOwnerKind.guest
            else None
        ),
        user_id=(
            reservation.owner.owner_id
            if reservation.owner.owner_kind is ExecutionOwnerKind.portal_user
            else None
        ),
        handoff_id=reservation.handoff_id,
        acquisition_source=metadata_str(job.metadata, "acquisition_source"),
    )


def _transition(
    session: Session,
    reservation: ExecutionReservation,
    state: ReservationState,
    *,
    result_artifact_id: str | None = None,
) -> ConsumptionTransition:
    table, bucket_id, quantity = _bucket(reservation)
    used, limit = session.execute(
        sa.select(table.c.used_count, quantity).where(table.c.id == bucket_id)
    ).one()
    consume = state is ReservationState.consumed
    now = utc_now()
    changed = session.execute(
        sa.update(table)
        .where(table.c.id == bucket_id, table.c.reserved_count > 0)
        .values(
            reserved_count=table.c.reserved_count - 1,
            used_count=table.c.used_count + int(consume),
            updated_at=now,
        )
    )
    if changed.rowcount != 1:
        raise RuntimeError("reservation counter integrity failure")
    changed = session.execute(
        sa.update(execution_reservations_table)
        .where(
            execution_reservations_table.c.id == reservation.id,
            execution_reservations_table.c.state == ReservationState.reserved,
        )
        .values(
            state=state, result_artifact_id=result_artifact_id, finalized_at=now, updated_at=now
        )
    )
    if changed.rowcount != 1:
        raise RuntimeError("reservation terminal arbitration failure")
    return ConsumptionTransition(
        applied=True,
        reservation=replace(
            reservation,
            state=state,
            result_artifact_id=result_artifact_id,
            finalized_at=now,
            updated_at=now,
        ),
        became_exhausted=consume and used < limit <= used + 1,
    )


def _terminal_replay(job: JobRecord, reservation: ExecutionReservation) -> ConsumptionTransition:
    if reservation.state is ReservationState.consumed:
        if (
            job.status is not JobStatus.succeeded
            or job.result_artifact_id != reservation.result_artifact_id
        ):
            raise RuntimeError("consumed reservation lacks its durable succeeded job")
    elif job.status not in {JobStatus.failed, JobStatus.canceled}:
        raise RuntimeError("released reservation lacks its durable terminal job")
    return ConsumptionTransition(False, reservation)


def release_execution(session: Session, job_id: str) -> ConsumptionTransition:
    """Release only durable terminal failure/cancellation; never infer an outcome from time."""
    job, scenario, reservation = _lock_execution(session, job_id)
    if reservation.state is not ReservationState.reserved:
        return _terminal_replay(job, reservation)
    if job.status not in {JobStatus.failed, JobStatus.canceled}:
        raise RuntimeError("release requires terminal failure or cancellation")
    transition = _transition(session, reservation, ReservationState.released)
    emit_execution_quota_event(
        session,
        ExecutionQuotaEvent.released,
        transition.reservation,
        _context(job, scenario, transition.reservation),
    )
    if scenario is not None and scenario.status in {
        ScenarioSessionStatus.started,
        ScenarioSessionStatus.running,
    }:
        ScenarioSessionService(
            ScenarioSessionRepository(session), EventEmitter(EventLogRepository(session))
        ).mark_failed(
            replace(scenario, completed_at=job.completed_at),
            error_code=job.error_code
            if job.error_code is not None
            else "workflow_execution_cancelled",
            context=_context(job, scenario, reservation),
        )
    return transition


def finalize_success(
    session: Session,
    job_id: str,
    final_result: FinalExecutionResult,
    *,
    config_registry: ConfigRegistry,
) -> ConsumptionTransition:
    """Publication, success, scenario completion and debit share the caller's transaction.

    Normal execution and rollback/unknown-commit recovery use this exact decision boundary.
    ANY-766 writes exhaustion outbox work from the returned transition before the same commit.
    """
    job, scenario, reservation = _lock_execution(session, job_id)
    if reservation.state is not ReservationState.reserved:
        return _terminal_replay(job, reservation)
    if job.status in {JobStatus.failed, JobStatus.canceled}:
        return release_execution(session, job_id)
    if job.status is not JobStatus.running:
        raise RuntimeError("new success requires a running job")
    if scenario is None:
        raise RuntimeError("reserved execution lacks its scenario")
    if scenario.status is not ScenarioSessionStatus.running:
        failed = JobRepository(session).mark_failed(
            replace(
                job,
                status=JobStatus.failed,
                result_artifact_id=None,
                error_code=SCENARIO_TERMINAL_ERROR,
                error_message_safe="Scenario is no longer running.",
                completed_at=utc_now(),
            )
        )
        EventEmitter(EventLogRepository(session)).emit(
            "workflow.failed",
            _context(failed, scenario, reservation),
            result_status=failed.status.value,
            properties={
                "error_code": SCENARIO_TERMINAL_ERROR,
                "workflow_version": job.workflow_version,
            },
        )
        return release_execution(session, job_id)
    ExecutionReservationRepository(session).validate_links(reservation)
    candidate = final_result.job
    for name in (
        "id",
        "tenant_id",
        "region",
        "product_id",
        "frontend_id",
        "scenario_session_id",
        "workflow_id",
        "workflow_version",
        "consumption_mode",
    ):
        if getattr(candidate, name) != getattr(job, name):
            raise ValueError(f"final result job {name} differs from accepted execution")
    resolve_available_workflow_result(
        artifact=final_result.artifact,
        job=candidate,
        config_registry=config_registry,
    )
    if candidate.completed_at is None:
        raise ValueError("final result requires completion time")
    artifacts = ArtifactRepository(session)
    existing = artifacts.get(final_result.artifact.id)
    if existing is None:
        ArtifactService(artifacts, EventEmitter(EventLogRepository(session))).create(
            final_result.artifact,
            recover=False,
        )
    elif existing != final_result.artifact:
        raise RuntimeError("final artifact identity already has different data")
    succeeded = JobRepository(session).mark_succeeded(candidate)
    transition = _transition(
        session, reservation, ReservationState.consumed, result_artifact_id=final_result.artifact.id
    )
    emit_execution_quota_event(
        session,
        ExecutionQuotaEvent.consumed,
        transition.reservation,
        _context(succeeded, scenario, transition.reservation),
    )
    emitter = EventEmitter(EventLogRepository(session))
    emitter.emit(
        "workflow.succeeded",
        _context(succeeded, scenario, reservation),
        result_status=succeeded.status.value,
        properties={"workflow_version": job.workflow_version},
    )
    ScenarioSessionService(ScenarioSessionRepository(session), emitter).mark_completed(
        replace(scenario, completed_at=candidate.completed_at),
        context=_context(succeeded, scenario, reservation),
    )
    return transition
