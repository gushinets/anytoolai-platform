#!/usr/bin/env python3
from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

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


def products_missing_a_quota_policy(registry: ConfigRegistry) -> list[str]:
    """Repo-wide invariant (ANY-414): `quotas/service.py`'s `validate_accepted_start()` silently
    treats a product with no `quota_policy_ref` as "quota does not apply", so guest usage of that
    product's LLM actions is then completely unmetered -- easy to do by simply forgetting a
    `quotas.yaml`. Every product in the default bundle set must therefore declare one; a
    genuinely free/unlimited product must say so through an explicit exemption added to this
    function (none exists today), not by silently omitting `quota_policy_ref`. Client Update
    Writer's own quota (3 runs, lifetime, product-wide) is a product decision recorded in
    docs/exec-plans/active/any-414-*.md, not something this check derives.
    """
    return sorted(
        product_id
        for product_id, product in registry.products.items()
        if not product.quota_policy_ref
    )


def main() -> int:
    try:
        registry = load_registry()
        load_model_capability_overrides(default_model_capability_overrides_path())
    except RegistryLoadError as error:
        print(str(error), file=sys.stderr)
        return 1
    except ConfigError as error:
        print(str(error), file=sys.stderr)
        return 1
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    missing_quota_policy = products_missing_a_quota_policy(registry)
    if missing_quota_policy:
        print(
            "Config validation failed: product(s) with no quota_policy_ref (quota enforcement is "
            "silently skipped for these): " + ", ".join(missing_quota_policy),
            file=sys.stderr,
        )
        return 1

    print("Config validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
