#!/usr/bin/env python3
from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
# Keep the code-extension aliases defined so merge refs that preserve the
# older iter_code_files path still have a consistent symbol to use.
PY_EXTS = {".py"}
JS_TS_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
CODE_EXTS = PY_EXTS | JS_TS_EXTS
TEXT_EXTS = {".py", ".ts", ".tsx", ".md", ".yaml", ".yml", ".json"}
SKIP_PATH_PARTS = {
    ".git",
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

FORBIDDEN_PLATFORM_TERMS = [
    "FreelancerProfile",
    "ExternalTask",
    "Proposal",
    "Brief",
    "ScopeCreep",
    "AcceptanceDocument",
    "CaseStudy",
    "RhetoricalAnalysis",
    "Upwork",
    "Gmail",
    "client message",
    "proposal angle",
    "send-ready verdict",
    "generate_proposal",
    "acceptance_document",
    "proposal_ai",
]

LLM_PROVIDER_IMPORTS = {
    "litellm",
    "pydantic_ai",
    "openai",
    "anthropic",
    "google.genai",
    "@google/genai",
    "cohere",
    "mistralai",
}

JS_MODULE_IMPORT_RE = re.compile(
    r"""
    (?:
        (?:import|export)\s+
        (?:(?:type\s+)?[^'"]*?\s+from\s+)?
        ["']([^"']+)["']
    )
    |
    (?:require\(\s*["']([^"']+)["']\s*\))
    |
    (?:import\(\s*["']([^"']+)["']\s*\))
    """,
    re.VERBOSE,
)
GOOGLE_GENAI_NAMED_IMPORT_RE = re.compile(
    r"""import\s+(?:type\s+)?\{[^}]*\bgenai\b[^}]*\}\s+from\s+["']google["']"""
)


def iter_text_files(root: Path) -> Iterator[Path]:
    """Yield repo text files that architecture validation should scan."""
    if not root.exists():
        return
    for path in root.rglob("*"):
        if any(part in SKIP_PATH_PARTS for part in path.parts):
            continue
        if path.is_file() and path.suffix in TEXT_EXTS:
            yield path


def iter_code_files(root: Path) -> Iterator[Path]:
    """Yield source files that import-boundary validation should scan."""
    if not root.exists():
        return
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in CODE_EXTS and ".git" not in path.parts:
            yield path


def imported_python_modules(path: Path) -> set[str]:
    """Return Python direct imports and from-imported submodule candidates."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return set()

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
            if node.level == 0:
                for alias in node.names:
                    if alias.name != "*":
                        imports.add(f"{node.module}.{alias.name}")
    return imports


def imported_js_ts_modules(path: Path) -> set[str]:
    """Return JavaScript/TypeScript module specifiers from imports/requires."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    imports: set[str] = set()
    for match in JS_MODULE_IMPORT_RE.finditer(text):
        module = next((value for value in match.groups() if value), None)
        if module:
            imports.add(module)

    if GOOGLE_GENAI_NAMED_IMPORT_RE.search(text):
        imports.add("google.genai")

    return imports


def imported_modules(path: Path) -> set[str]:
    """Return modules imported by a supported source file."""
    if path.suffix in PY_EXTS:
        return imported_python_modules(path)
    if path.suffix in JS_TS_EXTS:
        return imported_js_ts_modules(path)
    return set()


def imports_module(imports: set[str], module: str) -> bool:
    """Return whether any captured import references a forbidden module."""
    return any(
        imported == module
        or imported.startswith(f"{module}.")
        or imported.startswith(f"{module}/")
        for imported in imports
    )


def is_provider_boundary(path: Path) -> bool:
    """Return whether a path is inside the AnytoolAI provider boundary."""
    relative = path.relative_to(ROOT)
    return (
        relative.parts[:3] == ("packages", "backend", "platform-core")
        and "providers" in relative.parts
    )


def is_structured_llm_executor_boundary(path: Path) -> bool:
    """Return whether a path is inside a structured LLM executor boundary."""
    relative = path.relative_to(ROOT)
    return (
        relative.parts[:3] == ("packages", "backend", "platform-actions")
        and (
            "structured_llm" in relative.parts
            or "structured_llm_executor" in relative.parts
        )
    )


def main() -> int:
    """Validate product-domain and LLM/provider import architecture boundaries."""
    errors: list[str] = []

    platform_core = ROOT / "packages" / "backend" / "platform-core"
    platform_actions = ROOT / "packages" / "backend" / "platform-actions"
    extensions = ROOT / "extensions"

    for path in iter_text_files(platform_core):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "product-platforms" in text or "anytoolai_freelancer" in text:
            errors.append(f"ATAI001 {path}: platform-core must not import product-platforms")
        for term in FORBIDDEN_PLATFORM_TERMS:
            if term in text:
                errors.append(f"ATAI002 {path}: forbidden product term in platform-core: {term}")

    for path in iter_text_files(platform_actions):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "product-platforms" in text or "anytoolai_freelancer" in text:
            errors.append(f"ATAI004 {path}: platform-actions must not import product-platforms")

    for root in [ROOT / "apps", ROOT / "packages", ROOT / "extensions"]:
        for path in iter_code_files(root):
            imports = imported_modules(path)
            for module in LLM_PROVIDER_IMPORTS:
                if not imports_module(imports, module):
                    continue

                if module == "litellm" and is_provider_boundary(path):
                    continue
                if module == "pydantic_ai" and is_structured_llm_executor_boundary(path):
                    continue
                if module in {"openai", "anthropic", "google.genai", "@google/genai", "cohere", "mistralai"} and is_provider_boundary(path):
                    continue

                errors.append(
                    "ATAI006 "
                    f"{path}: forbidden direct LLM/provider import `{module}` outside approved gateway/executor boundary"
                )

    for path in iter_text_files(extensions):
        if path.name in {"AGENTS.md", "README.md"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        if "system prompt" in text or "prompt_ref" in text or "provider_policy" in text:
            errors.append(f"ATAI005 {path}: extensions must not contain prompts or provider selection")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("Architecture validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
