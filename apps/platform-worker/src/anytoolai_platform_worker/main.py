from __future__ import annotations

import asyncio

from anytoolai_platform_worker.composition import build_worker
from anytoolai_platform_worker.settings import WorkerSettings
from anytoolai_platform_core.common.logging import configure_json_logging


async def run() -> None:
    settings = WorkerSettings.from_env()
    worker = build_worker(
        database_url=settings.database_url,
        poll_interval_seconds=settings.poll_interval_seconds,
    )
    await worker.run_forever()


def main() -> None:
    configure_json_logging("platform-worker")
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
