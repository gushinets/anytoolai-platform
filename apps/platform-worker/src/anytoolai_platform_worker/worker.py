"""Minimal worker façade for DB-backed workflow jobs."""

from __future__ import annotations

import asyncio

from anytoolai_platform_core.workflows.models import JobRecord

from anytoolai_platform_worker.handlers.run_workflow import RunWorkflowHandler
from anytoolai_platform_worker.queues import DatabaseJobQueue


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
        return await self._workflow_handler.handle(job_id)

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
            result = await self.process_next_job()
            if result is None:
                await asyncio.sleep(self._poll_interval_seconds)
