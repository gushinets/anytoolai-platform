#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

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

for source_root in (PLATFORM_CORE_SRC, PLATFORM_SDK_SRC, FREELANCER_SUITE_SRC):
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))

from anytoolai_freelancer_suite.bundle import FreelancerSuiteBundle  # noqa: E402
from anytoolai_platform_core.config.errors import (  # noqa: E402
    ConfigError,
    RegistryLoadError,
    check_ids_are_unique,
)
from anytoolai_platform_core.config.loader import ConfigLoader  # noqa: E402

# Mirrors apps/platform-api/bootstrap.py's and apps/platform-worker/composition.py's identically-
# named DEFAULT_PRODUCT_BUNDLES -- all three must stay in sync (see
# tests/architecture/test_bundle_composition_parity.py).
DEFAULT_PRODUCT_BUNDLES = (FreelancerSuiteBundle(),)


def main() -> int:
    config_root = ROOT / "configs" / "kernel"

    try:
        check_ids_are_unique(
            (bundle.bundle_id for bundle in DEFAULT_PRODUCT_BUNDLES),
            ref_type="bundle_id",
            context="composed bundles",
        )
        extra_product_roots = [
            root for bundle in DEFAULT_PRODUCT_BUNDLES for root in bundle.config_roots()
        ]
        ConfigLoader(config_root, extra_product_roots=extra_product_roots).load()
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
