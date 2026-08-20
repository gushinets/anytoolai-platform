"""Console entrypoint for running Alembic migrations against a real database."""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config

from anytoolai_platform_api.bootstrap import (
    GENERIC_DATABASE_URL_ENV,
    PROJECT_DATABASE_URL_ENV,
)
from anytoolai_platform_api.bootstrap import _resolve_database_url as _bootstrap_database_url
from anytoolai_platform_core.storage.db import (
    POSTGRES_DB_ENV,
    POSTGRES_PASSWORD_ENV,
    POSTGRES_USER_ENV,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
MIGRATIONS_SCRIPT_LOCATION = REPO_ROOT / "migrations" / "platform"


def _resolve_database_url() -> str:
    # _bootstrap_database_url's second element (decode_database_name) is deliberately unused
    # here: Alembic (migrations/platform/env.py's engine_from_config) builds its own engine
    # internally from this string, with no hook for us to decode the database segment after its
    # own make_url() call the way create_sync_engine() does -- so the DSN is kept consistently
    # percent-encoded end-to-end instead. A database name with a reserved character (?, #, /)
    # therefore still won't resolve correctly through this path, but it now fails loudly
    # (connecting to a nonexistent, still-encoded name) instead of the pre-eighteenth-round
    # silent connect_args-injection bug.
    database_url, _decode_database_name = _bootstrap_database_url(None)
    if not database_url:
        raise RuntimeError(
            f"Set {PROJECT_DATABASE_URL_ENV} or {GENERIC_DATABASE_URL_ENV}, or all of "
            f"{POSTGRES_USER_ENV}/{POSTGRES_PASSWORD_ENV}/{POSTGRES_DB_ENV}, before running "
            "migrations."
        )
    return database_url


def main() -> None:
    alembic_config = Config()
    alembic_config.set_main_option("script_location", str(MIGRATIONS_SCRIPT_LOCATION))
    # alembic.config.Config stores options via configparser with interpolation enabled, so a
    # literal `%` in the URL (e.g. a URL-encoded password like `p%40ss`) must be escaped as
    # `%%` or set_main_option raises ValueError: invalid interpolation syntax.
    alembic_config.set_main_option(
        "sqlalchemy.url", _resolve_database_url().replace("%", "%%")
    )
    command.upgrade(alembic_config, "head")


if __name__ == "__main__":
    main()
