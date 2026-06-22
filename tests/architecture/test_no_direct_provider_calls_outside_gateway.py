from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP_PATH_PARTS = {".venv", ".quick-check-venv", "scripts"}
ALLOWED_ADAPTER_IMPORT_ROOT = (
    ROOT
    / "packages"
    / "backend"
    / "platform-core"
    / "src"
    / "anytoolai_platform_core"
    / "providers"
)
FORBIDDEN_ADAPTER_IMPORT_PREFIX = "anytoolai_platform_core.providers.adapters"


def _python_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*.py")
        if not any(part in SKIP_PATH_PARTS for part in path.parts)
    ]


def _imports_provider_adapter(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(
                alias.name == FORBIDDEN_ADAPTER_IMPORT_PREFIX
                or alias.name.startswith(f"{FORBIDDEN_ADAPTER_IMPORT_PREFIX}.")
                for alias in node.names
            ):
                return True
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module == FORBIDDEN_ADAPTER_IMPORT_PREFIX or node.module.startswith(
                f"{FORBIDDEN_ADAPTER_IMPORT_PREFIX}."
            ):
                return True
    return False


def test_no_direct_provider_adapter_imports_outside_provider_boundary() -> None:
    offenders: list[Path] = []
    for path in _python_files():
        if path.is_relative_to(ALLOWED_ADAPTER_IMPORT_ROOT):
            continue
        if "tests" in path.parts:
            continue
        if _imports_provider_adapter(path):
            offenders.append(path)

    assert offenders == [], "direct provider adapter imports found outside provider boundary: " + ", ".join(
        str(path.relative_to(ROOT)) for path in offenders
    )


def test_no_direct_openai_imports_outside_provider_adapter() -> None:
    offenders: list[Path] = []
    for path in _python_files():
        if path.is_relative_to(ALLOWED_ADAPTER_IMPORT_ROOT):
            continue
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "import openai" in text or "from openai" in text:
            offenders.append(path)

    assert offenders == [], "direct openai imports found outside provider adapters: " + ", ".join(
        str(path.relative_to(ROOT)) for path in offenders
    )
