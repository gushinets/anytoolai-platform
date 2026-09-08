from __future__ import annotations

import tomllib
from pathlib import Path

from anytoolai_freelancer_suite.bundle import FreelancerSuiteBundle


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_freelancer_suite_declares_platform_sdk_dependency() -> None:
    pyproject = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    assert "anytoolai-platform-sdk==0.1.0" in dependencies


def test_freelancer_bundle_has_the_client_update_writer_product_root() -> None:
    """ANY-413: client_update_writer is the first implemented product root -- see this package's
    README for the full 6-product roadmap order."""
    assert FreelancerSuiteBundle().bundle_id == "freelancer_suite"
    (config_root,) = FreelancerSuiteBundle().config_roots()
    assert config_root.name == "client_update_writer"
    assert (config_root / "product.yaml").is_file()
