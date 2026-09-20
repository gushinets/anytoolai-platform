from __future__ import annotations

import tomllib
from pathlib import Path

from anytoolai_freelancer_suite.bundle import FreelancerSuiteBundle


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_freelancer_suite_declares_platform_sdk_dependency() -> None:
    pyproject = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    assert "anytoolai-platform-sdk==0.1.0" in dependencies


def test_freelancer_bundle_has_the_implemented_product_roots_in_release_order() -> None:
    """ANY-227 (B02a) ProposalAI and ANY-413 Client Update Writer are the implemented product
    roots so far -- see this package's README for the full 5-product release order (ANY-452)."""
    bundle = FreelancerSuiteBundle()
    assert bundle.bundle_id == "freelancer_suite"
    roots = bundle.config_roots()
    assert [root.name for root in roots] == ["proposal_ai", "client_update_writer"]
    for root in roots:
        assert (root / "product.yaml").is_file()
