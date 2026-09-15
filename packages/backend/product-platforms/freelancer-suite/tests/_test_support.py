"""Shared by test_proposal_ai_product.py and test_client_update_writer_product.py (ANY-414 code
review finding: `_load_validate_architecture_module()`, the forbidden-provider-terms tuple, and
`_load_yaml()` were each duplicated verbatim across the two).

Not a `conftest.py`: this directory has no `__init__.py` (ATAI007/ATAI008 forbid product-platforms
code, tests included, from being a package that could import `anytoolai_platform_core`), and a
combined multi-directory `pytest` run (as `full-check`/`quick-check` do) loads a same-named
`conftest.py` from several directories at once -- a bare `from conftest import ...` in a test file
risks resolving to a *different* directory's cached module. Callers load this file the same way
both already loaded `validate_architecture.py`: by explicit path via `importlib`, which never
touches `sys.modules` and so never collides with anything.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[5]


def load_validate_architecture_module() -> Any:
    """`validate_architecture.py` is pure stdlib (no `anytoolai_platform_core` import chain), so
    loading it stays within ATAI007/ATAI008's ban on product-platforms code depending on
    platform-core internals."""
    path = REPO_ROOT / "scripts" / "agent" / "validate_architecture.py"
    spec = importlib.util.spec_from_file_location("validate_architecture_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Provider-SDK names come from validate_architecture.py's own LLM_PROVIDER_IMPORTS -- the single
# source of truth ATAI006 already enforces repo-wide -- rather than a second, hand-maintained copy
# that could silently drift from it. Model-string prefixes are a distinct concern (raw text, not
# an import name) with no central list to reuse.
FORBIDDEN_PROVIDER_TERMS: tuple[str, ...] = tuple(
    load_validate_architecture_module().LLM_PROVIDER_IMPORTS
) + ("gpt-", "claude-", "gemini-")


def load_yaml(product_dir: Path, relative_path: str) -> dict[str, Any]:
    return yaml.safe_load((product_dir / relative_path).read_text(encoding="utf-8"))
