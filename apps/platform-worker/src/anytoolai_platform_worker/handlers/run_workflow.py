"""DB-backed workflow job handler."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any

from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.providers.gateway import ProviderGatewayExecutionError
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.transactions import transaction_boundary
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from anytoolai_platform_core.workflows.runner import (
    SequentialWorkflowRunner,
    WorkflowJobService,
)
from sqlalchemy.orm import Session, sessionmaker


class ScenarioInputMissingError(PlatformError):
    def __init__(self) -> None:
        super().__init__("scenario_input_missing", "Scenario input is missing.")


class ScenarioInputInvalidError(PlatformError):
    def __init__(self) -> None:
        super().__init__("scenario_input_invalid", "Scenario input must be an object.")


RunnerFactory = Callable[[Session], SequentialWorkflowRunner]


class RunWorkflowHandler:
    """Claim and execute one workflow job using caller-owned runtime composition."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        runner_factory: RunnerFactory,
    ) -> None:
        self._session_factory = session_factory
        self._runner_factory = runner_factory

    async def handle(self, job_id: str) -> JobRecord | None:
        claimed = self._claim(job_id)
        if claimed is None:
            return self._get(job_id)

        try:
            with transaction_boundary(self._session_factory) as session:
                job = JobRepository(session).get(job_id)
                if job is None:
                    raise LookupError(f"job not found after claim: {job_id}")
                if job.status is not JobStatus.running:
                    return job

                scenario = self._load_scenario(session, job)
                input_payload = self._scenario_input(scenario)
                context = self._execution_context(job, scenario)
                runner = self._runner_factory(session)
                await runner.run_claimed_job(job, input_payload, context)
        except Exception as exc:
            self._persist_handler_failure(job_id, exc)

        return self._get(job_id)

    def cancel(self, job_id: str) -> JobRecord | None:
        with transaction_boundary(self._session_factory) as session:
            repository = JobRepository(session)
            emitter = EventEmitter(EventLogRepository(session))
            return (
                WorkflowJobService(repository, emitter).cancel_created(job_id)
                or repository.get(job_id)
            )

    def _claim(self, job_id: str) -> JobRecord | None:
        with transaction_boundary(self._session_factory) as session:
            repository = JobRepository(session)
            emitter = EventEmitter(EventLogRepository(session))
            return WorkflowJobService(repository, emitter).claim_created(job_id)

    def _get(self, job_id: str) -> JobRecord | None:
        with transaction_boundary(self._session_factory) as session:
            return JobRepository(session).get(job_id)

    def _load_scenario(self, session: Session, job: JobRecord) -> ScenarioSessionRecord:
        scenario = ScenarioSessionRepository(session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
        if scenario is None:
            raise LookupError(f"scenario session not found: {job.scenario_session_id}")
        return scenario

    def _scenario_input(self, scenario: ScenarioSessionRecord) -> dict[str, Any]:
        if "input" not in scenario.metadata:
            raise ScenarioInputMissingError()
        input_payload = scenario.metadata["input"]
        if not isinstance(input_payload, Mapping):
            raise ScenarioInputInvalidError()
        return dict(input_payload)

    def _execution_context(
        self,
        job: JobRecord,
        scenario: ScenarioSessionRecord,
    ) -> ExecutionContext:
        return ExecutionContext(
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
            scenario_session_id=scenario.id,
            job_id=job.id,
            workflow_id=job.workflow_id,
            workflow_version=job.workflow_version,
            guest_id=scenario.guest_id,
            user_id=scenario.user_id,
            scenario_chain_id=scenario.scenario_chain_id,
            handoff_id=_metadata_str(job.metadata, "handoff_id"),
            acquisition_source=_metadata_str(job.metadata, "acquisition_source"),
        )

    def _persist_handler_failure(self, job_id: str, exc: Exception) -> None:
        error_code = _safe_error_code(exc)
        error_message_safe = _safe_error_message(exc)
        with transaction_boundary(self._session_factory) as session:
            repository = JobRepository(session)
            job = repository.get(job_id)
            if job is None or job.status is not JobStatus.running:
                return
            emitter = EventEmitter(EventLogRepository(session))
            WorkflowJobService(repository, emitter).mark_failed(
                replace(
                    job,
                    status=JobStatus.failed,
                    error_code=error_code,
                    error_message_safe=error_message_safe,
                    completed_at=job.completed_at or utc_now(),
                ),
                error_code=error_code,
            )


def _metadata_str(metadata: Mapping[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) and value else None


def _safe_error_code(exc: Exception) -> str:
    if isinstance(exc, ProviderGatewayExecutionError):
        return exc.error_code
    if isinstance(exc, PlatformError):
        return exc.code
    return "workflow_execution_failed"


def _safe_error_message(exc: Exception) -> str:
    if isinstance(exc, ProviderGatewayExecutionError):
        return _redact(exc.message)
    if isinstance(exc, PlatformError):
        return _redact(str(exc))
    return "Workflow execution failed."


def _redact(message: str) -> str:
    normalized = message.strip() or "Workflow execution failed."
    if any(secret in normalized.casefold() for secret in _SECRET_KEYS):
        return "[redacted workflow error]"
    return normalized[:_MAX_SAFE_ERROR_MESSAGE_LENGTH]


_MAX_SAFE_ERROR_MESSAGE_LENGTH = 256
_SECRET_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "bearer",
        "password",
        "secret",
        "token",
    }
)
