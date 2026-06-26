#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
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


def iter_text_files(root: Path):
    for path in root.rglob("*"):
        if any(part in SKIP_PATH_PARTS for part in path.parts):
            continue
        if path.is_file() and path.suffix in TEXT_EXTS:
            yield path


def main() -> int:
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
        if "from openai" in text or "import openai" in text:
            if "providers/adapters/openai.py" not in str(path):
                errors.append(f"ATAI003 {path}: direct OpenAI import outside provider adapter")

    for path in iter_text_files(platform_actions):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "product-platforms" in text or "anytoolai_freelancer" in text:
            errors.append(f"ATAI004 {path}: platform-actions must not import product-platforms")

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
