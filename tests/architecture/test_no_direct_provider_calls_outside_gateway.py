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


def _imports_openai(text: str) -> bool:
    try:
        module = ast.parse(text)
    except SyntaxError:
        return False

    for node in ast.walk(module):
        if isinstance(node, ast.Import) and any(alias.name == "openai" for alias in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "openai":
            return True
    return False


def test_no_direct_openai_imports_outside_provider_adapter() -> None:
    for path in ROOT.rglob("*.py"):
        if any(part in SKIP_PATH_PARTS for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if _imports_openai(text):
            assert "providers/adapters/openai.py" in str(path), f"direct provider import in {path}"
