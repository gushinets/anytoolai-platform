#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
INDEX_PATH_PATTERN = re.compile(r"`([^\`]+(?:\.md|/))`")
ACTIVE_FIELDS = ("Owner", "Last updated", "Review date", "Next action", "Blocker")
REQUIRED_INDEX_LINKS = (
    "product-specs/mvp-scope-source-of-truth.md",
    "architecture/platform-boundaries.md",
    "architecture/package-layering.md",
    "architecture/llm-runtime.md",
    "agent/harness-engineering-map.md",
)
GUIDANCE = "See docs/index.md and docs/exec-plans/template.md."


def validate(root: Path = ROOT) -> list[str]:
    docs = root / "docs"
    errors: list[str] = []
    for markdown in sorted(docs.rglob("*.md")):
        text = markdown.read_text(encoding="utf-8")
        for match in LINK_PATTERN.finditer(text):
            raw_target = match.group(1).strip().split(maxsplit=1)[0].strip("<>")
            target = raw_target.split("#", 1)[0]
            if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                continue
            if not (markdown.parent / target).resolve().exists():
                errors.append(
                    f"[DOC001] {markdown.relative_to(root)}: broken link "
                    f"{raw_target!r}. {GUIDANCE}"
                )

    index_text = (docs / "index.md").read_text(encoding="utf-8")
    for target in INDEX_PATH_PATTERN.findall(index_text):
        if not (docs / target).resolve().exists():
            errors.append(
                f"[DOC001] docs/index.md: broken indexed path {target!r}. {GUIDANCE}"
            )
    for target in REQUIRED_INDEX_LINKS:
        if target not in index_text:
            errors.append(
                f"[DOC002] docs/index.md: missing required link {target!r}. {GUIDANCE}"
            )

    errors.extend(_validate_plan_directory(root, "active", {"active", "blocked"}, True))
    errors.extend(_validate_plan_directory(root, "completed", {"completed"}, False))
    return errors


def _validate_plan_directory(
    root: Path,
    directory: str,
    allowed_states: set[str],
    require_metadata: bool,
) -> list[str]:
    errors: list[str] = []
    plan_dir = root / "docs" / "exec-plans" / directory
    for plan in sorted(plan_dir.glob("*.md")):
        if plan.name == "README.md":
            continue
        text = plan.read_text(encoding="utf-8")
        state_match = re.search(r"(?m)^- State:\s*([a-z_-]+)\s*$", text)
        if state_match is None:
            errors.append(
                f"[DOC003] {plan.relative_to(root)}: missing or unknown plan state. {GUIDANCE}"
            )
            continue
        state = state_match.group(1)
        if state not in allowed_states:
            errors.append(
                f"[DOC004] {plan.relative_to(root)}: state {state!r} is invalid in "
                f"{directory}/; move the plan or correct its state. {GUIDANCE}"
            )
        if require_metadata:
            for field in ACTIVE_FIELDS:
                if re.search(rf"(?m)^- {re.escape(field)}:\s*\S", text) is None:
                    errors.append(
                        f"[DOC005] {plan.relative_to(root)}: missing {field!r} "
                        f"metadata. {GUIDANCE}"
                    )
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Documentation validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
