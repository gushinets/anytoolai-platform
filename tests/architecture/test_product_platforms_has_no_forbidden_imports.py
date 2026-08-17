from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRODUCT_PLATFORMS = ROOT / "packages" / "backend" / "product-platforms"
FORBIDDEN_IMPORTS = {
    "anytoolai_platform_core",
    "anytoolai_platform_actions",
    "anytoolai_platform_api",
    "anytoolai_platform_worker",
}


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


def test_product_platforms_has_no_forbidden_imports() -> None:
    offenders: list[str] = []
    for path in PRODUCT_PLATFORMS.rglob("*.py"):
        for module in FORBIDDEN_IMPORTS:
            if _imports_module(path, module):
                offenders.append(f"{path.relative_to(ROOT)} imports `{module}`")

    assert offenders == [], "product-platforms must depend on platform-sdk only: " + ", ".join(offenders)


def test_forbidden_import_is_detected(tmp_path: Path) -> None:
    fixture = tmp_path / "offending_module.py"
    fixture.write_text("import anytoolai_platform_core\n", encoding="utf-8")

    assert _imports_module(fixture, "anytoolai_platform_core") is True
