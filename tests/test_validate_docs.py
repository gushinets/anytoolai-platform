from __future__ import annotations

import importlib.util
from pathlib import Path


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


def test_validate_accepts_normalized_plan_and_links(tmp_path) -> None:
    module = load_module()
    seed_docs(tmp_path)
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
