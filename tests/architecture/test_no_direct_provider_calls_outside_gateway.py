from __future__ import annotations

import ast
import re
from pathlib import Path

from static_string_resolution import (
    JS_TS_EXTS,
    iter_source_files,
    js_modules,
    js_string_values,
    line_number_at,
    parse_python_files,
    python_modules,
    python_string_values,
)

ROOT = Path(__file__).resolve().parents[2]
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
    return iter_source_files(ROOT, {".py"})


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
# `from "pkg"` (named/default import), `require("pkg")` (CommonJS), a bare side-effect
# `import "pkg"` (no `from` at all), and a dynamic `import("pkg")`/`await import("pkg")` — all four
# are real ways to pull in a module, and each is a real, distinct bypass of an import-specifier
# check that only recognized `from`/`require(`. `import\(?` covers both the side-effect form
# (bare `import`, no paren) and the dynamic form (`import(`) with one alternative. A specifier can
# also be a no-interpolation template literal (`` import(`openai`) ``, valid JS/TS) — the quote
# class covers `` ` `` alongside `'`/`"`; a specifier containing real `${...}` interpolation still
# never equals a plain package name in `PROVIDER_JS_PACKAGES`, so it naturally never false-positives.
# `require`/`import` and their `(` don't have to be adjacent (`require ("pkg")`, `import
# ("pkg")` are both valid JS/TS) — `\s*` between the keyword and `\(` tolerates that the same way
# it already does between the whole call form and the opening quote.
_JS_IMPORT_SPECIFIER_RE = re.compile(
    r"""(?:from|require\s*\(|import\s*\(?)\s*["'`]([^"'`]+)["'`]"""
)


def _js_files() -> list[Path]:
    return iter_source_files(ROOT, JS_TS_EXTS)


def _is_forbidden_js_specifier(specifier: str) -> bool:
    """`specifier` is a forbidden package itself, or a subpath import from one
    (`openai/resources/chat/completions` from `openai`) — still a direct provider SDK import,
    just not of the package's own root. The `/` boundary means `openai-compatible` (a different,
    unrelated package) doesn't false-positive against `openai`."""
    return any(
        specifier == package or specifier.startswith(f"{package}/")
        for package in PROVIDER_JS_PACKAGES
    )


def test_no_direct_provider_js_sdk_imports() -> None:
    offenders: list[str] = []
    for path in _js_files():
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in _JS_IMPORT_SPECIFIER_RE.finditer(text):
            if _is_forbidden_js_specifier(match.group(1)):
                offenders.append(f"{path.relative_to(ROOT)} imports {match.group(1)!r}")
                break

    assert offenders == [], "direct provider JS/TS SDK imports found outside provider boundary: " + ", ".join(
        offenders
    )


# Provider API hosts a raw HTTP call (fetch/axios/httpx/requests) could hit directly, bypassing
# ProviderGateway/adapters without ever importing a "forbidden" module or package at all — e.g.
# `fetch("https://api.openai.com/v1/chat/completions")`. Checked two ways: a plain substring
# search over the raw source (each host is specific enough never to appear by accident, and this
# also covers comments/prose), plus every *statically folded* string value — so a host split
# across a concatenation (`"https://api." + "openai.com/v1"`), a template literal, an f-string, or
# a constant defined in another module is caught exactly like the contiguous literal is.
PROVIDER_API_HOSTS = [
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.cohere.ai",
    "api.mistral.ai",
]


def _host_in(value: str) -> str | None:
    return next((host for host in PROVIDER_API_HOSTS if host in value), None)


def check_provider_api_host_references(root: Path, allowed_python_roots: tuple[Path, ...]) -> list[str]:
    offenders: list[str] = []
    python_paths = [
        path
        for path in iter_source_files(root, {".py"}, {"tests"})
        if not any(path.is_relative_to(allowed) for allowed in allowed_python_roots)
    ]
    py = python_modules(root, parse_python_files(python_paths))
    for path in python_paths:
        host = _host_in(path.read_text(encoding="utf-8", errors="ignore"))
        if host is None:
            resolved = next(
                ((lineno, host) for lineno, value in python_string_values(py, path) if (host := _host_in(value))),
                None,
            )
            if resolved is None:
                continue
            host = f"{resolved[1]} (folded, line {resolved[0]})"
        offenders.append(f"{path.relative_to(root)} references {host!r}")

    js_paths = iter_source_files(root, JS_TS_EXTS, {"tests"})
    js = js_modules(js_paths)
    for path in js_paths:
        host = _host_in(path.read_text(encoding="utf-8", errors="ignore"))
        if host is None:
            resolved = next(
                ((offset, host) for offset, value in js_string_values(js, path) if (host := _host_in(value))),
                None,
            )
            if resolved is None:
                continue
            host = f"{resolved[1]} (folded, line {line_number_at(js.texts[path], resolved[0])})"
        offenders.append(f"{path.relative_to(root)} references {host!r}")
    return offenders


def test_no_direct_provider_api_host_references() -> None:
    offenders = check_provider_api_host_references(
        ROOT, (ALLOWED_ADAPTER_MODULE_ROOT, ALLOWED_GATEWAY_MODULE_ROOT)
    )
    assert offenders == [], "direct provider API host references found outside provider boundary: " + ", ".join(
        offenders
    )


def test_concatenated_provider_host_is_detected_in_js(tmp_path: Path) -> None:
    (tmp_path / "client.ts").write_text(
        'const endpoint = "https://api." + "openai.com/v1/responses";\n'
        "await fetch(endpoint, { method: \"POST\" });\n",
        encoding="utf-8",
    )
    (tmp_path / "hosts.ts").write_text('export const HOST = "api.anthropic";\n', encoding="utf-8")
    (tmp_path / "template.ts").write_text(
        'import { HOST } from "./hosts";\nconst url = `https://${HOST}.com/v1/messages`;\n',
        encoding="utf-8",
    )
    offenders = check_provider_api_host_references(tmp_path, ())
    assert len(offenders) == 2, offenders
    assert any("client.ts" in o and "api.openai.com" in o for o in offenders)
    assert any("template.ts" in o and "api.anthropic.com" in o for o in offenders)


def test_concatenated_provider_host_is_detected_in_python(tmp_path: Path) -> None:
    (tmp_path / "hosts.py").write_text('BASE = "https://api."\n', encoding="utf-8")
    (tmp_path / "client.py").write_text(
        "from hosts import BASE\nURL = BASE + \"openai.com/v1/responses\"\n", encoding="utf-8"
    )
    (tmp_path / "fstring.py").write_text(
        'import hosts as h\nURL = f"{h.BASE}mistral.ai/v1"\n', encoding="utf-8"
    )
    (tmp_path / "dynamic.py").write_text(
        'def url(host: str) -> str:\n    return "https://api." + host\n', encoding="utf-8"
    )
    offenders = check_provider_api_host_references(tmp_path, ())
    assert len(offenders) == 2, offenders
    assert any("client.py" in o and "api.openai.com" in o for o in offenders)
    assert any("fstring.py" in o and "api.mistral.ai" in o for o in offenders)
