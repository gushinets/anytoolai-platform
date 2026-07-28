from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from anytoolai_platform_api import migrate
from sqlalchemy import event
from sqlalchemy.engine import URL, make_url

POSTGRES_TEST_DATABASE_URL_ENV = "ANYTOOLAI_POSTGRES_TEST_DATABASE_URL"


def test_migrations_script_location_resolves_to_repo_migrations_dir() -> None:
    assert migrate.MIGRATIONS_SCRIPT_LOCATION.is_dir()
    assert (migrate.MIGRATIONS_SCRIPT_LOCATION / "env.py").is_file()


def test_resolve_database_url_prefers_project_specific_env_var(monkeypatch) -> None:
    monkeypatch.setenv(migrate.PROJECT_DATABASE_URL_ENV, "postgresql://project")
    monkeypatch.setenv(migrate.GENERIC_DATABASE_URL_ENV, "postgresql://generic")

    assert migrate._resolve_database_url() == "postgresql://project"


def test_resolve_database_url_falls_back_to_generic_env_var(monkeypatch) -> None:
    monkeypatch.delenv(migrate.PROJECT_DATABASE_URL_ENV, raising=False)
    monkeypatch.setenv(migrate.GENERIC_DATABASE_URL_ENV, "postgresql://generic")

    assert migrate._resolve_database_url() == "postgresql://generic"


def test_resolve_database_url_raises_when_unset(monkeypatch) -> None:
    monkeypatch.delenv(migrate.PROJECT_DATABASE_URL_ENV, raising=False)
    monkeypatch.delenv(migrate.GENERIC_DATABASE_URL_ENV, raising=False)
    monkeypatch.delenv(migrate.POSTGRES_USER_ENV, raising=False)
    monkeypatch.delenv(migrate.POSTGRES_PASSWORD_ENV, raising=False)
    monkeypatch.delenv(migrate.POSTGRES_DB_ENV, raising=False)

    with pytest.raises(RuntimeError):
        migrate._resolve_database_url()


def test_resolve_database_url_error_mentions_all_three_fallbacks(monkeypatch) -> None:
    monkeypatch.delenv(migrate.PROJECT_DATABASE_URL_ENV, raising=False)
    monkeypatch.delenv(migrate.GENERIC_DATABASE_URL_ENV, raising=False)
    monkeypatch.delenv(migrate.POSTGRES_USER_ENV, raising=False)
    monkeypatch.delenv(migrate.POSTGRES_PASSWORD_ENV, raising=False)
    monkeypatch.delenv(migrate.POSTGRES_DB_ENV, raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        migrate._resolve_database_url()

    message = str(exc_info.value)
    assert migrate.PROJECT_DATABASE_URL_ENV in message
    assert migrate.GENERIC_DATABASE_URL_ENV in message
    assert migrate.POSTGRES_USER_ENV in message
    assert migrate.POSTGRES_PASSWORD_ENV in message
    assert migrate.POSTGRES_DB_ENV in message


def test_resolve_database_url_falls_back_to_postgres_components(monkeypatch) -> None:
    monkeypatch.delenv(migrate.PROJECT_DATABASE_URL_ENV, raising=False)
    monkeypatch.delenv(migrate.GENERIC_DATABASE_URL_ENV, raising=False)
    monkeypatch.setenv(migrate.POSTGRES_USER_ENV, "produser")
    monkeypatch.setenv(migrate.POSTGRES_PASSWORD_ENV, "p@ss")
    monkeypatch.setenv(migrate.POSTGRES_DB_ENV, "proddb")

    assert migrate._resolve_database_url() == (
        "postgresql+psycopg://produser:p%40ss@postgres:5432/proddb"
    )


def _require_postgres_test_url() -> URL:
    raw_url = os.getenv(POSTGRES_TEST_DATABASE_URL_ENV)
    if not raw_url:
        pytest.skip(f"set {POSTGRES_TEST_DATABASE_URL_ENV} to run migrate.main() coverage")
    return make_url(raw_url)


def _expected_head_revision() -> str:
    config = Config()
    config.set_main_option("script_location", str(migrate.MIGRATIONS_SCRIPT_LOCATION))
    return ScriptDirectory.from_config(config).get_current_head()


def _sqlite_url(database_path: Path) -> str:
    return f"sqlite+pysqlite:///{database_path.resolve().as_posix()}"


@pytest.mark.postgresql
@pytest.mark.slow
def test_main_upgrades_a_real_postgresql_database_to_head(monkeypatch) -> None:
    maintenance_url = _require_postgres_test_url()
    database_name = f"anytoolai_migrate_test_{uuid4().hex[:12]}"
    test_url = maintenance_url.set(database=database_name)

    admin_engine = sa.create_engine(maintenance_url, future=True, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            connection.execute(sa.text(f'CREATE DATABASE "{database_name}"'))
    finally:
        admin_engine.dispose()

    try:
        monkeypatch.delenv(migrate.PROJECT_DATABASE_URL_ENV, raising=False)
        monkeypatch.setenv(
            migrate.GENERIC_DATABASE_URL_ENV, test_url.render_as_string(hide_password=False)
        )
        migrate.main()

        check_engine = sa.create_engine(test_url, future=True)
        try:
            with check_engine.connect() as connection:
                version = connection.execute(
                    sa.text("SELECT version_num FROM alembic_version")
                ).scalar_one()
        finally:
            check_engine.dispose()
        assert version == _expected_head_revision()
    finally:
        admin_engine = sa.create_engine(maintenance_url, future=True, isolation_level="AUTOCOMMIT")
        try:
            with admin_engine.connect() as connection:
                connection.execute(sa.text(f'DROP DATABASE IF EXISTS "{database_name}"'))
        finally:
            admin_engine.dispose()


def test_alembic_env_adds_repo_root_for_shared_migration_helpers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main_db = tmp_path / "migrate-main.sqlite3"
    platform_db = tmp_path / "migrate-platform.sqlite3"
    engine = sa.create_engine(_sqlite_url(main_db), future=True)

    @event.listens_for(engine, "connect")
    def attach_platform_schema(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
        del connection_record
        dbapi_connection.execute(
            "ATTACH DATABASE ? AS platform",
            (str(platform_db.resolve()),),
        )

    monkeypatch.chdir(tmp_path)
    repo_root = str(migrate.REPO_ROOT.resolve())
    monkeypatch.setattr(
        sys,
        "path",
        [entry for entry in sys.path if Path(entry or ".").resolve() != Path(repo_root)],
    )

    alembic_config = Config()
    alembic_config.set_main_option("script_location", str(migrate.MIGRATIONS_SCRIPT_LOCATION))
    alembic_config.set_main_option("sqlalchemy.url", _sqlite_url(main_db))

    try:
        with engine.begin() as connection:
            alembic_config.attributes["connection"] = connection
            command.upgrade(alembic_config, "head")

        with engine.connect() as connection:
            version = connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
    finally:
        engine.dispose()

    assert version == _expected_head_revision()
