from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PRODUCT_PLATFORMS = ROOT / "packages" / "backend" / "product-platforms"


@pytest.fixture(scope="module")
def validate_architecture_module():
    path = ROOT / "scripts" / "agent" / "validate_architecture.py"
    spec = importlib.util.spec_from_file_location("validate_architecture_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _check_over_tmp_path(module, tmp_path: Path, monkeypatch) -> list[str]:
    # SKIP_PATH_PARTS excludes scratch/build directory names (e.g. "tmp", ".quick-check-tmp")
    # that can also appear as ancestors of pytest's tmp_path, depending on where the test
    # runner points --basetemp. Drop only the entries that actually collide with tmp_path's
    # own location, so the real recursive walk and the other skip-dir filtering (node_modules,
    # dist, ...) still run for real against the fixture tree underneath it.
    colliding = {part for part in tmp_path.parts if part in module.SKIP_PATH_PARTS}
    monkeypatch.setattr(module, "SKIP_PATH_PARTS", module.SKIP_PATH_PARTS - colliding)
    return module.check_product_platforms_boundary(tmp_path)


def test_product_platforms_has_no_forbidden_imports(validate_architecture_module) -> None:
    errors = validate_architecture_module.check_product_platforms_boundary(PRODUCT_PLATFORMS)

    assert errors == [], "product-platforms must depend on platform-sdk only: " + ", ".join(errors)


def test_forbidden_python_import_is_detected(
    validate_architecture_module, monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / "offending_module.py").write_text(
        "import anytoolai_platform_core\n", encoding="utf-8"
    )

    errors = _check_over_tmp_path(validate_architecture_module, tmp_path, monkeypatch)

    assert len(errors) == 1
    assert errors[0].startswith("ATAI007 ")
    assert "anytoolai_platform_core" in errors[0]


def test_forbidden_python_from_import_is_detected(
    validate_architecture_module, monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / "offending_from_import.py").write_text(
        "from anytoolai_platform_actions import run_action\n", encoding="utf-8"
    )

    errors = _check_over_tmp_path(validate_architecture_module, tmp_path, monkeypatch)

    assert len(errors) == 1
    assert errors[0].startswith("ATAI007 ")
    assert "anytoolai_platform_actions" in errors[0]


def test_forbidden_typescript_import_is_detected(
    validate_architecture_module, monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / "offending_module.ts").write_text(
        'import { runAction } from "anytoolai_platform_actions";\n', encoding="utf-8"
    )

    errors = _check_over_tmp_path(validate_architecture_module, tmp_path, monkeypatch)

    assert len(errors) == 1
    assert errors[0].startswith("ATAI007 ")
    assert "anytoolai_platform_actions" in errors[0]


def test_skip_path_parts_filters_vendored_directories(
    validate_architecture_module, monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / "offending_module.py").write_text(
        "import anytoolai_platform_core\n", encoding="utf-8"
    )
    vendored = tmp_path / "node_modules" / "vendored"
    vendored.mkdir(parents=True)
    (vendored / "also_offending.py").write_text(
        "import anytoolai_platform_core\n", encoding="utf-8"
    )

    errors = _check_over_tmp_path(validate_architecture_module, tmp_path, monkeypatch)

    assert len(errors) == 1
    assert "offending_module.py" in errors[0]
