"""DB-backed workflow job handler."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any

from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.common.metadata import metadata_str
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.providers.gateway import ProviderGatewayExecutionError
from anytoolai_platform_core.scenarios.models import (
    ScenarioSessionRecord,
    ScenarioSessionStatus,
)
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.scenarios.service import ScenarioSessionService
from anytoolai_platform_core.storage.transactions import transaction_boundary
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from anytoolai_platform_core.workflows.runner import (
    SequentialWorkflowRunner,
    WorkflowJobService,
)
from sqlalchemy.orm import Session, sessionmaker

from anytoolai_platform_worker.lease import JobLease, NullJobLease

logger = logging.getLogger(__name__)


class ScenarioInputMissingError(PlatformError):
    def __init__(self) -> None:
        super().__init__("scenario_input_missing", "Scenario input is missing.")


class ScenarioInputInvalidError(PlatformError):
    def __init__(self) -> None:
        super().__init__("scenario_input_invalid", "Scenario input must be an object.")


class JobScenarioSessionInvalidError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "job_scenario_session_invalid",
            "Job scenario session linkage is invalid.",
        )


RunnerFactory = Callable[[Session], SequentialWorkflowRunner]


class RunWorkflowHandler:
    """Claim and execute one workflow job using caller-owned runtime composition."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        runner_factory: RunnerFactory,
        lease: JobLease | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._runner_factory = runner_factory
        self._lease = lease if lease is not None else NullJobLease()

    async def handle(self, job_id: str) -> JobRecord | None:
        try:
            claimed = self._claim(job_id)
        except asyncio.CancelledError:
            raise
        except JobScenarioSessionInvalidError as exc:
            self._persist_created_job_failure(job_id, exc)
            return self._get(job_id)
        if claimed is None:
            # The job is already past `created` (a prior call already claimed/ran it, or
            # it doesn't exist). If a prior run left the job succeeded but its scenario
            # un-reconciled (e.g. mark_completed failed both on the happy path and on
            # the recovery attempt below), this is the only remaining path that ever
            # revisits it -- without this, that scenario would stay `running` forever.
            self._try_reconcile_succeeded_job_scenario(job_id)
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
                updated_job = JobRepository(session).get(job_id)
                if updated_job is None:
                    raise LookupError(f"job not found after execution: {job_id}")
                if updated_job.status is JobStatus.succeeded:
                    refreshed_scenario = self._load_scenario(session, updated_job)
                    self._complete_scenario_if_still_running(
                        session, updated_job, refreshed_scenario
                    )
        except asyncio.CancelledError:
            self._persist_handler_cancellation(job_id)
            raise
        except Exception as exc:
            self._persist_handler_failure(job_id, exc)
        finally:
            self._lease.release(job_id)

        return self._get(job_id)

    def terminate_orphaned_job(self, job_id: str) -> None:
        """Fail a `running` job whose lease-holder is gone (see `reconciliation.py`).

        Never raises: called from a sweep over multiple candidate jobs, and one
        failure here must not abort the rest of the pass.
        """
        try:
            self._persist_running_failure(
                job_id,
                error_code="worker_lease_lost",
                error_message_safe=("Worker holding this job's lease was lost (crash or restart)."),
            )
        except Exception:
            logger.exception(
                "run_workflow.terminate_orphaned_job_failed",
                extra={
                    "event": "run_workflow.terminate_orphaned_job_failed",
                    "fields": {"job_id": job_id},
                },
            )

    def cancel(self, job_id: str) -> JobRecord | None:
        with transaction_boundary(self._session_factory) as session:
            repository = JobRepository(session)
            emitter = EventEmitter(EventLogRepository(session))
            return WorkflowJobService(repository, emitter).cancel_created(job_id) or repository.get(
                job_id
            )

    def _claim(self, job_id: str) -> JobRecord | None:
        with transaction_boundary(self._session_factory) as session:
            repository = JobRepository(session)
            emitter = EventEmitter(EventLogRepository(session))
            scenario_service = ScenarioSessionService(
                ScenarioSessionRepository(session),
                emitter,
            )
            job = repository.get(job_id)
            if job is None or job.status is not JobStatus.created:
                return None

            # Held until handle()'s finally releases it after the terminal-state commit.
            # A failed acquire means another worker already owns this job -- not an
            # error, just skip it.
            if not self._lease.acquire(job_id):
                return None

            try:
                scenario = self._load_scenario(session, job)
                metadata = {
                    **job.metadata,
                    "guest_id": scenario.guest_id,
                    "user_id": scenario.user_id,
                    "scenario_chain_id": scenario.scenario_chain_id,
                }
                claimed = WorkflowJobService(repository, emitter).claim_created(
                    job_id,
                    metadata=metadata,
                )
                if claimed is None:
                    self._lease.release(job_id)
                    return None
                scenario_service.mark_running(scenario)
                return claimed
            except BaseException:
                self._lease.release(job_id)
                raise

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
            raise JobScenarioSessionInvalidError()
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
            handoff_id=metadata_str(job.metadata, "handoff_id"),
            acquisition_source=metadata_str(job.metadata, "acquisition_source"),
        )

    def _persist_handler_failure(self, job_id: str, exc: Exception) -> None:
        self._persist_running_failure(
            job_id,
            error_code=_safe_error_code(exc),
            error_message_safe=_safe_error_message(exc),
        )

    def _persist_running_failure(
        self,
        job_id: str,
        *,
        error_code: str,
        error_message_safe: str,
    ) -> None:
        # The runner's own rollback-recovery callback may already have restored the job
        # to succeeded in an independent transaction (e.g. mark_completed itself raised
        # after the workflow succeeded). Reconciling the scenario for that case needs its
        # own isolated transaction/try-except (see _try_reconcile_succeeded_job_scenario)
        # so a repeat failure there can't escape this method mid-transaction and leave
        # the session in a broken state -- so it's deferred to after this transaction
        # exits cleanly, rather than being called from inside it.
        reconcile_succeeded_job = False
        with transaction_boundary(self._session_factory) as session:
            repository = JobRepository(session)
            job = repository.get(job_id)
            if job is None:
                return
            emitter = EventEmitter(EventLogRepository(session))
            if job.status is JobStatus.running:
                job = WorkflowJobService(repository, emitter).mark_failed(
                    replace(
                        job,
                        status=JobStatus.failed,
                        error_code=error_code,
                        error_message_safe=error_message_safe,
                        completed_at=job.completed_at or utc_now(),
                    ),
                    error_code=error_code,
                )
                scenario_error_code = error_code
            elif job.status is JobStatus.succeeded:
                reconcile_succeeded_job = True
            elif job.status is not JobStatus.failed:
                return
            else:
                # A different error_code than what's already stored means this call
                # didn't come from a repeat `terminate_orphaned_job` on the same
                # orphan -- execution kept running past its lease being reclaimed and
                # only now reached a terminal outcome of its own, colliding with the
                # sweep's already-committed `failed`/worker_lease_lost. Known residual
                # race (see plans/ANY-147.md); not auto-fixed, just made observable.
                if job.error_code == "worker_lease_lost" and error_code != "worker_lease_lost":
                    logger.warning(
                        "worker.job_completed_after_lease_lost",
                        extra={
                            "event": "worker.job_completed_after_lease_lost",
                            "fields": {"job_id": job_id, "late_error_code": error_code},
                        },
                    )
                scenario_error_code = job.error_code or error_code

            if not reconcile_succeeded_job:
                scenario = ScenarioSessionRepository(session).get(
                    job.scenario_session_id,
                    tenant_id=job.tenant_id,
                    region=job.region,
                    product_id=job.product_id,
                    frontend_id=job.frontend_id,
                )
                if scenario is not None and scenario.status is not ScenarioSessionStatus.failed:
                    ScenarioSessionService(
                        ScenarioSessionRepository(session),
                        emitter,
                    ).mark_failed(
                        replace(
                            scenario,
                            completed_at=job.completed_at or utc_now(),
                        ),
                        error_code=scenario_error_code,
                        context=self._execution_context(job, scenario),
                    )

        if reconcile_succeeded_job:
            self._try_reconcile_succeeded_job_scenario(job_id)

    def _complete_scenario_if_still_running(
        self,
        session: Session,
        job: JobRecord,
        scenario: ScenarioSessionRecord,
    ) -> None:
        # Only the scenario's own `running` state (set by `_claim()`'s mark_running
        # right before this job started) is safe to advance to `completed` here. Any
        # other status means something else -- an independent expiry sweep, a prior
        # completion/failure -- already moved the scenario on, and blindly overwriting
        # it back to `completed` would clobber that and emit a stale scenario.completed
        # event. Shared by both the happy path and the rollback-recovery reconciliation
        # path below so a future change to this guard only has to be made once.
        if scenario.status is not ScenarioSessionStatus.running:
            return
        ScenarioSessionService(
            ScenarioSessionRepository(session),
            EventEmitter(EventLogRepository(session)),
        ).mark_completed(
            replace(scenario, completed_at=job.completed_at or utc_now()),
            context=self._execution_context(job, scenario),
        )

    def _reconcile_succeeded_job_scenario(self, session: Session, job: JobRecord) -> None:
        scenario = ScenarioSessionRepository(session).get(
            job.scenario_session_id,
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
        )
        if scenario is None:
            return
        self._complete_scenario_if_still_running(session, job, scenario)

    def _try_reconcile_succeeded_job_scenario(self, job_id: str) -> None:
        """Best-effort, safe to call repeatedly (e.g. from a later `handle()` call).

        Never lets a failure here escape to the caller: a job that already succeeded
        must not be reported as a fresh handler failure just because its scenario
        reconciliation is still stuck, and swallowing it here is what keeps this
        retryable from _persist_handler_failure and handle()'s claimed-is-None path
        instead of a repeat failure permanently wedging the scenario in `running`.
        """
        try:
            with transaction_boundary(self._session_factory) as session:
                job = JobRepository(session).get(job_id)
                if job is None or job.status is not JobStatus.succeeded:
                    return
                self._reconcile_succeeded_job_scenario(session, job)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "run_workflow.scenario_reconciliation_failed",
                extra={
                    "event": "run_workflow.scenario_reconciliation_failed",
                    "fields": {"job_id": job_id},
                },
            )

    def _persist_created_job_failure(self, job_id: str, exc: Exception) -> None:
        error_code = _safe_error_code(exc)
        error_message_safe = _safe_error_message(exc)
        with transaction_boundary(self._session_factory) as session:
            repository = JobRepository(session)
            job = repository.get(job_id)
            if job is None or job.status is not JobStatus.created:
                return
            emitter = EventEmitter(EventLogRepository(session))
            WorkflowJobService(repository, emitter).mark_failed_from_created(
                replace(
                    job,
                    status=JobStatus.failed,
                    error_code=error_code,
                    error_message_safe=error_message_safe,
                    completed_at=job.completed_at or utc_now(),
                ),
                error_code=error_code,
            )

    def _persist_handler_cancellation(self, job_id: str) -> None:
        with transaction_boundary(self._session_factory) as session:
            repository = JobRepository(session)
            job = repository.get(job_id)
            if job is None:
                return
            emitter = EventEmitter(EventLogRepository(session))
            if job.status is JobStatus.running:
                job = WorkflowJobService(repository, emitter).mark_canceled(job)
            elif job.status is not JobStatus.canceled:
                return
            scenario = ScenarioSessionRepository(session).get(
                job.scenario_session_id,
                tenant_id=job.tenant_id,
                region=job.region,
                product_id=job.product_id,
                frontend_id=job.frontend_id,
            )
            if scenario is not None and scenario.status is not ScenarioSessionStatus.failed:
                ScenarioSessionService(
                    ScenarioSessionRepository(session),
                    emitter,
                ).mark_failed(
                    replace(
                        scenario,
                        completed_at=utc_now(),
                    ),
                    error_code="workflow_execution_cancelled",
                    context=self._execution_context(job, scenario),
                )


def _safe_error_code(exc: Exception) -> str:
    if isinstance(exc, ProviderGatewayExecutionError):
        return exc.error_code
    if isinstance(exc, PlatformError):
        return exc.code
    return "workflow_execution_failed"


def _safe_error_message(exc: Exception) -> str:
    if isinstance(exc, ProviderGatewayExecutionError):
        return exc.message
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
