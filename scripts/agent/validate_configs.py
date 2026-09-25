#!/usr/bin/env python3
import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import uuid
from collections.abc import Iterable, Sequence, Set
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PLATFORM_CORE_SRC = ROOT / "packages" / "backend" / "platform-core" / "src"
# ANY-32 code review finding: this is one of the modules allowed to import a product-platforms
# package (alongside apps/platform-api/bootstrap.py and apps/platform-worker/composition.py) --
# it must validate the same default bundle set those runtimes compose, or `validate-configs`
# (the required CI gate) can pass while a real product config is broken.
PLATFORM_SDK_SRC = ROOT / "packages" / "backend" / "platform-sdk" / "src"
FREELANCER_SUITE_SRC = (
    ROOT / "packages" / "backend" / "product-platforms" / "freelancer-suite" / "src"
)

SOURCE_ROOTS = (PLATFORM_CORE_SRC, PLATFORM_SDK_SRC, FREELANCER_SUITE_SRC)
for source_root in SOURCE_ROOTS:
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))

from anytoolai_freelancer_suite.bundle import FreelancerSuiteBundle  # noqa: E402
from anytoolai_platform_core.config.errors import (  # noqa: E402
    RESERVED_BUNDLE_IDS,
    ConfigError,
    RegistryLoadError,
    check_ids_are_unique,
)
from anytoolai_platform_core.config.loader import ConfigLoader  # noqa: E402
from anytoolai_platform_core.config.registry import ConfigRegistry  # noqa: E402
from anytoolai_platform_core.providers.catalog import (  # noqa: E402
    default_model_capability_overrides_path,
    load_model_capability_overrides,
)
from anytoolai_platform_sdk import ProductBundle  # noqa: E402

# Mirrors apps/platform-api/bootstrap.py's and apps/platform-worker/composition.py's identically-
# named DEFAULT_PRODUCT_BUNDLES -- all three must stay in sync (see
# tests/architecture/test_bundle_composition_parity.py).
DEFAULT_PRODUCT_BUNDLES: tuple[ProductBundle, ...] = (FreelancerSuiteBundle(),)

LIVE_PROVIDER_POLICY_REF = "default_text_generation_v1"
FAKE_PROVIDER_POLICY_REF = "default_fake_provider_v1"
CONTAINER_PRODUCTS_ROOT = Path(
    "/app/packages/backend/product-platforms/freelancer-suite/src/"
    "anytoolai_freelancer_suite/products"
)


@dataclass(frozen=True)
class ProductProfileExpectation:
    provider_policy_ref: str
    quota_policy_ref: str | None


@dataclass(frozen=True)
class DeploymentProfileManifest:
    source_products_root: str
    generated_products_root: str
    container_products_root: str
    enabled_products: dict[str, ProductProfileExpectation]
    unmetered_product_ids: tuple[str, ...]
    source_fingerprint: str
    profile_fingerprint: str


def normalized_relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def tree_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: normalized_relative_path(root, path),
    )
    for path in files:
        for part in (normalized_relative_path(root, path).encode("utf-8"), path.read_bytes()):
            digest.update(len(part).to_bytes(8, "big"))
            digest.update(part)
    return digest.hexdigest()


def check_source_fingerprint(source_root: Path, expected_fingerprint: str) -> None:
    if not source_root.is_dir():
        raise ValueError(f"source products root does not exist: {source_root}")
    if tree_fingerprint(source_root) != expected_fingerprint:
        raise ValueError("source fingerprint mismatch")


def common_products_root(roots: Sequence[Path] | None = None) -> Path:
    bundle = FreelancerSuiteBundle()
    product_roots = list(roots if roots is not None else bundle.config_roots())
    products_root = bundle._package_dir() / "products"
    if not product_roots or any(
        root.parent.resolve() != products_root.resolve() for root in product_roots
    ):
        raise ValueError("Freelancer Suite config roots must share the package products directory")
    return products_root


def action_config_ids_for_product(registry: ConfigRegistry, product_id: str) -> set[str]:
    product = registry.products[product_id]
    return {
        step.action_config_id
        for scenario_id in product.scenarios
        for step in registry.workflows[registry.scenarios[scenario_id].workflow_id].steps
    }


def _assert_product_expectations(
    registry: ConfigRegistry, expectations: dict[str, ProductProfileExpectation]
) -> None:
    for product_id, expected in expectations.items():
        product = registry.products.get(product_id)
        if product is None:
            raise ValueError(f"unknown product: {product_id}")
        if product.quota_policy_ref != expected.quota_policy_ref:
            raise ValueError(f"{product_id}: expected quota policy {expected.quota_policy_ref!r}")
        action_ids = action_config_ids_for_product(registry, product_id)
        if not action_ids:
            raise ValueError(f"{product_id}: no workflow action configs")
        for action_id in action_ids:
            actual = registry.action_configurations[action_id].provider_policy_ref
            if actual != expected.provider_policy_ref:
                raise ValueError(
                    f"{product_id}: {action_id} uses {actual}, "
                    f"expected {expected.provider_policy_ref}"
                )


def _transform_live_product(product_dir: Path, *, unmetered: bool) -> None:
    action_path = product_dir / "action_configs.yaml"
    payload = yaml.safe_load(action_path.read_text(encoding="utf-8"))
    changed = 0
    for item in payload["action_configs"]:
        if item.get("provider_policy_ref") == FAKE_PROVIDER_POLICY_REF:
            item["provider_policy_ref"] = LIVE_PROVIDER_POLICY_REF
            changed += 1
    if changed == 0:
        raise ValueError(f"{product_dir.name}: no action config uses {FAKE_PROVIDER_POLICY_REF}")
    if any(
        item.get("provider_policy_ref") == FAKE_PROVIDER_POLICY_REF
        for item in payload["action_configs"]
    ):
        raise ValueError(f"{product_dir.name}: fake provider policy remains after transform")
    action_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    if unmetered:
        product_path = product_dir / "product.yaml"
        product = yaml.safe_load(product_path.read_text(encoding="utf-8"))
        product.pop("quota_policy_ref", None)
        product_path.write_text(yaml.safe_dump(product, sort_keys=False), encoding="utf-8")
        (product_dir / "quotas.yaml").write_text("quota_policies: []\n", encoding="utf-8")


def build_deployment_profile(
    output_dir: Path,
    enabled_product_ids: Sequence[str],
    unmetered_product_ids: Set[str],
) -> DeploymentProfileManifest:
    if not enabled_product_ids:
        raise ValueError("at least one enabled product is required")
    if len(enabled_product_ids) != len(set(enabled_product_ids)):
        raise ValueError("duplicate enabled product id")
    if not unmetered_product_ids <= set(enabled_product_ids):
        raise ValueError("unmetered product ids must be a subset of enabled products")

    roots = FreelancerSuiteBundle().config_roots()
    source_root = common_products_root(roots)
    known_ids = {root.name for root in roots}
    for product_id in enabled_product_ids:
        if product_id not in known_ids:
            raise ValueError(f"unknown product: {product_id}")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_dir.parent) as temporary:
        temporary_root = Path(temporary)
        staged = temporary_root / "profile"
        staged_products = staged / "products"
        shutil.copytree(source_root, staged_products)
        expectations: dict[str, ProductProfileExpectation] = {}
        for product_id in enabled_product_ids:
            product_dir = staged_products / product_id
            _transform_live_product(product_dir, unmetered=product_id in unmetered_product_ids)
            source_product = yaml.safe_load(
                (source_root / product_id / "product.yaml").read_text(encoding="utf-8")
            )
            expectations[product_id] = ProductProfileExpectation(
                LIVE_PROVIDER_POLICY_REF,
                None
                if product_id in unmetered_product_ids
                else source_product.get("quota_policy_ref"),
            )

        generated_roots = [staged_products / root.name for root in roots]
        registry = ConfigLoader(
            ROOT / "configs" / "kernel", extra_product_roots=generated_roots
        ).load()
        _assert_product_expectations(registry, expectations)
        manifest = DeploymentProfileManifest(
            source_products_root=str(source_root.resolve()),
            generated_products_root=str((output_dir / "products").resolve()),
            container_products_root=CONTAINER_PRODUCTS_ROOT.as_posix(),
            enabled_products=expectations,
            unmetered_product_ids=tuple(sorted(unmetered_product_ids)),
            source_fingerprint=tree_fingerprint(source_root),
            profile_fingerprint=tree_fingerprint(staged_products),
        )
        (staged / "manifest.json").write_text(
            json.dumps(asdict(manifest), sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        if output_dir.exists():
            previous = output_dir.parent / f"{output_dir.name}.previous-{uuid.uuid4().hex}"
            output_dir.rename(previous)
            try:
                staged.rename(output_dir)
            except OSError:
                previous.rename(output_dir)
                raise
        else:
            staged.rename(output_dir)
        return manifest


def check_deployment_profile(
    products_root: Path,
    expected_fingerprint: str,
    expectations: dict[str, ProductProfileExpectation],
) -> None:
    roots = FreelancerSuiteBundle().config_roots()
    resolved_root = common_products_root(roots)
    if resolved_root.resolve() != products_root.resolve():
        raise ValueError(
            f"resolved bundle products root {resolved_root} does not match {products_root}"
        )
    if not products_root.is_dir():
        raise ValueError(f"products root does not exist: {products_root}")
    actual_fingerprint = tree_fingerprint(products_root)
    if actual_fingerprint != expected_fingerprint:
        raise ValueError(
            f"profile fingerprint mismatch: expected {expected_fingerprint}, "
            f"got {actual_fingerprint}"
        )
    registry = ConfigLoader(ROOT / "configs" / "kernel", extra_product_roots=roots).load()
    _assert_product_expectations(registry, expectations)


def _parse_expectations(values: Sequence[str]) -> dict[str, ProductProfileExpectation]:
    expectations: dict[str, ProductProfileExpectation] = {}
    for value in values:
        if "=" not in value or "," not in value:
            raise ValueError(f"invalid expected product: {value}")
        product_id, references = value.split("=", 1)
        provider_ref, quota_ref = references.split(",", 1)
        if not product_id or not provider_ref or not quota_ref or product_id in expectations:
            raise ValueError(f"invalid or duplicate expected product: {value}")
        expectations[product_id] = ProductProfileExpectation(
            provider_ref, None if quota_ref == "-" else quota_ref
        )
    if not expectations:
        raise ValueError("at least one expected product is required")
    return expectations


def load_registry(bundles: Iterable[ProductBundle] | None = None) -> ConfigRegistry:
    """Split out from main() so a test can inspect the loaded registry directly (e.g. assert a
    fixture bundle's product actually landed in it) instead of only observing main()'s exit
    code. `bundles=None` (the CLI default) reads DEFAULT_PRODUCT_BUNDLES at call time -- a bound
    default parameter would freeze the value at import time, immune to a test's
    monkeypatch.setattr(module, "DEFAULT_PRODUCT_BUNDLES", ...)."""
    bundles = list(bundles) if bundles is not None else list(DEFAULT_PRODUCT_BUNDLES)
    check_ids_are_unique(
        (bundle.bundle_id for bundle in bundles),
        reserved=RESERVED_BUNDLE_IDS,
        ref_type="bundle_id",
        context="composed bundles",
    )
    extra_product_roots = [root for bundle in bundles for root in bundle.config_roots()]
    config_root = ROOT / "configs" / "kernel"
    return ConfigLoader(config_root, extra_product_roots=extra_product_roots).load()


def main(argv: Sequence[str] = ()) -> int:
    arguments = list(argv)
    try:
        if arguments:
            parser = argparse.ArgumentParser(description="Validate canonical or deployment configs")
            commands = parser.add_subparsers(dest="command", required=True)
            build = commands.add_parser("build-deployment-profile")
            build.add_argument("--output-dir", type=Path, required=True)
            build.add_argument("--enabled-product", action="append", required=True)
            build.add_argument("--unmetered-product", action="append", default=[])
            check = commands.add_parser("check-deployment-profile")
            check.add_argument("--products-root", type=Path, required=True)
            check.add_argument("--expected-fingerprint", required=True)
            check.add_argument("--expect-product", action="append", required=True)
            source_check = commands.add_parser("check-source-fingerprint")
            source_check.add_argument("--products-root", type=Path, required=True)
            source_check.add_argument("--expected-fingerprint", required=True)
            try:
                parsed = parser.parse_args(arguments)
            except SystemExit as error:
                return int(error.code)
            if parsed.command == "build-deployment-profile":
                manifest = build_deployment_profile(
                    parsed.output_dir,
                    parsed.enabled_product,
                    set(parsed.unmetered_product),
                )
                print(f"Deployment profile built: {manifest.profile_fingerprint}")
            elif parsed.command == "check-deployment-profile":
                check_deployment_profile(
                    parsed.products_root,
                    parsed.expected_fingerprint,
                    _parse_expectations(parsed.expect_product),
                )
                print(f"Deployment profile verified: {parsed.expected_fingerprint}")
            else:
                check_source_fingerprint(parsed.products_root, parsed.expected_fingerprint)
                print("Canonical source fingerprint verified")
            return 0
        load_registry()
        load_model_capability_overrides(default_model_capability_overrides_path())
    except (RegistryLoadError, ConfigError, ValueError, OSError, yaml.YAMLError) as error:
        print(str(error), file=sys.stderr)
        return 1

    print("Config validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
