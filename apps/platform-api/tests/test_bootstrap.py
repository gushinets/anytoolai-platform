from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
PLATFORM_CORE_SRC = REPO_ROOT / "packages" / "backend" / "platform-core" / "src"
PLATFORM_API_SRC = REPO_ROOT / "apps" / "platform-api" / "src"

for src_path in (PLATFORM_CORE_SRC, PLATFORM_API_SRC):
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

from anytoolai_platform_api import bootstrap
from anytoolai_platform_core.storage.db import (
    POSTGRES_DB_ENV,
    POSTGRES_PASSWORD_ENV,
    POSTGRES_USER_ENV,
)


def _patch_storage_builders(
    monkeypatch: Any,
) -> tuple[list[tuple[str, object]], object, object]:
    calls: list[tuple[str, object]] = []
    engine = object()
    session_factory = object()

    def fake_create_sync_engine(database_url: str) -> object:
        calls.append(("database_url", database_url))
        return engine

    def fake_build_session_factory(resolved_engine: object) -> object:
        calls.append(("engine", resolved_engine))
        return session_factory

    monkeypatch.setattr(bootstrap, "create_sync_engine", fake_create_sync_engine)
    monkeypatch.setattr(bootstrap, "build_session_factory", fake_build_session_factory)
    return calls, engine, session_factory


def test_storage_dependencies_use_database_url_env(monkeypatch: Any) -> None:
    calls, engine, session_factory = _patch_storage_builders(monkeypatch)
    monkeypatch.delenv(bootstrap.PROJECT_DATABASE_URL_ENV, raising=False)
    monkeypatch.setenv(bootstrap.GENERIC_DATABASE_URL_ENV, "postgresql://compose")

    storage = bootstrap._build_storage_dependencies(database_url=None)

    assert storage.session_factory is session_factory
    assert calls == [
        ("database_url", "postgresql://compose"),
        ("engine", engine),
    ]


def test_storage_dependencies_use_project_database_url_env(monkeypatch: Any) -> None:
    calls, engine, session_factory = _patch_storage_builders(monkeypatch)
    monkeypatch.delenv(bootstrap.GENERIC_DATABASE_URL_ENV, raising=False)
    monkeypatch.setenv(bootstrap.PROJECT_DATABASE_URL_ENV, "postgresql://project")

    storage = bootstrap._build_storage_dependencies(database_url=None)

    assert storage.session_factory is session_factory
    assert calls == [
        ("database_url", "postgresql://project"),
        ("engine", engine),
    ]


def test_storage_dependencies_stay_optional_without_database_url(monkeypatch: Any) -> None:
    monkeypatch.delenv(bootstrap.PROJECT_DATABASE_URL_ENV, raising=False)
    monkeypatch.delenv(bootstrap.GENERIC_DATABASE_URL_ENV, raising=False)
    monkeypatch.delenv(POSTGRES_USER_ENV, raising=False)
    monkeypatch.delenv(POSTGRES_PASSWORD_ENV, raising=False)
    monkeypatch.delenv(POSTGRES_DB_ENV, raising=False)
    monkeypatch.setattr(
        bootstrap,
        "create_sync_engine",
        lambda database_url: (_ for _ in ()).throw(AssertionError(database_url)),
    )

    storage = bootstrap._build_storage_dependencies(database_url=None)

    assert storage.session_factory is None


def test_storage_dependencies_build_url_from_postgres_components(monkeypatch: Any) -> None:
    calls, engine, session_factory = _patch_storage_builders(monkeypatch)
    monkeypatch.delenv(bootstrap.PROJECT_DATABASE_URL_ENV, raising=False)
    monkeypatch.delenv(bootstrap.GENERIC_DATABASE_URL_ENV, raising=False)
    monkeypatch.setenv(POSTGRES_USER_ENV, "produser")
    monkeypatch.setenv(POSTGRES_PASSWORD_ENV, "p@ss:w/rd#1%2")
    monkeypatch.setenv(POSTGRES_DB_ENV, "proddb")

    storage = bootstrap._build_storage_dependencies(database_url=None)

    assert storage.session_factory is session_factory
    [(_, built_url), _] = calls
    assert built_url == (
        "postgresql+psycopg://produser:p%40ss%3Aw%2Frd%231%252@postgres:5432/proddb"
    )


def test_storage_dependencies_prefer_project_database_url_env(monkeypatch: Any) -> None:
    calls, engine, session_factory = _patch_storage_builders(monkeypatch)
    monkeypatch.setenv(bootstrap.PROJECT_DATABASE_URL_ENV, "postgresql://project")
    monkeypatch.setenv(bootstrap.GENERIC_DATABASE_URL_ENV, "postgresql://compose")

    storage = bootstrap._build_storage_dependencies(database_url=None)

    assert storage.session_factory is session_factory
    assert calls == [
        ("database_url", "postgresql://project"),
        ("engine", engine),
    ]
