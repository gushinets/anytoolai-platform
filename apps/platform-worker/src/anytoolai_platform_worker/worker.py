"""Minimal worker façade for DB-backed workflow jobs."""

from __future__ import annotations

import asyncio
import logging

from anytoolai_platform_core.workflows.models import JobRecord
from anytoolai_platform_core.common.logging import (
    bind_log_context,
    log_event,
    reset_log_context,
)

from anytoolai_platform_worker.handlers.run_workflow import RunWorkflowHandler
from anytoolai_platform_worker.queues import DatabaseJobQueue

logger = logging.getLogger(__name__)


class Worker:
    def __init__(
        self,
        workflow_handler: RunWorkflowHandler,
        *,
        job_queue: DatabaseJobQueue | None = None,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self._workflow_handler = workflow_handler
        self._job_queue = job_queue
        self._poll_interval_seconds = poll_interval_seconds

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
        while True:
            try:
                result = await self.process_next_job()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("worker loop iteration failed")
                await asyncio.sleep(self._poll_interval_seconds)
                continue
            if result is None:
                await asyncio.sleep(self._poll_interval_seconds)
