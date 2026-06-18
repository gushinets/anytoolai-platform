from __future__ import annotations

import tomllib
from pathlib import Path

from anytoolai_freelancer_suite.bundle import FreelancerSuiteBundle


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_freelancer_suite_declares_platform_sdk_dependency() -> None:
    pyproject = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    assert "anytoolai-platform-sdk==0.1.0" in dependencies


def test_freelancer_bundle_exposes_all_validation_products() -> None:
    assert FreelancerSuiteBundle().config_roots() == [
        "products/proposal_ai",
        "products/acceptance_builder",
        "products/case_study",
        "products/scope_guard",
        "products/task_finder",
        "products/send_ready",
        "products/brief_decoder",
        "products/persuasion_lens",
    ]
