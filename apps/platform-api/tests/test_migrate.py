from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.script import ScriptDirectory
from anytoolai_platform_api import migrate
from anytoolai_platform_core.storage.db import (
    POSTGRES_INTERNAL_HOST_ENV,
    POSTGRES_INTERNAL_PORT_ENV,
)

from tests.db_support import (
    PLACEHOLDER_POSTGRESQL_URL,
    build_alembic_config,
    create_database,
    drop_database,
    provision_database,
    require_postgres_test_url,
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
    the database segment, so a reserved character in POSTGRES_DB_ENV no longer gets misread by
    make_url() as a query-string delimiter (the silent connect_args-injection bug this round
    closed for storage/db.py). _resolve_database_url() itself intentionally still returns this
    string percent-encoded as-is -- it feeds Alembic's offline-mode-only "sqlalchemy.url" option,
    not a live engine -- see test_main_upgrades_a_real_postgresql_database_to_head and
    test_main_resolves_a_reserved_character_database_name (nineteenth code review pass) for
    proof that main()'s actual online engine path decodes this correctly. Verified through the
    real sqlalchemy.engine.make_url() consumer, not string parsing."""
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
def test_main_resolves_a_reserved_character_database_name(monkeypatch) -> None:
    """Nineteenth code review pass finding (inline comments): migrate.main() must resolve to
    the real database when its name has a reserved character, not merely avoid the earlier
    connect_args-injection bug -- a live counterpart to
    test_resolve_database_url_keeps_a_reserved_character_db_name_percent_encoded, which only
    proves the intermediate DSN string is safe, not that migrations actually land in the
    intended database. Exercises the POSTGRES_*_ENV fallback (build_postgres_url_from_env(),
    decode_database_name=True), not an explicit URL override."""
    maintenance_url = require_postgres_test_url(
        "migrate.main() reserved-character database name coverage"
    )
    database_name = f"anytoolai_migrate_reserved_{uuid4().hex[:8]}?x"
    create_database(maintenance_url, database_name)
    try:
        monkeypatch.delenv(migrate.PROJECT_DATABASE_URL_ENV, raising=False)
        monkeypatch.delenv(migrate.GENERIC_DATABASE_URL_ENV, raising=False)
        monkeypatch.setenv(migrate.POSTGRES_USER_ENV, maintenance_url.username or "")
        monkeypatch.setenv(migrate.POSTGRES_PASSWORD_ENV, maintenance_url.password or "")
        monkeypatch.setenv(migrate.POSTGRES_DB_ENV, database_name)
        monkeypatch.setenv(POSTGRES_INTERNAL_HOST_ENV, maintenance_url.host or "")
        monkeypatch.setenv(POSTGRES_INTERNAL_PORT_ENV, str(maintenance_url.port or 5432))

        migrate.main()

        verify_engine = sa.create_engine(maintenance_url.set(database=database_name), future=True)
        try:
            with verify_engine.connect() as connection:
                version = connection.execute(
                    sa.text("SELECT version_num FROM alembic_version")
                ).scalar_one()
        finally:
            verify_engine.dispose()
        assert version == _expected_head_revision()
    finally:
        drop_database(maintenance_url, database_name)


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
