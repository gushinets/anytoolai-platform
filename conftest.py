from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent


def _iter_src_roots() -> list[Path]:
    roots: list[Path] = []

    for base in (REPO_ROOT / "apps", REPO_ROOT / "packages" / "backend"):
        if not base.exists():
            continue
        for child in sorted(base.iterdir()):
            src_dir = child / "src"
            if src_dir.is_dir():
                roots.append(src_dir)

    return roots


for src_root in reversed(_iter_src_roots()):
    src_root_str = str(src_root)
    if src_root_str not in sys.path:
        sys.path.insert(0, src_root_str)

# Shared test-only helpers (e.g. tests/support/sqlite_harness.py) used across
# packages/backend/*/tests and apps/*/tests, which otherwise have no way to import
# from each other's test trees.
TEST_SUPPORT_ROOT = str(REPO_ROOT / "tests" / "support")
if TEST_SUPPORT_ROOT not in sys.path:
    sys.path.insert(0, TEST_SUPPORT_ROOT)
