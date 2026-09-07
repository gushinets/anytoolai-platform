from __future__ import annotations

import tomllib
from pathlib import Path

from anytoolai_freelancer_suite.bundle import FreelancerSuiteBundle


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_freelancer_suite_declares_platform_sdk_dependency() -> None:
    pyproject = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    assert "anytoolai-platform-sdk==0.1.0" in dependencies


def test_freelancer_bundle_has_no_implemented_product_roots() -> None:
    """ANY-32 (B01): the bundle starts with zero product roots. ProposalAI becomes the first
    real one in ANY-227 -- see this package's README for the full 6-product roadmap order."""
    assert FreelancerSuiteBundle().bundle_id == "freelancer_suite"
    assert FreelancerSuiteBundle().config_roots() == []
