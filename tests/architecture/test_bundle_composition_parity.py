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

from anytoolai_platform_api import bootstrap  # noqa: E402
from anytoolai_platform_worker import composition as worker_composition  # noqa: E402


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
