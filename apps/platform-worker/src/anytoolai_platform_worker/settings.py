import os
from dataclasses import dataclass
from math import isfinite

PROJECT_DATABASE_URL_ENV = "ANYTOOLAI_DATABASE_URL"
GENERIC_DATABASE_URL_ENV = "DATABASE_URL"
POLL_INTERVAL_ENV = "ANYTOOLAI_WORKER_POLL_INTERVAL_SECONDS"


@dataclass(frozen=True)
class WorkerSettings:
    database_url: str
    poll_interval_seconds: float = 1.0

    @classmethod
    def from_env(cls) -> "WorkerSettings":
        database_url = os.getenv(PROJECT_DATABASE_URL_ENV) or os.getenv(
            GENERIC_DATABASE_URL_ENV
        )
        if not database_url:
            raise RuntimeError(
                f"set {PROJECT_DATABASE_URL_ENV} or {GENERIC_DATABASE_URL_ENV}"
            )
        poll_interval_seconds = float(os.getenv(POLL_INTERVAL_ENV, "1.0"))
        if not isfinite(poll_interval_seconds) or poll_interval_seconds <= 0:
            raise ValueError(f"{POLL_INTERVAL_ENV} must be greater than zero")
        return cls(
            database_url=database_url,
            poll_interval_seconds=poll_interval_seconds,
        )
