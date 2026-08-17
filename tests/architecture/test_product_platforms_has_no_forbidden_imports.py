from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRODUCT_PLATFORMS = ROOT / "packages" / "backend" / "product-platforms"


def _load_validate_architecture():
    path = ROOT / "scripts" / "agent" / "validate_architecture.py"
    spec = importlib.util.spec_from_file_location("validate_architecture_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_product_platforms_has_no_forbidden_imports() -> None:
    module = _load_validate_architecture()

    errors = module.check_product_platforms_boundary(PRODUCT_PLATFORMS)

    assert errors == [], "product-platforms must depend on platform-sdk only: " + ", ".join(errors)


def _check_fixture(monkeypatch, tmp_path: Path) -> list[str]:
    # iter_code_files skips any path with a "tmp" path segment (scratch/build dirs),
    # which always matches pytest's tmp_path. Point it at the fixture file directly so
    # check_product_platforms_boundary's real import-detection and message-formatting
    # logic still runs end-to-end.
    module = _load_validate_architecture()
    fixture_files = list(tmp_path.iterdir())
    monkeypatch.setattr(module, "iter_code_files", lambda _root: iter(fixture_files))
    return module.check_product_platforms_boundary(tmp_path)


def test_forbidden_python_import_is_detected(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "offending_module.py").write_text(
        "import anytoolai_platform_core\n", encoding="utf-8"
    )

    errors = _check_fixture(monkeypatch, tmp_path)

    assert len(errors) == 1
    assert errors[0].startswith("ATAI007 ")
    assert "anytoolai_platform_core" in errors[0]


def test_forbidden_typescript_import_is_detected(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "offending_module.ts").write_text(
        'import { runAction } from "anytoolai_platform_actions";\n', encoding="utf-8"
    )

    errors = _check_fixture(monkeypatch, tmp_path)

    assert len(errors) == 1
    assert errors[0].startswith("ATAI007 ")
    assert "anytoolai_platform_actions" in errors[0]
