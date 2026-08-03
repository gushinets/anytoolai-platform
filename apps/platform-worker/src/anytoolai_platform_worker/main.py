from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Callable

from anytoolai_platform_core.common.logging import configure_json_logging

from anytoolai_platform_worker.composition import build_worker
from anytoolai_platform_worker.settings import WorkerSettings

logger = logging.getLogger(__name__)


def _register_sigterm_handler(
    loop: asyncio.AbstractEventLoop, callback: Callable[[], None]
) -> None:
    """Best-effort hookup for the SIGTERM graceful-drain path.

    `loop.add_signal_handler` is POSIX-only -- Windows' `ProactorEventLoop` raises
    `NotImplementedError` unconditionally. On Windows the worker still runs and still
    exits via `KeyboardInterrupt` (SIGINT) as before; it just does not get the
    finish-in-flight-job SIGTERM drain.
    """
    try:
        loop.add_signal_handler(signal.SIGTERM, callback)
    except NotImplementedError:
        logger.warning(
            "worker.sigterm_drain_unavailable",
            extra={"event": "worker.sigterm_drain_unavailable"},
        )


async def run() -> None:
    settings = WorkerSettings.from_env()
    worker = build_worker(
        database_url=settings.database_url,
        poll_interval_seconds=settings.poll_interval_seconds,
    )
    try:
        _register_sigterm_handler(asyncio.get_running_loop(), worker.request_shutdown)
        await worker.run_forever()
    finally:
        worker.dispose()


def main() -> None:
    configure_json_logging("platform-worker")
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
