from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import URL, make_url

REPO_ROOT = Path(__file__).resolve().parents[1]
POSTGRES_TEST_DATABASE_URL_ENV = "ANYTOOLAI_POSTGRES_TEST_DATABASE_URL"
PLACEHOLDER_POSTGRESQL_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"
MIGRATIONS_SCRIPT_LOCATION = REPO_ROOT / "migrations" / "platform"


def require_postgres_test_url(skip_reason: str) -> URL:
    raw_url = os.getenv(POSTGRES_TEST_DATABASE_URL_ENV)
    if not raw_url:
        pytest.skip(f"set {POSTGRES_TEST_DATABASE_URL_ENV} to run {skip_reason}")

    url = make_url(raw_url)
    if not url.drivername.startswith("postgresql"):
        pytest.fail(f"{POSTGRES_TEST_DATABASE_URL_ENV} must use a PostgreSQL dialect")
    if not url.database:
        pytest.fail(f"{POSTGRES_TEST_DATABASE_URL_ENV} must name a maintenance database")
    return url


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def build_alembic_config(database_url: str) -> Config:
    alembic_config = Config()
    alembic_config.set_main_option("script_location", str(MIGRATIONS_SCRIPT_LOCATION))
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    return alembic_config


def create_database(maintenance_url: URL, database_name: str) -> None:
    engine = sa.create_engine(maintenance_url, future=True, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.execute(sa.text(f"CREATE DATABASE {quote_identifier(database_name)}"))
    except sa.exc.OperationalError as exc:
        raise RuntimeError(f"could not create PostgreSQL test database: {exc}") from exc
    finally:
        engine.dispose()


def drop_database(maintenance_url: URL, database_name: str) -> None:
    engine = sa.create_engine(maintenance_url, future=True, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.execute(
                sa.text(
                    f"DROP DATABASE IF EXISTS {quote_identifier(database_name)} WITH (FORCE)"
                )
            )
    finally:
        engine.dispose()


@contextmanager
def provision_database(
    *,
    database_name_prefix: str,
    upgrade_target: str | None = "head",
    skip_reason: str,
) -> Iterator[tuple[sa.Engine, Config, URL]]:
    maintenance_url = require_postgres_test_url(skip_reason)
    database_name = f"{database_name_prefix}_{uuid4().hex[:12]}"
    test_url = maintenance_url.set(database=database_name)
    engine: sa.Engine | None = None
    setup_error: BaseException | None = None
    try:
        create_database(maintenance_url, database_name)
        engine = sa.create_engine(test_url, future=True)
        alembic_config = build_alembic_config(
            test_url.render_as_string(hide_password=False)
        )
        if upgrade_target is not None:
            with engine.begin() as connection:
                alembic_config.attributes["connection"] = connection
                command.upgrade(alembic_config, upgrade_target)
        yield engine, alembic_config, test_url
    except BaseException as exc:
        setup_error = exc
        raise
    finally:
        if engine is not None:
            engine.dispose()
        try:
            drop_database(maintenance_url, database_name)
        except Exception:
            if setup_error is None:
                raise
