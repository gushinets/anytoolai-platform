"""ANY-32 code-review finding: apps/platform-api/bootstrap.py, apps/platform-worker/composition.py,
and scripts/agent/validate_configs.py are the only three modules allowed to compose a
product-platforms bundle, and all three must resolve the identical default bundle set -- or the
API can accept/validate a product workflow the worker's own registry never loaded (a job that
fails at execution time, not at request time). This proves the API and worker composition roots
actually land on the same product registry contents, not just that each one runs without error.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = ROOT / "configs" / "kernel"

for src_path in (
    ROOT / "packages" / "backend" / "platform-core" / "src",
    ROOT / "packages" / "backend" / "platform-sdk" / "src",
    ROOT / "packages" / "backend" / "platform-actions" / "src",
    ROOT / "packages" / "backend" / "product-platforms" / "freelancer-suite" / "src",
    ROOT / "apps" / "platform-api" / "src",
    ROOT / "apps" / "platform-worker" / "src",
):
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

import pytest  # noqa: E402
from anytoolai_platform_actions.bundle import PlatformActionsBundle  # noqa: E402
from anytoolai_platform_api import bootstrap  # noqa: E402
from anytoolai_platform_core.config.errors import RegistryLoadError  # noqa: E402
from anytoolai_platform_sdk import ProductBundle  # noqa: E402
from anytoolai_platform_worker import composition as worker_composition  # noqa: E402


class _EmptyBundle(ProductBundle):
    """Minimal test-only ProductBundle: no real product roots needed, since the duplicate-id
    check runs before config_roots() is ever resolved."""

    def __init__(self, bundle_id: str) -> None:
        self.bundle_id = bundle_id

    def config_roots(self) -> list[Path]:
        return []


FIXTURE_PRODUCT_DIR = (
    ROOT / "apps" / "platform-api" / "tests" / "fixtures" / "fixture_product"
)


class _FixtureBundle(ProductBundle):
    """Reuses apps/platform-api/tests/test_bundle_composition.py's fixture_product directory
    (product_id: fixture_product) rather than checking in a second copy -- proves a *non-empty*
    ProductBundle actually reaches the loaded registry, not just that composition runs without
    error (ANY-32 code review finding: DEFAULT_PRODUCT_BUNDLES currently contributes zero
    config_roots, so a passing composition call alone doesn't prove roots are wired through)."""

    bundle_id = "fixture_bundle"

    def config_roots(self) -> list[Path]:
        return [FIXTURE_PRODUCT_DIR]


def _load_validate_configs_module() -> Any:
    path = ROOT / "scripts" / "agent" / "validate_configs.py"
    spec = importlib.util.spec_from_file_location("validate_configs_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bundle_ids(bundles: Any) -> list[str]:
    return [bundle.bundle_id for bundle in bundles]


def test_default_product_bundles_match_across_all_three_composition_boundaries() -> None:
    """The regression this finding actually needs: DEFAULT_PRODUCT_BUNDLES is currently `()` of
    contributed config roots for every bundle (no real product exists yet), so a registry-content
    comparison alone would pass even if one composition root silently used a different or empty
    bundle set. Comparing the bundle_id sequence directly catches that today, before ANY-227 gives
    it any config-root content to diverge on."""
    validate_configs = _load_validate_configs_module()

    api_bundle_ids = _bundle_ids(bootstrap.DEFAULT_PRODUCT_BUNDLES)
    worker_bundle_ids = _bundle_ids(worker_composition.DEFAULT_PRODUCT_BUNDLES)
    validate_configs_bundle_ids = _bundle_ids(validate_configs.DEFAULT_PRODUCT_BUNDLES)

    assert api_bundle_ids == worker_bundle_ids == validate_configs_bundle_ids
    assert api_bundle_ids, "expected at least the production FreelancerSuiteBundle default"


def test_reserved_bundle_ids_are_shared_not_duplicated_across_composition_boundaries() -> None:
    """Contract A (ANY-32 code review finding): a first fix gave each composition boundary its
    own independently-defined-but-tested-equal RESERVED_BUNDLE_IDS -- rejected as not actually
    "shared/reused from a single product-neutral composition contract boundary". All three now
    import the identical object from platform-core's config.errors, so this asserts identity
    (`is`), not just equal value -- a real regression (e.g. one module re-defining its own copy)
    would break `is` even if the value still matched by coincidence."""
    validate_configs = _load_validate_configs_module()

    assert bootstrap.RESERVED_BUNDLE_IDS is worker_composition.RESERVED_BUNDLE_IDS
    # validate_configs.py is loaded via importlib as a separate module object (see
    # _load_validate_configs_module), so its RESERVED_BUNDLE_IDS is a distinct import of the same
    # underlying platform-core tuple -- equal by value, not necessarily by identity.
    assert bootstrap.RESERVED_BUNDLE_IDS == validate_configs.RESERVED_BUNDLE_IDS
    assert bootstrap.RESERVED_BUNDLE_IDS == ("platform_actions", "kernel_demo")


def test_reserved_bundle_ids_do_not_drift_from_platform_actions_bundle_id() -> None:
    """platform-core's RESERVED_BUNDLE_IDS hardcodes "platform_actions" as a plain string literal
    rather than importing PlatformActionsBundle (platform-actions depends on platform-core, so
    the reverse import would be circular). This is the drift check that makes that safe: if
    PlatformActionsBundle.bundle_id is ever renamed, this test (which can import both) catches
    the mismatch immediately."""
    assert PlatformActionsBundle.bundle_id in bootstrap.RESERVED_BUNDLE_IDS


def _capture_registry(monkeypatch: Any, module: Any) -> list[Any]:
    real_build_config_registry = module.build_config_registry
    captured: list[Any] = []

    def spy(*args: Any, **kwargs: Any) -> Any:
        registry = real_build_config_registry(*args, **kwargs)
        captured.append(registry)
        return registry

    monkeypatch.setattr(module, "build_config_registry", spy)
    return captured


def test_api_and_worker_compose_the_same_default_product_registry(monkeypatch: Any) -> None:
    api_registries = _capture_registry(monkeypatch, bootstrap)
    worker_registries = _capture_registry(monkeypatch, worker_composition)

    bootstrap.build_runtime(config_root=CONFIG_ROOT)

    engine = sa.create_engine("sqlite://")
    worker_composition.build_worker(
        session_factory=sessionmaker(bind=engine), config_root=CONFIG_ROOT
    )

    assert len(api_registries) == 1
    assert len(worker_registries) == 1
    assert dict(api_registries[0].products) == dict(worker_registries[0].products)
    assert dict(api_registries[0].workflows) == dict(worker_registries[0].workflows)


def test_duplicate_bundle_id_fails_consistently_across_all_three_composition_boundaries(
    monkeypatch: Any,
) -> None:
    """ANY-32 code-review finding: only apps/platform-api/bootstrap.py rejected a duplicate
    composed bundle_id -- apps/platform-worker/composition.py and
    scripts/agent/validate_configs.py silently accepted one. All three now share platform-core's
    check_ids_are_unique(); this proves all three actually reject the same duplicate."""
    dup_bundles = [_EmptyBundle("dup"), _EmptyBundle("dup")]

    with pytest.raises(RegistryLoadError) as api_excinfo:
        bootstrap.build_runtime(config_root=CONFIG_ROOT, bundles=dup_bundles)
    assert "config_duplicate_bundle_id" in [error.code for error in api_excinfo.value.errors]

    engine = sa.create_engine("sqlite://")
    with pytest.raises(RegistryLoadError) as worker_excinfo:
        worker_composition.build_worker(
            session_factory=sessionmaker(bind=engine),
            config_root=CONFIG_ROOT,
            bundles=dup_bundles,
        )
    assert "config_duplicate_bundle_id" in [error.code for error in worker_excinfo.value.errors]

    validate_configs = _load_validate_configs_module()
    monkeypatch.setattr(validate_configs, "DEFAULT_PRODUCT_BUNDLES", dup_bundles)
    assert validate_configs.main() == 1


def test_reserved_bundle_id_collision_fails_consistently_across_all_three_composition_boundaries(
    monkeypatch: Any,
) -> None:
    """Contract A (ANY-32 code review finding): a composed bundle_id colliding with a reserved
    kernel-level label ("platform_actions"/"kernel_demo") was only rejected by
    apps/platform-api/bootstrap.py. All three now share the same RESERVED_BUNDLE_IDS."""
    colliding_bundles = [_EmptyBundle("platform_actions")]

    with pytest.raises(RegistryLoadError) as api_excinfo:
        bootstrap.build_runtime(config_root=CONFIG_ROOT, bundles=colliding_bundles)
    assert "config_duplicate_bundle_id" in [error.code for error in api_excinfo.value.errors]

    engine = sa.create_engine("sqlite://")
    with pytest.raises(RegistryLoadError) as worker_excinfo:
        worker_composition.build_worker(
            session_factory=sessionmaker(bind=engine),
            config_root=CONFIG_ROOT,
            bundles=colliding_bundles,
        )
    assert "config_duplicate_bundle_id" in [error.code for error in worker_excinfo.value.errors]

    validate_configs = _load_validate_configs_module()
    monkeypatch.setattr(validate_configs, "DEFAULT_PRODUCT_BUNDLES", colliding_bundles)
    assert validate_configs.main() == 1


def test_non_empty_bundle_actually_lands_in_worker_and_validate_configs_registries(
    monkeypatch: Any,
) -> None:
    """ANY-32 code-review finding: DEFAULT_PRODUCT_BUNDLES currently contributes zero
    config_roots for every bundle, so composition running without error doesn't prove a real
    product actually reaches the loaded registry. Runs a non-empty fixture bundle through
    build_worker() and validate_configs.load_registry() and asserts fixture_product is present."""
    worker_registries = _capture_registry(monkeypatch, worker_composition)
    engine = sa.create_engine("sqlite://")
    worker_composition.build_worker(
        session_factory=sessionmaker(bind=engine),
        config_root=CONFIG_ROOT,
        bundles=[_FixtureBundle()],
    )
    assert len(worker_registries) == 1
    assert "fixture_product" in worker_registries[0].products

    validate_configs = _load_validate_configs_module()
    registry = validate_configs.load_registry(bundles=[_FixtureBundle()])
    assert "fixture_product" in registry.products
