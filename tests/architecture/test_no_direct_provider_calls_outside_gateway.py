from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP_PATH_PARTS = {
    ".venv",
    ".quick-check-venv",
    ".quick-check-tmp",
    ".uv-cache",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "site-packages",
    "node_modules",
    ".pnpm-store",
    ".next",
    "dist",
    "build",
    "coverage",
}
ALLOWED_ADAPTER_MODULE_ROOT = (
    ROOT
    / "packages"
    / "backend"
    / "platform-core"
    / "src"
    / "anytoolai_platform_core"
    / "providers"
    / "adapters"
)
ALLOWED_PROVIDER_MODULE_ROOT = (
    ROOT
    / "packages"
    / "backend"
    / "platform-core"
    / "src"
    / "anytoolai_platform_core"
    / "providers"
)
ALLOWED_PYDANTIC_AI_MODULE_ROOT = (
    ROOT
    / "packages"
    / "backend"
    / "platform-actions"
    / "src"
    / "anytoolai_platform_actions"
    / "structured_llm"
)
FORBIDDEN_ADAPTER_IMPORT_PREFIX = "anytoolai_platform_core.providers.adapters"
FORBIDDEN_PROVIDER_IMPORT_PARENT = "anytoolai_platform_core.providers"
ALLOWED_GATEWAY_MODULE = (
    ROOT
    / "packages"
    / "backend"
    / "platform-core"
    / "src"
    / "anytoolai_platform_core"
    / "providers"
    / "gateway.py"
)


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
            if node.module == FORBIDDEN_PROVIDER_IMPORT_PARENT and any(
                alias.name == "adapters" for alias in node.names
            ):
                return True
    return False


def _imports_module(path: Path, module_name: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(
                alias.name == module_name or alias.name.startswith(f"{module_name}.")
                for alias in node.names
            ):
                return True
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module == module_name or node.module.startswith(f"{module_name}."):
                return True
    return False


def test_no_direct_provider_adapter_imports_outside_provider_boundary() -> None:
    offenders: list[Path] = []
    for path in _python_files():
        if path.is_relative_to(ALLOWED_ADAPTER_MODULE_ROOT):
            continue
        if path == ALLOWED_GATEWAY_MODULE:
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
        if path.is_relative_to(ALLOWED_ADAPTER_MODULE_ROOT):
            continue
        if "tests" in path.parts:
            continue
        if _imports_module(path, "openai"):
            offenders.append(path)

    assert offenders == [], "direct openai imports found outside provider adapters: " + ", ".join(
        str(path.relative_to(ROOT)) for path in offenders
    )


def test_no_direct_litellm_imports_outside_provider_adapter() -> None:
    offenders: list[Path] = []
    for path in _python_files():
        if path.is_relative_to(ALLOWED_ADAPTER_MODULE_ROOT):
            continue
        if "tests" in path.parts:
            continue
        if _imports_module(path, "litellm"):
            offenders.append(path)

    assert offenders == [], "direct litellm imports found outside provider adapters: " + ", ".join(
        str(path.relative_to(ROOT)) for path in offenders
    )


def test_no_direct_pydantic_ai_imports_outside_structured_llm_executor_boundary() -> None:
    offenders: list[Path] = []
    for path in _python_files():
        if path.is_relative_to(ALLOWED_PYDANTIC_AI_MODULE_ROOT):
            continue
        if "tests" in path.parts:
            continue
        if _imports_module(path, "pydantic_ai"):
            offenders.append(path)

    assert offenders == [], "direct pydantic_ai imports found outside structured LLM boundary: " + ", ".join(
        str(path.relative_to(ROOT)) for path in offenders
    )
