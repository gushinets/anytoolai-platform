#!/usr/bin/env python3
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PLATFORM_CORE_SRC = ROOT / "packages" / "backend" / "platform-core" / "src"
# ANY-32 code review finding: this is one of the modules allowed to import a product-platforms
# package (alongside apps/platform-api/bootstrap.py and apps/platform-worker/composition.py) --
# it must validate the same default bundle set those runtimes compose, or `validate-configs`
# (the required CI gate) can pass while a real product config is broken.
PLATFORM_SDK_SRC = ROOT / "packages" / "backend" / "platform-sdk" / "src"
PLATFORM_ACTIONS_SRC = ROOT / "packages" / "backend" / "platform-actions" / "src"
FREELANCER_SUITE_SRC = (
    ROOT / "packages" / "backend" / "product-platforms" / "freelancer-suite" / "src"
)

SOURCE_ROOTS = (PLATFORM_CORE_SRC, PLATFORM_SDK_SRC, PLATFORM_ACTIONS_SRC, FREELANCER_SUITE_SRC)
for source_root in SOURCE_ROOTS:
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))

from anytoolai_freelancer_suite.bundle import FreelancerSuiteBundle  # noqa: E402
from anytoolai_platform_actions.bundle import PlatformActionsBundle  # noqa: E402
from anytoolai_platform_core.config.errors import (  # noqa: E402
    ConfigError,
    RegistryLoadError,
    check_ids_are_unique,
)
from anytoolai_platform_core.config.loader import ConfigLoader  # noqa: E402
from anytoolai_platform_core.config.registry import ConfigRegistry  # noqa: E402
from anytoolai_platform_sdk import ProductBundle  # noqa: E402

# Mirrors apps/platform-api/bootstrap.py's and apps/platform-worker/composition.py's identically-
# named DEFAULT_PRODUCT_BUNDLES -- all three must stay in sync (see
# tests/architecture/test_bundle_composition_parity.py).
DEFAULT_PRODUCT_BUNDLES: tuple[ProductBundle, ...] = (FreelancerSuiteBundle(),)

# Contract A (ANY-32 code review finding): mirrors bootstrap.py's/composition.py's identically-
# named RESERVED_BUNDLE_IDS -- platform_actions/kernel_demo are globally reserved bundle IDs, not
# just an apps/platform-api `loaded_bundles`-reporting constraint.
RESERVED_BUNDLE_IDS: tuple[str, ...] = (PlatformActionsBundle.bundle_id, "kernel_demo")


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


def main() -> int:
    try:
        load_registry()
    except RegistryLoadError as error:
        print(str(error), file=sys.stderr)
        return 1
    except ConfigError as error:
        print(str(error), file=sys.stderr)
        return 1

    print("Config validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
