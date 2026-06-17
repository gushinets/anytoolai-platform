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
