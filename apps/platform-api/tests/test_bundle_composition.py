"""ANY-32 (B01) required-evidence coverage for the bundle composition loader.

Every case here goes through the real application composition path
(anytoolai_platform_api.bootstrap.build_runtime), the same one apps/platform-api's production
FastAPI app uses -- not a hand-rolled ConfigLoader call -- so a passing test here is direct
evidence the composition boundary (platform-sdk's ProductBundle contract, platform-core's
Path-only ConfigLoader extension point, and the composition root in bootstrap.py) actually works
end to end.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PLATFORM_CORE_SRC = REPO_ROOT / "packages" / "backend" / "platform-core" / "src"
PLATFORM_SDK_SRC = REPO_ROOT / "packages" / "backend" / "platform-sdk" / "src"
PLATFORM_API_SRC = REPO_ROOT / "apps" / "platform-api" / "src"

for src_path in (PLATFORM_CORE_SRC, PLATFORM_SDK_SRC, PLATFORM_API_SRC):
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

from anytoolai_platform_api import bootstrap
from anytoolai_platform_core.config.errors import RegistryLoadError
from anytoolai_platform_sdk import ProductBundle

CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
FIXTURE_PRODUCT_DIR = Path(__file__).resolve().parent / "fixtures" / "fixture_product"


class FixtureProductBundle(ProductBundle):
    """Test-only ProductBundle proving the composition loader path. Never imported by production
    code -- apps/platform-api/bootstrap.py's default wiring only ever constructs
    FreelancerSuiteBundle. `_package_dir()` (inherited from ProductBundle) resolves relative to
    *this file*, so config_roots() stays correct regardless of the caller's working directory --
    see test_bundle_root_resolution_is_independent_of_the_working_directory below.

    `root` is an optional explicit override (e.g. a tmp_path copy the invalid-cross-reference
    case below mutates per-test) that bypasses `_package_dir()`-relative resolution entirely.
    `bundle_id` is likewise overridable per-instance -- used by the reserved-bundle-id collision
    test below, which needs a bundle whose bundle_id equals a reserved kernel-level label."""

    bundle_id = "fixture_bundle"

    def __init__(
        self,
        product_dir_name: str = "fixture_product",
        *,
        root: Path | None = None,
        bundle_id: str | None = None,
    ) -> None:
        self._product_dir_name = product_dir_name
        self._root = root
        if bundle_id is not None:
            self.bundle_id = bundle_id

    def config_roots(self) -> list[Path]:
        if self._root is not None:
            return [self._root]
        return [self._package_dir() / "fixtures" / self._product_dir_name]


def test_fixture_bundle_loads_through_real_composition_into_the_shared_registry() -> None:
    result = bootstrap.build_runtime(config_root=CONFIG_ROOT, bundles=[FixtureProductBundle()])

    assert "fixture_bundle" in result.loaded_bundles
    assert "fixture_product" in result.config_registry.products
    # Loaded into the same validated registry as kernel configuration -- kernel_demo (from
    # configs/kernel/products/kernel_demo, config_root's own products dir) is present alongside
    # the bundle-contributed fixture product.
    assert "kernel_demo" in result.config_registry.products
    assert "fixture_product.single_action_v1" in result.config_registry.workflows


def test_production_default_excludes_the_fixture_bundle() -> None:
    result = bootstrap.build_runtime(config_root=CONFIG_ROOT)

    assert "fixture_bundle" not in result.loaded_bundles
    assert "fixture_product" not in result.config_registry.products
    # ANY-32: production default is FreelancerSuiteBundle with zero product roots.
    assert "freelancer_suite" in result.loaded_bundles


def test_bundle_root_resolution_is_independent_of_the_working_directory(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    result = bootstrap.build_runtime(config_root=CONFIG_ROOT, bundles=[FixtureProductBundle()])

    assert "fixture_product" in result.config_registry.products


def test_missing_bundle_root_fails_startup() -> None:
    with pytest.raises(RegistryLoadError):
        bootstrap.build_runtime(
            config_root=CONFIG_ROOT,
            bundles=[FixtureProductBundle("does_not_exist")],
        )


@pytest.mark.parametrize("duplicate_first", [False, True], ids=["fixture_product_first", "fixture_product_duplicate_first"])
def test_duplicate_product_id_across_bundles_fails_regardless_of_order(
    tmp_path: Path,
    duplicate_first: bool,
) -> None:
    # A second bundle root with the same product id as fixture_product, but its own directory --
    # a tmp copy (not a second checked-in fixture) since only the duplicate product id matters,
    # not distinct content.
    duplicate_product_dir = tmp_path / "fixture_product_duplicate"
    shutil.copytree(FIXTURE_PRODUCT_DIR, duplicate_product_dir)

    bundle_a = FixtureProductBundle("fixture_product", bundle_id="fixture_bundle_a")
    bundle_b = FixtureProductBundle(root=duplicate_product_dir, bundle_id="fixture_bundle_b")
    bundles = [bundle_b, bundle_a] if duplicate_first else [bundle_a, bundle_b]

    with pytest.raises(RegistryLoadError) as exc_info:
        bootstrap.build_runtime(config_root=CONFIG_ROOT, bundles=bundles)

    codes = {error.code for error in exc_info.value.errors}
    assert "config_duplicate_id" in codes


def test_invalid_cross_reference_in_a_bundle_product_fails_startup(tmp_path: Path) -> None:
    broken_product_dir = tmp_path / "broken_fixture_product"
    shutil.copytree(FIXTURE_PRODUCT_DIR, broken_product_dir)

    scenarios_path = broken_product_dir / "scenarios.yaml"
    data = yaml.safe_load(scenarios_path.read_text(encoding="utf-8"))
    data["scenarios"][0]["workflow_id"] = "fixture_product.does_not_exist"
    scenarios_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    with pytest.raises(RegistryLoadError) as exc_info:
        bootstrap.build_runtime(
            config_root=CONFIG_ROOT,
            bundles=[FixtureProductBundle(root=broken_product_dir)],
        )

    codes = {error.code for error in exc_info.value.errors}
    assert "config_broken_reference" in codes


def test_duplicate_bundle_id_across_bundles_fails_startup(tmp_path: Path) -> None:
    # Both FixtureProductBundle instances share the class-level bundle_id "fixture_bundle" but
    # point at distinct, individually-valid product roots -- proving the failure is specifically
    # the bundle_id collision check, not a coincidental duplicate product_id. The second root is a
    # tmp copy of fixture_product (only needs to be a distinct, valid directory).
    other_product_dir = tmp_path / "fixture_product_other"
    shutil.copytree(FIXTURE_PRODUCT_DIR, other_product_dir)

    with pytest.raises(RegistryLoadError) as exc_info:
        bootstrap.build_runtime(
            config_root=CONFIG_ROOT,
            bundles=[
                FixtureProductBundle("fixture_product"),
                FixtureProductBundle(root=other_product_dir),
            ],
        )

    codes = {error.code for error in exc_info.value.errors}
    assert "config_duplicate_bundle_id" in codes


@pytest.mark.parametrize("reserved_bundle_id", ["platform_actions", "kernel_demo"])
def test_bundle_id_colliding_with_a_reserved_kernel_label_fails_startup(
    reserved_bundle_id: str,
) -> None:
    with pytest.raises(RegistryLoadError) as exc_info:
        bootstrap.build_runtime(
            config_root=CONFIG_ROOT,
            bundles=[FixtureProductBundle(bundle_id=reserved_bundle_id)],
        )

    codes = {error.code for error in exc_info.value.errors}
    assert "config_duplicate_bundle_id" in codes
