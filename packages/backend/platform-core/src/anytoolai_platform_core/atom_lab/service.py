from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from anytoolai_platform_core.actions.models import ActionRunStatus
from anytoolai_platform_core.artifacts.models import ArtifactStatus
from anytoolai_platform_core.atom_lab.diagnostics import (
    ATOM_LAB_DEBUG_VERSION,
    bound_atom_lab_debug_text,
)
from anytoolai_platform_core.atom_lab.models import AtomLabRunHistoryState, AtomLabRunStatus
from anytoolai_platform_core.atom_lab.repository import (
    ATOM_LAB_DIAGNOSTIC_ITEMS_MAX,
    AtomLabRunRepository,
)
from anytoolai_platform_core.atom_lab.snapshots import (
    AtomLabSnapshotRequest,
    build_atom_lab_run_record,
)
from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.common.ids import new_id
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.identity.service import GuestIdentityService
from anytoolai_platform_core.providers.models import ReasoningEffort
from anytoolai_platform_core.scenarios.checkpoints import PROCESSING_CHECKPOINT_ID
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord, ScenarioSessionStatus
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.scenarios.runtime_scope import RuntimeScope, runtime_scope_metadata
from anytoolai_platform_core.scenarios.service import ScenarioSessionService
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository

DEFAULT_ATOM_LAB_DAILY_LIMIT = 100
DEFAULT_ATOM_LAB_ACTIVE_LIMIT = 1


def project_atom_lab_run_status(
    job_status: JobStatus, session_status: ScenarioSessionStatus,
) -> AtomLabRunStatus:
    terminal_session = {
        ScenarioSessionStatus.completed: AtomLabRunStatus.succeeded,
        ScenarioSessionStatus.failed: AtomLabRunStatus.failed,
        ScenarioSessionStatus.expired: AtomLabRunStatus.expired,
    }
    if session_status in terminal_session:
        return terminal_session[session_status]
    terminal = {
        JobStatus.succeeded: AtomLabRunStatus.succeeded,
        JobStatus.failed: AtomLabRunStatus.failed,
        JobStatus.canceled: AtomLabRunStatus.cancelled,
    }
    if job_status in terminal:
        return terminal[job_status]
    return {
        JobStatus.created: AtomLabRunStatus.queued,
        JobStatus.running: AtomLabRunStatus.running,
    }[job_status]


class AtomLabRunHistoryService:
    """Read saved configuration and project the existing runtime; never resolve live config."""

    def __init__(self, session: Session) -> None:
        self._repository = AtomLabRunRepository(session)

    @staticmethod
    def status(state: AtomLabRunHistoryState) -> AtomLabRunStatus:
        return project_atom_lab_run_status(state.job.status, state.session_status)

    def summary(self, state: AtomLabRunHistoryState) -> dict[str, Any]:
        run = state.run
        return {
            "run_id": run.id,
            "status": self.status(state),
            "atom_id": run.atom_id,
            "model_id": run.model_id,
            "preset_id": run.preset_id,
            "preset_version": run.preset_version,
            "created_at": run.created_at,
            "started_at": state.job.started_at,
            "finished_at": state.job.completed_at,
        }

    def detail(self, state: AtomLabRunHistoryState) -> dict[str, Any]:
        run, job = state.run, state.job
        status = self.status(state)
        action = self._repository.history_action(run)
        artifact_id = run.artifact_id
        if action is not None and action.output_artifact_id is not None:
            artifact_id = action.output_artifact_id
        result = None
        if (
            status is AtomLabRunStatus.succeeded
            and action is not None
            and (action.status is ActionRunStatus.succeeded and artifact_id is not None)
        ):
            artifact = self._repository.history_artifact(run, artifact_id)
            if artifact is not None and (
                artifact.artifact_type == "structured_output"
                and artifact.status is ArtifactStatus.stored
                and artifact.action_run_id == action.id
            ):
                result = artifact.content_json
        calls, validation, transport, physical = self._repository.history_provider_calls(run)
        debug = self._repository.history_debug_artifacts(run)
        error_code = job.error_code
        if error_code is None and action is not None:
            error_code = action.error_code
        duration_ms = None
        if job.started_at is not None and job.completed_at is not None:
            duration_ms = max(0, round((job.completed_at - job.started_at).total_seconds() * 1000))
        provider_calls = [
            {
                "provider_call_id": call.id,
                "action_run_id": call.action_run_id,
                "status": call.status,
                "semantic_attempt_index": call.semantic_attempt_index,
                "transport_attempt_index": call.transport_attempt_index,
                "physical_call_index": call.physical_call_index,
                "response_model_id": _confirmed_response_model_id(call.metadata),
                "error_code": _history_error_code(call.error_code),
                "latency_ms": call.latency_ms,
            }
            for call in calls
        ]
        return {
            "run_id": run.id,
            "status": status,
            "snapshot": run.snapshot_payload(),
            "runtime_ids": {
                "scenario_session_id": run.scenario_session_id,
                "job_id": run.job_id,
                "action_run_id": None if action is None else action.id,
                "artifact_id": artifact_id,
            },
            "result": result,
            "diagnostics": {
                "error_code": _history_error_code(error_code),
                "duration_ms": duration_ms,
                "requested_model_id": run.model_id,
                "requested_reasoning_effort": run.reasoning_effort,
                "response_model_id": None
                if not calls
                else _confirmed_response_model_id(calls[-1].metadata),
                "validation_attempts": validation,
                "transport_attempts": transport,
                "physical_calls": physical,
                "succeeded_first_attempt": (
                    physical == 1 and validation == 1
                    if status is AtomLabRunStatus.succeeded and physical > 0
                    else None
                ),
                "provider_calls": provider_calls,
                "provider_calls_truncated": physical > len(calls),
                "debug_artifacts": [
                    {
                        "artifact_id": artifact.id,
                        "error_code": _history_error_code(artifact.metadata.get("error_code")),
                        **_lab_debug_text(artifact.content_text, artifact.metadata, run.id),
                    }
                    for artifact in debug[:ATOM_LAB_DIAGNOSTIC_ITEMS_MAX]
                ],
                "debug_artifacts_truncated": len(debug) > ATOM_LAB_DIAGNOSTIC_ITEMS_MAX,
            },
            "created_at": run.created_at,
            "started_at": job.started_at,
            "finished_at": job.completed_at,
        }


def _lab_debug_text(
    text: str | None, metadata: Mapping[str, Any], run_id: str,
) -> dict[str, Any]:
    if (
        metadata.get("atom_lab_run_id") != run_id
        or metadata.get("atom_lab_debug_version") != ATOM_LAB_DEBUG_VERSION
        or not isinstance(text, str)
    ):
        return {"raw_output_text": None, "truncated": False, "redacted": False}
    diagnostic = bound_atom_lab_debug_text(text)
    return {
        "raw_output_text": diagnostic.text,
        "truncated": metadata.get("truncated") is True or diagnostic.truncated,
        "redacted": metadata.get("redacted") is True or diagnostic.redacted,
    }


def _history_error_code(value: Any) -> str | None:
    # Never return upstream exception text, arbitrary metadata, or raw provider output.
    if isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,127}", value):
        return value
    return None


def _confirmed_response_model_id(metadata: Mapping[str, Any]) -> str | None:
    response = metadata.get("response_metadata")
    if not isinstance(response, Mapping):
        return None
    adapter = response.get("litellm")
    if not isinstance(adapter, Mapping):
        return None
    model = adapter.get("actual_model")
    if isinstance(model, str) and re.fullmatch(r"[A-Za-z0-9._:/-]{1,256}", model):
        return model
    return None


class AtomLabIdempotencyConflictError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "idempotency_conflict",
            "Idempotency-Key was already used with a different Atom Lab request.",
        )


class AtomLabActiveRunLimitError(PlatformError):
    def __init__(self) -> None:
        super().__init__("lab_busy", "Another Atom Lab run is active.")


class AtomLabDailyLimitError(PlatformError):
    def __init__(self) -> None:
        super().__init__("daily_limit_exhausted", "Atom Lab daily limit exhausted.")


@dataclass(frozen=True)
class AtomLabRunAdmissionRequest:
    tenant_id: str
    region: str
    product_id: str
    frontend_id: str
    atom_id: str
    input_payload: Mapping[str, Any]
    prompt: str
    model_id: str
    reasoning_effort: ReasoningEffort | None
    capability_snapshot_id: str
    capability_provenance: Mapping[str, Any]
    idempotency_key: str
    preset_id: str | None = None
    preset_version: int | None = None


@dataclass(frozen=True)
class AtomLabRunAdmissionResult:
    run_id: str
    scenario_session_id: str
    job_id: str
    guest_id: str
    status: AtomLabRunStatus
    replayed: bool = False


def compute_atom_lab_request_hash(request: AtomLabRunAdmissionRequest) -> str:
    canonical_request = {
        "atom_id": request.atom_id,
        "input": request.input_payload,
        "prompt": request.prompt,
        "model_id": request.model_id,
        "reasoning_effort": (
            None if request.reasoning_effort is None else request.reasoning_effort.value
        ),
        "preset_ref": (
            None
            if request.preset_id is None and request.preset_version is None
            else {"preset_id": request.preset_id, "version": request.preset_version}
        ),
    }
    encoded = json.dumps(
        canonical_request,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class AtomLabRunService:
    """Admit one durable run inside the caller-owned database transaction."""

    def __init__(
        self,
        *,
        session: Session,
        config_registry: ConfigRegistry,
        daily_limit: int = DEFAULT_ATOM_LAB_DAILY_LIMIT,
        active_limit: int = DEFAULT_ATOM_LAB_ACTIVE_LIMIT,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        if daily_limit <= 0 or active_limit <= 0:
            raise ValueError("Atom Lab admission limits must be positive")
        self._session = session
        self._config_registry = config_registry
        self._daily_limit = daily_limit
        self._active_limit = active_limit
        self._now = now
        self._run_repository = AtomLabRunRepository(session)

    def start(
        self,
        request: AtomLabRunAdmissionRequest,
        *,
        validate: Callable[[], None],
    ) -> AtomLabRunAdmissionResult:
        lock_started_at = self._sample_utc_now()
        request_hash = compute_atom_lab_request_hash(request)
        admission = self._run_repository.lock_admission_scope(
            tenant_id=request.tenant_id,
            region=request.region,
            accepted_on=lock_started_at.date(),
            now=lock_started_at,
        )
        now = self._sample_utc_now()
        admission = self._run_repository.advance_admission_day(
            admission,
            accepted_on=now.date(),
            now=now,
        )

        existing = self._run_repository.get_by_idempotency_key(
            tenant_id=request.tenant_id,
            region=request.region,
            idempotency_key=request.idempotency_key,
        )
        if existing is not None:
            if existing.idempotency_request_hash != request_hash:
                raise AtomLabIdempotencyConflictError()
            return self._result(existing, replayed=True)

        validate()
        if admission.accepted_count >= self._daily_limit:
            raise AtomLabDailyLimitError()
        if self._active_count(request) >= self._active_limit:
            raise AtomLabActiveRunLimitError()

        scenario_definition = self._resolve_scenario(request)
        workflow = self._config_registry.get_workflow(scenario_definition.workflow_id)
        if workflow is None:
            raise LookupError(f"Atom Lab workflow not found: {scenario_definition.workflow_id}")

        event_emitter = EventEmitter(EventLogRepository(self._session))
        guest = GuestIdentityService(
            GuestIdentityRepository(self._session),
            event_emitter,
        ).create_guest(
            tenant_id=request.tenant_id,
            region=request.region,
            metadata={"runtime_scope": RuntimeScope.atom_lab.value},
        )
        scenario_session_id = new_id("scenario_session")
        scenario = ScenarioSessionService(
            ScenarioSessionRepository(self._session),
            event_emitter,
        ).start(
            ScenarioSessionRecord(
                id=scenario_session_id,
                tenant_id=request.tenant_id,
                region=request.region,
                product_id=request.product_id,
                frontend_id=request.frontend_id,
                scenario_id=scenario_definition.scenario_id,
                scenario_version=scenario_definition.version,
                guest_id=guest.id,
                current_checkpoint_id=PROCESSING_CHECKPOINT_ID,
                scenario_chain_id=scenario_session_id,
                idempotency_key=request.idempotency_key,
                idempotency_request_hash=request_hash,
                metadata={
                    "input": dict(request.input_payload),
                    **runtime_scope_metadata(RuntimeScope.atom_lab),
                },
            )
        )
        job = JobRepository(self._session).create(
            JobRecord(
                tenant_id=request.tenant_id,
                region=request.region,
                product_id=request.product_id,
                frontend_id=request.frontend_id,
                scenario_session_id=scenario.id,
                workflow_id=workflow.workflow_id,
                workflow_version=workflow.version,
                metadata={
                    "guest_id": guest.id,
                    "scenario_chain_id": scenario.id,
                    "acquisition_source": request.frontend_id,
                },
            )
        )
        record = build_atom_lab_run_record(
            self._config_registry,
            scenario=scenario,
            job=job,
            request=AtomLabSnapshotRequest(
                atom_id=request.atom_id,
                input_payload=request.input_payload,
                prompt=request.prompt,
                model_id=request.model_id,
                reasoning_effort=request.reasoning_effort,
                capability_snapshot_id=request.capability_snapshot_id,
                capability_provenance=request.capability_provenance,
                preset_id=request.preset_id,
                preset_version=request.preset_version,
            ),
        )
        stored = self._run_repository.create(
            replace(
                record,
                guest_id=guest.id,
                idempotency_key=request.idempotency_key,
                idempotency_request_hash=request_hash,
            )
        )
        self._run_repository.increment_accepted_count(admission, now=now)
        return self._result(stored, replayed=False)

    def _sample_utc_now(self) -> datetime:
        sampled = self._now()
        if sampled.tzinfo is None:
            raise ValueError("Atom Lab admission clock must return a timezone-aware datetime")
        return sampled.astimezone(UTC)

    def _active_count(self, request: AtomLabRunAdmissionRequest) -> int:
        return int(
            self._session.execute(
                self._run_repository.active_count_statement(
                    tenant_id=request.tenant_id,
                    region=request.region,
                )
            ).scalar_one()
        )

    def _resolve_scenario(self, request: AtomLabRunAdmissionRequest) -> Any:
        product = self._config_registry.get_product(request.product_id)
        if product is None:
            raise LookupError(f"Atom Lab product not found: {request.product_id}")
        matches = []
        for scenario_id in product.scenarios:
            scenario = self._config_registry.get_scenario(scenario_id)
            if scenario is None or not scenario.internal_only:
                continue
            workflow = self._config_registry.get_workflow(scenario.workflow_id)
            if (
                workflow is None
                or len(workflow.steps) != 1
                or workflow.steps[0].input_mapping
            ):
                continue
            action_config = self._config_registry.get_action_configuration(
                workflow.steps[0].action_config_id
            )
            atom_metadata = (
                None if action_config is None else action_config.metadata.get("atom_lab")
            )
            if (
                isinstance(atom_metadata, Mapping)
                and atom_metadata.get("atom_id") == request.atom_id
            ):
                matches.append(scenario)
        if len(matches) != 1:
            raise LookupError(f"Atom Lab scenario not found for atom: {request.atom_id}")
        return matches[0]

    def _result(self, record: Any, *, replayed: bool) -> AtomLabRunAdmissionResult:
        if record.guest_id is None:
            raise RuntimeError("Accepted Atom Lab run is missing its stable guest identity")
        job = JobRepository(self._session).get(record.job_id)
        if job is None:
            raise RuntimeError("Accepted Atom Lab run is missing its durable job")
        scenario_session = ScenarioSessionRepository(self._session).get(
            record.scenario_session_id,
            tenant_id=record.tenant_id,
            region=record.region,
            product_id=record.product_id,
            frontend_id=record.frontend_id,
        )
        if scenario_session is None:
            raise RuntimeError("Accepted Atom Lab run is missing its durable session")
        return AtomLabRunAdmissionResult(
            run_id=record.id,
            scenario_session_id=record.scenario_session_id,
            job_id=record.job_id,
            guest_id=record.guest_id,
            status=project_atom_lab_run_status(job.status, scenario_session.status),
            replayed=replayed,
        )


__all__ = [
    "DEFAULT_ATOM_LAB_ACTIVE_LIMIT",
    "DEFAULT_ATOM_LAB_DAILY_LIMIT",
    "AtomLabActiveRunLimitError",
    "AtomLabDailyLimitError",
    "AtomLabIdempotencyConflictError",
    "AtomLabRunAdmissionRequest",
    "AtomLabRunAdmissionResult",
    "AtomLabRunService",
    "compute_atom_lab_request_hash",
]
