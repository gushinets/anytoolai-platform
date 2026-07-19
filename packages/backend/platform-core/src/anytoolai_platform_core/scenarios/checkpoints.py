from __future__ import annotations

from dataclasses import dataclass

from anytoolai_platform_core.scenarios.models import (
    ScenarioDefinition,
    ScenarioSessionRecord,
    ScenarioSessionStatus,
)
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus

PROCESSING_CHECKPOINT_ID = "processing"
RESULT_READY_CHECKPOINT_ID = "result_ready"
FAILED_CHECKPOINT_ID = "failed"


@dataclass(frozen=True)
class ScenarioCheckpointState:
    checkpoint_id: str
    actionable: bool
    allowed_next_actions: tuple[str, ...]


def resolve_checkpoint_state(
    *,
    scenario: ScenarioDefinition,
    session: ScenarioSessionRecord,
    job: JobRecord | None,
) -> ScenarioCheckpointState:
    checkpoint_id = _resolved_checkpoint_id(session=session, job=job)
    if checkpoint_id == RESULT_READY_CHECKPOINT_ID:
        return ScenarioCheckpointState(
            checkpoint_id=checkpoint_id,
            actionable=True,
            allowed_next_actions=tuple(scenario.allowed_next_actions),
        )
    return ScenarioCheckpointState(
        checkpoint_id=checkpoint_id,
        actionable=False,
        allowed_next_actions=(),
    )


def resolve_effective_status(
    *,
    session: ScenarioSessionRecord,
    job: JobRecord | None,
) -> ScenarioSessionStatus:
    if session.status in {
        ScenarioSessionStatus.completed,
        ScenarioSessionStatus.failed,
        ScenarioSessionStatus.expired,
    }:
        return session.status
    if job is None:
        return session.status
    if job.status is JobStatus.created:
        return ScenarioSessionStatus.started
    if job.status is JobStatus.running:
        return ScenarioSessionStatus.running
    if job.status is JobStatus.succeeded:
        return ScenarioSessionStatus.completed
    return ScenarioSessionStatus.failed


def _resolved_checkpoint_id(
    *,
    session: ScenarioSessionRecord,
    job: JobRecord | None,
) -> str:
    effective_status = resolve_effective_status(session=session, job=job)

    if session.current_checkpoint_id == RESULT_READY_CHECKPOINT_ID:
        return RESULT_READY_CHECKPOINT_ID
    if session.current_checkpoint_id == FAILED_CHECKPOINT_ID:
        return FAILED_CHECKPOINT_ID
    if effective_status is ScenarioSessionStatus.completed:
        return RESULT_READY_CHECKPOINT_ID
    if effective_status is ScenarioSessionStatus.failed:
        return FAILED_CHECKPOINT_ID
    if session.current_checkpoint_id == PROCESSING_CHECKPOINT_ID:
        return PROCESSING_CHECKPOINT_ID

    return PROCESSING_CHECKPOINT_ID
