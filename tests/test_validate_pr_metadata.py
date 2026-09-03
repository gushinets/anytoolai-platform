from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def load_validator_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "agent" / "validate_pr_metadata.py"
    spec = importlib.util.spec_from_file_location("validate_pr_metadata_module", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def validator():
    return load_validator_module()


def pr_body(issue_id: str = "ANY-338") -> str:
    return f"""## Linear issue

https://linear.app/paveldik/issue/{issue_id}/propagate-core-closed-enums

## Summary

Something changed.
"""


def test_accepts_matching_title_and_linear_url(validator) -> None:
    validator.validate_pr_metadata(
        "ANY-338 - Propagate Core closed enums",
        pr_body(),
    )


@pytest.mark.parametrize(
    "title",
    [
        "ANY-338: Propagate Core closed enums",
        "ANY-0 - Something",
        "ANY-338 -",
    ],
)
def test_rejects_invalid_title_formats(validator, title: str) -> None:
    with pytest.raises(validator.MetadataError, match="Invalid PR title"):
        validator.validate_pr_metadata(title, pr_body())


def test_rejects_missing_linear_url(validator) -> None:
    body = "## Linear issue\n\nNot supplied.\n\n## Summary\n\nSomething changed.\n"

    with pytest.raises(validator.MetadataError, match="exactly one full Linear issue URL"):
        validator.validate_pr_metadata("ANY-338 - Something", body)


def test_rejects_different_ticket_ids(validator) -> None:
    with pytest.raises(validator.MetadataError, match="does not match"):
        validator.validate_pr_metadata("ANY-338 - Something", pr_body("ANY-337"))


def test_rejects_multiple_urls_in_linear_section(validator) -> None:
    body = pr_body().replace(
        "\n\n## Summary",
        "\nhttps://linear.app/paveldik/issue/ANY-339/other\n\n## Summary",
    )

    with pytest.raises(validator.MetadataError, match="exactly one full Linear issue URL"):
        validator.validate_pr_metadata("ANY-338 - Something", body)


def test_ignores_follow_up_ticket_links_outside_linear_section(validator) -> None:
    body = pr_body() + "\n## Follow-up debt\n\nhttps://linear.app/paveldik/issue/ANY-339/other\n"

    validator.validate_pr_metadata("ANY-338 - Something", body)
