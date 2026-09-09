"""Composition root for the platform runtime and its product bundles.

Alongside apps/platform-worker/composition.py and scripts/agent/validate_configs.py, this is one
of the only modules allowed to import a product-platforms package (see
docs/architecture/platform-boundaries.md and tests/architecture's freelancer-suite import-
boundary proof). Platform Core and Platform Actions stay bundle-ignorant; this module explicitly
resolves each bundle's config_roots() and passes them through platform-core's product-neutral
ConfigLoader extension point."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anytoolai_freelancer_suite.bundle import FreelancerSuiteBundle
from anytoolai_platform_actions.bundle import PlatformActionsBundle
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.config.errors import RESERVED_BUNDLE_IDS, check_ids_are_unique
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.storage.db import build_postgres_url_from_env, create_sync_engine
from anytoolai_platform_core.storage.transactions import build_session_factory
from anytoolai_platform_sdk import ProductBundle

PROJECT_DATABASE_URL_ENV = "ANYTOOLAI_DATABASE_URL"
GENERIC_DATABASE_URL_ENV = "DATABASE_URL"

# Named (not inline) so apps/platform-worker/composition.py and scripts/agent/validate_configs.py
# -- the only other modules allowed to import a product-platforms package (ANY-32 code review
# finding) -- can be tested against the exact same default bundle set this composition root uses.
DEFAULT_PRODUCT_BUNDLES: tuple[ProductBundle, ...] = (FreelancerSuiteBundle(),)


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
    bundles: Sequence[ProductBundle] | None = None,
) -> RuntimeBootstrapResult:
    """Compose the platform kernel with `bundles` (defaulting in production to
    `[FreelancerSuiteBundle()]`, which contributes ProposalAI (ANY-227) as its first product
    root). `loaded_bundles` reports what was actually composed: the two
    kernel-level labels plus each bundle's own `bundle_id`, in the order given -- not a fabricated
    literal. A caller that passes `bundles` explicitly (e.g. a test-only fixture bundle) fully
    replaces the production default; it is never combined with it."""
    resolved_bundles = list(bundles) if bundles is not None else list(DEFAULT_PRODUCT_BUNDLES)
    check_ids_are_unique(
        (bundle.bundle_id for bundle in resolved_bundles),
        reserved=RESERVED_BUNDLE_IDS,
        ref_type="bundle_id",
        context="composed bundles",
    )
    extra_product_roots = [
        root for bundle in resolved_bundles for root in bundle.config_roots()
    ]
    config_registry = build_config_registry(config_root, extra_product_roots=extra_product_roots)
    return RuntimeBootstrapResult(
        loaded_bundles=[
            PlatformActionsBundle.bundle_id,
            "kernel_demo",
            *(bundle.bundle_id for bundle in resolved_bundles),
        ],
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
