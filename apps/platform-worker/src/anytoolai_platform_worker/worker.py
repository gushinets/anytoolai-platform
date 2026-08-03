"""Minimal worker façade for DB-backed workflow jobs."""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from anytoolai_platform_core.common.logging import (
    bind_log_context,
    log_event,
    reset_log_context,
)
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus

from anytoolai_platform_worker.queues import WorkflowJobMessage

logger = logging.getLogger(__name__)


class WorkflowHandler(Protocol):
    """What `Worker` needs from a job handler -- see `RunWorkflowHandler` for the real one.

    Narrowed to exactly the methods `Worker` calls (rather than typing against the
    concrete class) so tests can hand it a small fake without either a fragile
    subclass or a `# type: ignore` papering over the mismatch.
    """

    async def handle(self, job_id: str) -> JobRecord | None: ...
    def cancel(self, job_id: str) -> JobRecord | None: ...
    def dispose(self) -> None: ...


class JobQueue(Protocol):
    """What `Worker` needs from a job queue -- see `DatabaseJobQueue` for the real one."""

    def next_message(self) -> WorkflowJobMessage | None: ...


class OrphanReconciler(Protocol):
    """What `Worker` needs from a reconciler -- see `OrphanedRunningJobReconciler`."""

    def reconcile_once(self) -> int: ...


class Worker:
    def __init__(
        self,
        workflow_handler: WorkflowHandler,
        *,
        job_queue: JobQueue | None = None,
        poll_interval_seconds: float = 1.0,
        reconciler: OrphanReconciler | None = None,
    ) -> None:
        self._workflow_handler = workflow_handler
        self._job_queue = job_queue
        self._poll_interval_seconds = poll_interval_seconds
        self._reconciler = reconciler
        self._stopping = asyncio.Event()

    def request_shutdown(self) -> None:
        """Signal `run_forever()` to drain: finish the in-flight job, take no more.

        Synchronous and side-effect-free beyond setting a flag, so it is safe to
        register directly as an `asyncio.add_signal_handler` callback.
        """
        self._stopping.set()

    def dispose(self) -> None:
        """Release resources (the lease's dedicated connection pool) after
        `run_forever()` has returned. Call once during shutdown."""
        self._workflow_handler.dispose()

    async def process_job(self, job_id: str) -> JobRecord | None:
        token = bind_log_context(job_id=job_id)
        log_event(logger, "worker.job_started", job_id=job_id)
        try:
            result = await self._workflow_handler.handle(job_id)
        except asyncio.CancelledError:
            log_event(logger, "worker.job_cancelled", job_id=job_id)
            raise
        except Exception:
            logger.exception(
                "worker.job_failed",
                extra={"event": "worker.job_failed", "fields": {"job_id": job_id}},
            )
            raise
        else:
            if result is not None:
                log_event(
                    logger,
                    "worker.job_completed",
                    job_id=result.id,
                    scenario_session_id=result.scenario_session_id,
                    workflow_id=result.workflow_id,
                    status=result.status.value,
                )
            return result
        finally:
            reset_log_context(token)

    def cancel_job(self, job_id: str) -> JobRecord | None:
        return self._workflow_handler.cancel(job_id)

    async def process_next_job(self) -> JobRecord | None:
        if self._job_queue is None:
            raise RuntimeError("worker has no DB job queue configured")
        message = self._job_queue.next_message()
        if message is None:
            return None
        return await self.process_job(message.job_id)

    async def run_forever(self) -> None:
        if self._job_queue is None:
            raise RuntimeError("worker has no DB job queue configured")
        self._sweep_orphaned_jobs()
        while not self._stopping.is_set():
            try:
                result = await self.process_next_job()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("worker loop iteration failed")
                await asyncio.sleep(self._poll_interval_seconds)
                continue
            # `result.status is JobStatus.created` means `_claim()` lost a race for this
            # job (another worker's `pg_try_advisory_lock` won first) and handed back the
            # still-`created` row untouched -- `next_message()` has no `FOR UPDATE`, so two
            # workers can pick the same candidate. Without treating that the same as "no
            # job available", this loop would spin hot on the same losing candidate with
            # no backoff until the winner's transaction commits.
            if result is None or result.status is JobStatus.created:
                self._sweep_orphaned_jobs()
                await asyncio.sleep(self._poll_interval_seconds)

    def _sweep_orphaned_jobs(self) -> None:
        """Reconcile `running` jobs whose lease-holder is gone. Best-effort, never raises.

        Called once before the loop starts (catches orphans left by a previous
        crash) and again on every idle iteration -- never mid-job, since the flag
        is only consulted between `process_next_job()` calls.
        """
        if self._reconciler is None:
            return
        try:
            terminated = self._reconciler.reconcile_once()
        except Exception:
            logger.exception("worker.reconciliation_sweep_failed")
            return
        if terminated:
            log_event(logger, "worker.orphaned_jobs_terminated", count=terminated)
