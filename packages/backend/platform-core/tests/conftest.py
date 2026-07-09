from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[4]
PLATFORM_CORE_SRC = REPO_ROOT / "packages" / "backend" / "platform-core" / "src"

if str(PLATFORM_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(PLATFORM_CORE_SRC))
