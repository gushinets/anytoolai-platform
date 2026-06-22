"""Composition root for platform runtime and future product bundles."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.storage.db import create_sync_engine
from anytoolai_platform_core.storage.transactions import build_session_factory

DATABASE_URL_ENV = "ANYTOOLAI_DATABASE_URL"


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
    resolved_database_url = database_url if database_url is not None else os.getenv(DATABASE_URL_ENV)
    if not resolved_database_url:
        return RuntimeStorageDependencies()

    engine = create_sync_engine(resolved_database_url)
    return RuntimeStorageDependencies(session_factory=build_session_factory(engine))
