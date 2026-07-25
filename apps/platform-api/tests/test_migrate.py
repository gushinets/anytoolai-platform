from __future__ import annotations

import os
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory
from anytoolai_platform_api import migrate
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

    with pytest.raises(RuntimeError):
        migrate._resolve_database_url()


def _require_postgres_test_url() -> URL:
    raw_url = os.getenv(POSTGRES_TEST_DATABASE_URL_ENV)
    if not raw_url:
        pytest.skip(f"set {POSTGRES_TEST_DATABASE_URL_ENV} to run migrate.main() coverage")
    return make_url(raw_url)


def _expected_head_revision() -> str:
    config = Config()
    config.set_main_option("script_location", str(migrate.MIGRATIONS_SCRIPT_LOCATION))
    return ScriptDirectory.from_config(config).get_current_head()


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
