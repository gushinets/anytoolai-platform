"""Composition root for platform runtime and future product bundles."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.storage.db import build_postgres_url_from_env, create_sync_engine
from anytoolai_platform_core.storage.transactions import build_session_factory

PROJECT_DATABASE_URL_ENV = "ANYTOOLAI_DATABASE_URL"
GENERIC_DATABASE_URL_ENV = "DATABASE_URL"


@dataclass(frozen=True)
class RuntimeStorageDependencies:
    session_factory: Any | None = None


@dataclass(frozen=True)
class RuntimeBootstrapResult:
    loaded_bundles: list[str]
    config_registry: ConfigRegistry
    storage: RuntimeStorageDependencies


def build_runtime(
    config_root: Path | None = None,
    *,
    database_url: str | None = None,
) -> RuntimeBootstrapResult:
    # MVP-A loads platform actions + kernel demo configs only.
    # MVP-B may add FreelancerSuiteBundle here, never inside platform-core.
    config_registry = build_config_registry(config_root)
    return RuntimeBootstrapResult(
        loaded_bundles=["platform_actions", "kernel_demo"],
        config_registry=config_registry,
        storage=_build_storage_dependencies(database_url),
    )


def _build_storage_dependencies(database_url: str | None) -> RuntimeStorageDependencies:
    resolved_database_url, decode_database_name = _resolve_database_url(database_url)
    if not resolved_database_url:
        return RuntimeStorageDependencies()

    engine = create_sync_engine(
        resolved_database_url, decode_database_name=decode_database_name
    )
    return RuntimeStorageDependencies(session_factory=build_session_factory(engine))


def _resolve_database_url(database_url: str | None) -> tuple[str | None, bool]:
    """Second element is create_sync_engine()'s decode_database_name: True only for the
    build_postgres_url_from_env() fallback, which percent-encodes its database segment --
    every other source here is an already-final, operator- or caller-supplied DSN whose
    database name must be used exactly as given (eighteenth code review pass finding)."""
    if database_url is not None:
        return database_url, False

    project_database_url = os.getenv(PROJECT_DATABASE_URL_ENV)
    if project_database_url:
        return project_database_url, False

    generic_database_url = os.getenv(GENERIC_DATABASE_URL_ENV)
    if generic_database_url:
        return generic_database_url, False

    return build_postgres_url_from_env(), True
