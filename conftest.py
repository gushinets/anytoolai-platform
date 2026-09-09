from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent


def _iter_src_roots() -> list[Path]:
    roots: list[Path] = []
    backend = REPO_ROOT / "packages" / "backend"
    # product-platforms/* (e.g. freelancer-suite) packages nest one level deeper than every
    # other apps/*/packages/backend/* package -- without walking it too, a package there is
    # silently invisible to any bare (non-editable-installed) pytest run relying on this
    # conftest's sys.path setup, even though apps/platform-api/bootstrap.py and friends import it
    # (ANY-32 code review finding, caught by a real CI failure in a subprocess that inherits this
    # same sys.path pattern via test_worker_lease_recovery_postgresql.py's _src_roots() mirror).
    for base in (REPO_ROOT / "apps", backend, backend / "product-platforms"):
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
