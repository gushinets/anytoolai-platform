from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "agent" / "validate_docs.py"
    spec = importlib.util.spec_from_file_location("validate_docs_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seed_docs(root: Path, *, active_state: str = "active") -> None:
    module = load_module()
    docs = root / "docs"
    (docs / "exec-plans" / "active").mkdir(parents=True)
    (docs / "exec-plans" / "completed").mkdir(parents=True)
    for target in module.REQUIRED_INDEX_LINKS:
        path = docs / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Source\n", encoding="utf-8")
    links = "\n".join(f"- [source]({target})" for target in module.REQUIRED_INDEX_LINKS)
    (docs / "index.md").write_text(links, encoding="utf-8")
    (docs / "exec-plans" / "active" / "plan.md").write_text(
        "\n".join(
            [
                "# Plan",
                "",
                "## Status",
                "",
                f"- State: {active_state}",
                "- Owner: agent",
                "- Last updated: 2026-07-15",
                "- Review date: 2026-07-15",
                "- Next action: test",
                "- Blocker: none",
            ]
        ),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "entry",
    [
        "[Portal](integrations/payment-portal.md)",
        "`integrations/payment-portal.md`",
        "[Portal](integrations/payment-portal.md#ownership-and-sources)",
    ],
)
def test_validate_accepts_normalized_plan_and_links(tmp_path, entry: str) -> None:
    module = load_module()
    seed_docs(tmp_path)
    index = tmp_path / "docs" / "index.md"
    index.write_text(
        index.read_text(encoding="utf-8").replace(
            "[source](integrations/payment-portal.md)", entry
        ),
        encoding="utf-8",
    )
    assert module.validate(tmp_path) == []


def test_validate_rejects_completed_plan_in_active(tmp_path) -> None:
    module = load_module()
    seed_docs(tmp_path, active_state="completed")
    assert any(error.startswith("[DOC004]") for error in module.validate(tmp_path))


def test_validate_rejects_broken_link(tmp_path) -> None:
    module = load_module()
    seed_docs(tmp_path)
    (tmp_path / "docs" / "index.md").write_text("[missing](missing.md)\n", encoding="utf-8")
    assert any(error.startswith("[DOC001]") for error in module.validate(tmp_path))


@pytest.mark.parametrize(
    "replacement",
    [
        "",
        "<!-- integrations/payment-portal.md -->",
        "<!--\n[Portal](integrations/payment-portal.md)\n-->",
        "The path integrations/payment-portal.md has no index entry.",
    ],
)
def test_validate_requires_portal_index_entry_even_when_file_exists(
    tmp_path: Path, replacement: str
) -> None:
    module = load_module()
    seed_docs(tmp_path)
    target = "integrations/payment-portal.md"
    page = tmp_path / "docs" / target
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("# Portal boundary\n", encoding="utf-8")
    index = tmp_path / "docs" / "index.md"
    index.write_text(
        "\n".join(
            replacement if target in line else line
            for line in index.read_text(encoding="utf-8").splitlines()
        ),
        encoding="utf-8",
    )

    errors = module.validate(tmp_path)
    assert len(errors) == 1
    assert errors[0].startswith("[DOC002]")
    assert target in errors[0]
