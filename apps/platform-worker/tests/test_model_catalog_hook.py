from __future__ import annotations

import asyncio
from typing import Any

from anytoolai_platform_worker.queues import WorkflowJobMessage
from anytoolai_platform_worker.worker import Worker

EXPECTED_REFRESH_CALLS = 2


class NoopHandler:
    def __init__(self) -> None:
        self.handled: list[str] = []

    async def handle(self, job_id: str) -> Any:
        self.handled.append(job_id)
        return None

    def cancel(self, job_id: str) -> None:
        del job_id

    def dispose(self) -> None:
        pass


class OneJobQueue:
    def __init__(self) -> None:
        self._message = WorkflowJobMessage(job_id="job-one")

    def next_message(self) -> WorkflowJobMessage | None:
        message, self._message = self._message, None
        return message


class TwoJobQueue:
    def __init__(self) -> None:
        self._messages = [
            WorkflowJobMessage(job_id="job-one"),
            WorkflowJobMessage(job_id="job-two"),
        ]

    def next_message(self) -> WorkflowJobMessage | None:
        return self._messages.pop(0) if self._messages else None


def test_catalog_refresh_runs_on_start_and_between_workflow_jobs() -> None:
    holder: dict[str, Worker] = {}

    class StoppingRefreshHook:
        def __init__(self) -> None:
            self.calls = 0

        async def refresh_if_due(self) -> None:
            self.calls += 1
            if self.calls == EXPECTED_REFRESH_CALLS:
                holder["worker"].request_shutdown()

    hook = StoppingRefreshHook()
    handler = NoopHandler()
    worker = Worker(
        handler,
        job_queue=OneJobQueue(),
        poll_interval_seconds=0,
        catalog_refresh_hook=hook,
    )
    holder["worker"] = worker

    asyncio.run(worker.run_forever())

    assert handler.handled == ["job-one"]
    assert hook.calls == EXPECTED_REFRESH_CALLS


def test_catalog_refresh_failure_does_not_stop_workflow_loop() -> None:
    holder: dict[str, Worker] = {}

    class FailingOnceRefreshHook:
        def __init__(self) -> None:
            self.calls = 0

        async def refresh_if_due(self) -> None:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("database unavailable")
            holder["worker"].request_shutdown()

    hook = FailingOnceRefreshHook()
    handler = NoopHandler()
    worker = Worker(
        handler,
        job_queue=OneJobQueue(),
        poll_interval_seconds=0,
        catalog_refresh_hook=hook,
    )
    holder["worker"] = worker

    asyncio.run(worker.run_forever())

    assert handler.handled == ["job-one"]
    assert hook.calls == EXPECTED_REFRESH_CALLS


def test_shutdown_requested_during_refresh_does_not_claim_another_job() -> None:
    holder: dict[str, Worker] = {}

    class ShutdownOnSecondRefreshHook:
        def __init__(self) -> None:
            self.calls = 0

        async def refresh_if_due(self) -> None:
            self.calls += 1
            if self.calls == EXPECTED_REFRESH_CALLS:
                holder["worker"].request_shutdown()

    hook = ShutdownOnSecondRefreshHook()
    handler = NoopHandler()
    worker = Worker(
        handler,
        job_queue=TwoJobQueue(),
        poll_interval_seconds=0,
        catalog_refresh_hook=hook,
    )
    holder["worker"] = worker

    asyncio.run(worker.run_forever())

    assert handler.handled == ["job-one"]
    assert hook.calls == EXPECTED_REFRESH_CALLS
