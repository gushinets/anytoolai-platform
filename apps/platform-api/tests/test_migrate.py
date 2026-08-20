from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.script import ScriptDirectory
from anytoolai_platform_api import migrate

from tests.db_support import (
    PLACEHOLDER_POSTGRESQL_URL,
    build_alembic_config,
    provision_database,
)


def test_migrations_script_location_resolves_to_repo_migrations_dir() -> None:
    assert migrate.MIGRATIONS_SCRIPT_LOCATION.is_dir()
    assert (migrate.MIGRATIONS_SCRIPT_LOCATION / "env.py").is_file()
    assert (migrate.MIGRATIONS_SCRIPT_LOCATION / "alembic.ini").is_file()


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


def test_resolve_database_url_keeps_a_reserved_character_db_name_percent_encoded(
    monkeypatch,
) -> None:
    """Eighteenth code review pass finding: build_postgres_url_from_env() now percent-encodes
    the database segment, and migrate.py has no hook to decode it back the way
    create_sync_engine() does (Alembic builds its own engine internally from this string). The
    DSN must therefore stay percent-encoded end-to-end here -- a reserved character in
    POSTGRES_DB_ENV no longer gets misread by make_url() as a query-string delimiter (the
    silent connect_args-injection bug this round closed for storage/db.py), even though it also
    doesn't resolve to the real database name through this particular path. Verified through
    the real sqlalchemy.engine.make_url() consumer, not string parsing."""
    monkeypatch.delenv(migrate.PROJECT_DATABASE_URL_ENV, raising=False)
    monkeypatch.delenv(migrate.GENERIC_DATABASE_URL_ENV, raising=False)
    monkeypatch.setenv(migrate.POSTGRES_USER_ENV, "produser")
    monkeypatch.setenv(migrate.POSTGRES_PASSWORD_ENV, "prodpassword")
    monkeypatch.setenv(migrate.POSTGRES_DB_ENV, "mydb?sslmode=disable")

    resolved = migrate._resolve_database_url()

    url = sa.engine.make_url(resolved)
    assert url.database == "mydb%3Fsslmode%3Ddisable"
    assert dict(url.query) == {}


def _expected_head_revision() -> str:
    config = build_alembic_config(PLACEHOLDER_POSTGRESQL_URL)
    return ScriptDirectory.from_config(config).get_current_head()


@pytest.mark.postgresql
@pytest.mark.slow
def test_main_upgrades_a_real_postgresql_database_to_head(monkeypatch) -> None:
    with provision_database(
        database_name_prefix="anytoolai_migrate_test",
        upgrade_target=None,
        skip_reason="migrate.main() coverage",
    ) as (engine, _alembic_config, test_url):
        monkeypatch.delenv(migrate.PROJECT_DATABASE_URL_ENV, raising=False)
        monkeypatch.setenv(
            migrate.GENERIC_DATABASE_URL_ENV, test_url.render_as_string(hide_password=False)
        )
        migrate.main()

        with engine.connect() as connection:
            version = connection.execute(
                sa.text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        assert version == _expected_head_revision()


@pytest.mark.postgresql
@pytest.mark.slow
def test_alembic_env_adds_repo_root_for_shared_migration_helpers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    repo_root = str(migrate.REPO_ROOT.resolve())
    monkeypatch.setattr(
        sys,
        "path",
        [entry for entry in sys.path if Path(entry or ".").resolve() != Path(repo_root)],
    )

    with provision_database(
        database_name_prefix="anytoolai_migrate_env_test",
        upgrade_target=None,
        skip_reason="Alembic env PostgreSQL coverage",
    ) as (engine, alembic_config, _test_url):
        with engine.begin() as connection:
            alembic_config.attributes["connection"] = connection
            command.upgrade(alembic_config, "head")

        with engine.connect() as connection:
            version = connection.execute(
                sa.text("SELECT version_num FROM alembic_version")
            ).scalar_one()

    assert version == _expected_head_revision()


def test_alembic_offline_cli_generates_sql_from_non_repo_cwd(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(migrate.MIGRATIONS_SCRIPT_LOCATION / "alembic.ini"),
            "upgrade",
            "head",
            "--sql",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    combined_output = f"{result.stdout}\n{result.stderr}"

    assert result.returncode == 0, combined_output
    assert "CREATE TABLE platform.product_handoffs" in result.stdout
    assert "DROP INDEX IF EXISTS platform.ix_product_handoffs_target_session" in result.stdout
    assert "CREATE INDEX IF NOT EXISTS ix_product_handoffs_status_expiry" in result.stdout
    assert "CREATE INDEX IF NOT EXISTS platform." not in result.stdout
    assert "ModuleNotFoundError" not in combined_output
    assert "NoInspectionAvailable" not in combined_output
