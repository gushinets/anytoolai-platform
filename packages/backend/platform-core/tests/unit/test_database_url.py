from __future__ import annotations

import pytest
from anytoolai_platform_core.storage.db import (
    POSTGRES_DB_ENV,
    POSTGRES_INTERNAL_HOST_ENV,
    POSTGRES_INTERNAL_PORT_ENV,
    POSTGRES_PASSWORD_ENV,
    POSTGRES_USER_ENV,
    build_postgres_url_from_env,
    create_sync_engine,
)


def _clear(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_var in (
        POSTGRES_USER_ENV,
        POSTGRES_PASSWORD_ENV,
        POSTGRES_DB_ENV,
        POSTGRES_INTERNAL_HOST_ENV,
        POSTGRES_INTERNAL_PORT_ENV,
    ):
        monkeypatch.delenv(env_var, raising=False)


def test_build_postgres_url_from_env_returns_none_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear(monkeypatch)

    assert build_postgres_url_from_env() is None


@pytest.mark.parametrize("missing_env", [POSTGRES_USER_ENV, POSTGRES_PASSWORD_ENV, POSTGRES_DB_ENV])
def test_build_postgres_url_from_env_returns_none_when_partially_set(
    monkeypatch: pytest.MonkeyPatch, missing_env: str
) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv(POSTGRES_USER_ENV, "anytoolai")
    monkeypatch.setenv(POSTGRES_PASSWORD_ENV, "anytoolai")
    monkeypatch.setenv(POSTGRES_DB_ENV, "anytoolai")
    monkeypatch.delenv(missing_env, raising=False)

    assert build_postgres_url_from_env() is None


def test_build_postgres_url_from_env_percent_encodes_reserved_characters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv(POSTGRES_USER_ENV, "produser")
    monkeypatch.setenv(POSTGRES_PASSWORD_ENV, "p@ss:w/rd#1%2")
    monkeypatch.setenv(POSTGRES_DB_ENV, "proddb")

    dsn = build_postgres_url_from_env()

    assert dsn == (
        "postgresql+psycopg://produser:p%40ss%3Aw%2Frd%231%252@postgres:5432/proddb"
    )

    from sqlalchemy.engine import make_url

    url = make_url(dsn)
    assert url.username == "produser"
    assert url.password == "p@ss:w/rd#1%2"
    assert url.host == "postgres"
    assert url.port == 5432
    assert url.database == "proddb"


def test_build_postgres_url_from_env_accepts_explicitly_empty_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An empty (but explicitly set) password is a valid trust-auth Postgres setup -- it must
    # not be treated the same as the variable being unset.
    _clear(monkeypatch)
    monkeypatch.setenv(POSTGRES_USER_ENV, "anytoolai")
    monkeypatch.setenv(POSTGRES_PASSWORD_ENV, "")
    monkeypatch.setenv(POSTGRES_DB_ENV, "anytoolai")

    dsn = build_postgres_url_from_env()

    assert dsn == "postgresql+psycopg://anytoolai:@postgres:5432/anytoolai"


def test_build_postgres_url_from_env_defaults_to_compose_topology(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv(POSTGRES_USER_ENV, "anytoolai")
    monkeypatch.setenv(POSTGRES_PASSWORD_ENV, "anytoolai")
    monkeypatch.setenv(POSTGRES_DB_ENV, "anytoolai")

    from sqlalchemy.engine import make_url

    url = make_url(build_postgres_url_from_env())
    assert url.host == "postgres"
    assert url.port == 5432


def test_build_postgres_url_from_env_supports_host_and_port_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv(POSTGRES_USER_ENV, "anytoolai")
    monkeypatch.setenv(POSTGRES_PASSWORD_ENV, "anytoolai")
    monkeypatch.setenv(POSTGRES_DB_ENV, "anytoolai")
    monkeypatch.setenv(POSTGRES_INTERNAL_HOST_ENV, "postgres.svc.cluster.local")
    monkeypatch.setenv(POSTGRES_INTERNAL_PORT_ENV, "6543")

    from sqlalchemy.engine import make_url

    url = make_url(build_postgres_url_from_env())
    assert url.host == "postgres.svc.cluster.local"
    assert url.port == 6543


def test_create_sync_engine_rejects_non_postgresql_urls() -> None:
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        create_sync_engine("sqlite:///tmp.db")


@pytest.mark.parametrize(
    "db_name", ["proddb", "my?db=x", "my#db", "my db", "my%db", "my/db", "my@db"]
)
def test_build_postgres_url_from_env_survives_the_real_sqlalchemy_consumer_path_for_reserved_db_name_chars(
    monkeypatch: pytest.MonkeyPatch, db_name: str
) -> None:
    """Eighteenth code review pass finding: build_postgres_url_from_env() is the production DSN
    builder (platform-api/platform-worker boot path) -- an un-encoded reserved character in
    POSTGRES_DB_ENV (e.g. "?") is parsed by sqlalchemy's make_url() as the start of a query
    string, not part of the path, letting it silently inject extra psycopg connect_args (the
    same bug class scripts/agent/runner.py's RuntimeIdentity.database_url already guards
    against). Exercise the real consumer (create_sync_engine's decode_database_name=True), not
    string parsing: the dsn must decode back to db_name with no extra connect_args."""
    _clear(monkeypatch)
    monkeypatch.setenv(POSTGRES_USER_ENV, "produser")
    monkeypatch.setenv(POSTGRES_PASSWORD_ENV, "prodpassword")
    monkeypatch.setenv(POSTGRES_DB_ENV, db_name)

    dsn = build_postgres_url_from_env()
    assert dsn is not None

    engine = create_sync_engine(dsn, decode_database_name=True)
    connect_args = engine.dialect.create_connect_args(engine.url)[1]

    assert connect_args["dbname"] == db_name
    assert connect_args["host"] == "postgres"
    assert connect_args["port"] == 5432
    assert connect_args["user"] == "produser"
    assert connect_args["password"] == "prodpassword"
    non_connection_keys = set(connect_args) - {
        "host", "port", "user", "password", "dbname", "context",
    }
    assert not non_connection_keys, f"{db_name!r} injected extra connect_args: {non_connection_keys}"
