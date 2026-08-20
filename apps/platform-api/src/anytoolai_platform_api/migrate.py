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
    create_sync_engine,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
MIGRATIONS_SCRIPT_LOCATION = REPO_ROOT / "migrations" / "platform"


def _resolve_database_url() -> str:
    database_url, _decode_database_name = _bootstrap_database_url(None)
    if not database_url:
        raise RuntimeError(
            f"Set {PROJECT_DATABASE_URL_ENV} or {GENERIC_DATABASE_URL_ENV}, or all of "
            f"{POSTGRES_USER_ENV}/{POSTGRES_PASSWORD_ENV}/{POSTGRES_DB_ENV}, before running "
            "migrations."
        )
    return database_url


def main() -> None:
    database_url = _resolve_database_url()
    # _bootstrap_database_url is pure (env-var reads only, no I/O), so re-calling it here for
    # just the decode flag -- rather than changing _resolve_database_url()'s tested, str-only
    # return contract -- costs nothing.
    _, decode_database_name = _bootstrap_database_url(None)

    alembic_config = Config()
    alembic_config.set_main_option("script_location", str(MIGRATIONS_SCRIPT_LOCATION))
    # alembic.config.Config stores options via configparser with interpolation enabled, so a
    # literal `%` in the URL (e.g. a URL-encoded password like `p%40ss`) must be escaped as
    # `%%` or set_main_option raises ValueError: invalid interpolation syntax. Only Alembic's
    # offline (--sql) mode reads this option; the online path below builds its own engine and
    # hands Alembic a live connection instead, so it never re-parses this string.
    alembic_config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

    # engine_from_config (migrations/platform/env.py's fallback) would build its own engine
    # straight from the option above, with no hook to decode a percent-encoded database segment
    # the way create_sync_engine() does -- so a reserved character in the database name would
    # resolve to the wrong (still-encoded) name. Build the engine ourselves, honoring the same
    # decode_database_name contract as every other build_postgres_url_from_env() consumer, and
    # hand Alembic the live connection through env.py's existing config.attributes["connection"]
    # hook (already used by tests/db_support.py's provision_database) so it skips
    # engine_from_config entirely.
    engine = create_sync_engine(database_url, decode_database_name=decode_database_name)
    try:
        with engine.connect() as connection:
            alembic_config.attributes["connection"] = connection
            command.upgrade(alembic_config, "head")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
