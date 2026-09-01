from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP_PATH_PARTS = {
    ".git",
    ".venv",
    ".quick-check-venv",
    ".quick-check-tmp",
    ".tmp",
    ".uv-cache",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tmp",
    "__pycache__",
    "site-packages",
    "node_modules",
    ".pnpm-store",
    ".next",
    "dist",
    "build",
    "coverage",
    "tmp",
    "uv-cache",
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
ALLOWED_GATEWAY_MODULE_ROOT = (
    ROOT
    / "packages"
    / "backend"
    / "platform-core"
    / "src"
    / "anytoolai_platform_core"
    / "providers"
    / "gateway"
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
    # For a dotted `module_name` (e.g. "google.genai"), the canonical import form for that SDK is
    # often `from google import genai`, not `import google.genai` — a parent-module-plus-child-name
    # import that resolves to the exact same object but doesn't literally contain "google.genai"
    # anywhere in its own AST. Mirrors the same parent+child pattern `_imports_provider_adapter`
    # already handles for its own "adapters" case above.
    parent, _, child = module_name.rpartition(".")
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
            if parent and node.module == parent and any(alias.name == child for alias in node.names):
                return True
    return False


def test_no_direct_provider_adapter_imports_outside_provider_boundary() -> None:
    offenders: list[Path] = []
    for path in _python_files():
        if path.is_relative_to(ALLOWED_ADAPTER_MODULE_ROOT):
            continue
        if path.is_relative_to(ALLOWED_GATEWAY_MODULE_ROOT):
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


# CLAUDE.md/llm-runtime.md forbid these provider SDKs outside the adapter boundary the same way
# openai/litellm already are above — the module name each package exposes at import time.
_OTHER_FORBIDDEN_PROVIDER_MODULES = ["anthropic", "google.genai", "cohere", "mistralai"]


def _assert_no_direct_module_imports_outside_adapter(module_name: str) -> None:
    offenders: list[Path] = []
    for path in _python_files():
        if path.is_relative_to(ALLOWED_ADAPTER_MODULE_ROOT):
            continue
        if "tests" in path.parts:
            continue
        if _imports_module(path, module_name):
            offenders.append(path)

    assert offenders == [], f"direct {module_name} imports found outside provider adapters: " + ", ".join(
        str(path.relative_to(ROOT)) for path in offenders
    )


def test_no_direct_anthropic_imports_outside_provider_adapter() -> None:
    _assert_no_direct_module_imports_outside_adapter("anthropic")


def test_no_direct_google_genai_imports_outside_provider_adapter() -> None:
    _assert_no_direct_module_imports_outside_adapter("google.genai")


def test_no_direct_cohere_imports_outside_provider_adapter() -> None:
    _assert_no_direct_module_imports_outside_adapter("cohere")


def test_no_direct_mistralai_imports_outside_provider_adapter() -> None:
    _assert_no_direct_module_imports_outside_adapter("mistralai")


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


# Frontend must not choose provider/model (CLAUDE.md) — no frontend code may import a provider
# SDK directly under any circumstance, so unlike the Python checks above there is no allowed-root
# exemption here at all.
PROVIDER_JS_PACKAGES = {
    "openai",
    "@anthropic-ai/sdk",
    "@google/genai",
    "@google/generative-ai",
    "cohere-ai",
    "mistralai",
    "@mistralai/mistralai",
}
_JS_EXTS = {".ts", ".tsx", ".js", ".jsx"}
# `from "pkg"` (named/default import), `require("pkg")` (CommonJS), a bare side-effect
# `import "pkg"` (no `from` at all), and a dynamic `import("pkg")`/`await import("pkg")` — all four
# are real ways to pull in a module, and each is a real, distinct bypass of an import-specifier
# check that only recognized `from`/`require(`. `import\(?` covers both the side-effect form
# (bare `import`, no paren) and the dynamic form (`import(`) with one alternative. A specifier can
# also be a no-interpolation template literal (`` import(`openai`) ``, valid JS/TS) — the quote
# class covers `` ` `` alongside `'`/`"`; a specifier containing real `${...}` interpolation still
# never equals a plain package name in `PROVIDER_JS_PACKAGES`, so it naturally never false-positives.
_JS_IMPORT_SPECIFIER_RE = re.compile(r"""(?:from|require\(|import\(?)\s*["'`]([^"'`]+)["'`]""")


def _js_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix in _JS_EXTS
        and not any(part in SKIP_PATH_PARTS for part in path.parts)
    ]


def test_no_direct_provider_js_sdk_imports() -> None:
    offenders: list[str] = []
    for path in _js_files():
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in _JS_IMPORT_SPECIFIER_RE.finditer(text):
            if match.group(1) in PROVIDER_JS_PACKAGES:
                offenders.append(f"{path.relative_to(ROOT)} imports {match.group(1)!r}")
                break

    assert offenders == [], "direct provider JS/TS SDK imports found outside provider boundary: " + ", ".join(
        offenders
    )


# Provider API hosts a raw HTTP call (fetch/axios/httpx/requests) could hit directly, bypassing
# ProviderGateway/adapters without ever importing a "forbidden" module or package at all — e.g.
# `fetch("https://api.openai.com/v1/chat/completions")`. A plain substring check is enough: each
# host is specific enough that it doesn't appear in real source by accident.
PROVIDER_API_HOSTS = [
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.cohere.ai",
    "api.mistral.ai",
]


def test_no_direct_provider_api_host_references() -> None:
    offenders: list[str] = []
    for path in ROOT.rglob("*"):
        if not (path.is_file() and path.suffix in ({".py"} | _JS_EXTS)):
            continue
        if any(part in SKIP_PATH_PARTS for part in path.parts):
            continue
        if "tests" in path.parts:
            continue
        if path.suffix == ".py" and (
            path.is_relative_to(ALLOWED_ADAPTER_MODULE_ROOT)
            or path.is_relative_to(ALLOWED_GATEWAY_MODULE_ROOT)
        ):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for host in PROVIDER_API_HOSTS:
            if host in text:
                offenders.append(f"{path.relative_to(ROOT)} references {host!r}")
                break

    assert offenders == [], "direct provider API host references found outside provider boundary: " + ", ".join(
        offenders
    )
