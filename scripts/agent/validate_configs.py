#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PLATFORM_CORE_SRC = ROOT / "packages" / "backend" / "platform-core" / "src"

if str(PLATFORM_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(PLATFORM_CORE_SRC))

from anytoolai_platform_core.config.errors import ConfigError, RegistryLoadError
from anytoolai_platform_core.config.loader import ConfigLoader


def main() -> int:
    config_root = ROOT / "configs" / "kernel"

    try:
        ConfigLoader(config_root).load()
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
