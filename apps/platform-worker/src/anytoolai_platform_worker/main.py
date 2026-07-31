from __future__ import annotations

import asyncio
import signal

from anytoolai_platform_core.common.logging import configure_json_logging

from anytoolai_platform_worker.composition import build_worker
from anytoolai_platform_worker.settings import WorkerSettings


async def run() -> None:
    settings = WorkerSettings.from_env()
    worker = build_worker(
        database_url=settings.database_url,
        poll_interval_seconds=settings.poll_interval_seconds,
    )
    # SIGTERM (docker stop / compose down / k8s eviction) drains: finish the
    # in-flight job, take no more. SIGINT stays the existing instant-exit path
    # below, for interactive Ctrl-C during local development.
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, worker.request_shutdown)
    await worker.run_forever()


def main() -> None:
    configure_json_logging("platform-worker")
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
