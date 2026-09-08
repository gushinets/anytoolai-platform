"""ANY-32 code-review finding: package-relative config_roots() resolution only helps if the
product config files it points at actually ship inside the built wheel. setuptools does not
include non-.py files by default, so this proves the package-data declaration in pyproject.toml
actually works, using a throwaway fixture product file (independent of client_update_writer,
ANY-413's real product root, so this test stays a minimal packaging-only proof)."""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _uv_executable() -> str:
    return shutil.which("uv") or "uv"


@pytest.mark.slow
def test_non_python_product_config_files_are_included_in_the_built_wheel(
    tmp_path: Path,
) -> None:
    package_copy = tmp_path / "freelancer-suite"
    shutil.copytree(
        PACKAGE_ROOT,
        package_copy,
        ignore=shutil.ignore_patterns("build", "*.egg-info", "__pycache__"),
    )
    fixture_product_dir = (
        package_copy / "src" / "anytoolai_freelancer_suite" / "products" / "_packaging_fixture"
    )
    fixture_product_dir.mkdir(parents=True)
    (fixture_product_dir / "product.yaml").write_text(
        "product_id: _packaging_fixture\n", encoding="utf-8"
    )

    out_dir = tmp_path / "dist"
    subprocess.run(
        [_uv_executable(), "build", "--wheel", "-o", str(out_dir), str(package_copy)],
        check=True,
        capture_output=True,
        text=True,
    )

    (wheel_path,) = out_dir.glob("*.whl")
    wheel_names = zipfile.ZipFile(wheel_path).namelist()

    assert "anytoolai_freelancer_suite/products/_packaging_fixture/product.yaml" in wheel_names
