import os
from dataclasses import dataclass
from math import isfinite

from anytoolai_platform_core.storage.db import (
    POSTGRES_DB_ENV,
    POSTGRES_PASSWORD_ENV,
    POSTGRES_USER_ENV,
    build_postgres_url_from_env,
)

PROJECT_DATABASE_URL_ENV = "ANYTOOLAI_DATABASE_URL"
GENERIC_DATABASE_URL_ENV = "DATABASE_URL"
POLL_INTERVAL_ENV = "ANYTOOLAI_WORKER_POLL_INTERVAL_SECONDS"


@dataclass(frozen=True)
class WorkerSettings:
    database_url: str
    poll_interval_seconds: float = 1.0
    # True only when database_url came from build_postgres_url_from_env(), which
    # percent-encodes its database segment -- PROJECT/GENERIC_DATABASE_URL_ENV are already-final
    # operator-supplied DSNs whose database name must be used exactly as given (eighteenth code
    # review pass finding). Forwarded to create_sync_engine()'s decode_database_name.
    decode_database_name: bool = False

    @classmethod
    def from_env(cls) -> "WorkerSettings":
        database_url = os.getenv(PROJECT_DATABASE_URL_ENV) or os.getenv(GENERIC_DATABASE_URL_ENV)
        decode_database_name = False
        if not database_url:
            database_url = build_postgres_url_from_env()
            decode_database_name = True
        if not database_url:
            raise RuntimeError(
                f"set {PROJECT_DATABASE_URL_ENV} or {GENERIC_DATABASE_URL_ENV}, or all of "
                f"{POSTGRES_USER_ENV}/{POSTGRES_PASSWORD_ENV}/{POSTGRES_DB_ENV}"
            )
        poll_interval_seconds = float(os.getenv(POLL_INTERVAL_ENV, "1.0"))
        if not isfinite(poll_interval_seconds) or poll_interval_seconds <= 0:
            raise ValueError(f"{POLL_INTERVAL_ENV} must be greater than zero")
        return cls(
            database_url=database_url,
            poll_interval_seconds=poll_interval_seconds,
            decode_database_name=decode_database_name,
        )
