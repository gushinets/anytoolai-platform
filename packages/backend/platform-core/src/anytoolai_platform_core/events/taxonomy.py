from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path

import yaml


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists() and (parent / "configs").exists():
            return parent
    raise RuntimeError("unable to locate repo root for platform event taxonomy")


def taxonomy_source_path() -> Path:
    return _repo_root() / "configs" / "kernel" / "platform_events.yaml"


@lru_cache(maxsize=1)
def load_platform_event_taxonomy() -> dict[str, object]:
    with taxonomy_source_path().open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    groups = data.get("groups")
    required_dimensions = data.get("required_dimensions")
    if not isinstance(groups, Mapping):
        raise RuntimeError("platform event taxonomy must define a mapping of groups")
    if not isinstance(required_dimensions, Sequence):
        raise RuntimeError("platform event taxonomy must define required_dimensions")
    return {
        "groups": {
            str(group): tuple(str(event) for event in events)
            for group, events in groups.items()
        },
        "required_dimensions": tuple(str(value) for value in required_dimensions),
    }


def platform_event_groups() -> dict[str, tuple[str, ...]]:
    return dict(load_platform_event_taxonomy()["groups"])


PLATFORM_EVENT_GROUPS = platform_event_groups()
PLATFORM_EVENTS = frozenset(
    event for events in PLATFORM_EVENT_GROUPS.values() for event in events
)
REQUIRED_EVENT_DIMENSIONS = tuple(load_platform_event_taxonomy()["required_dimensions"])


def render_event_catalog_markdown() -> str:
    lines = [
        "# Event Catalog",
        "",
        "<!-- Generated file. Do not edit by hand. -->",
        "Canonical source: configs/kernel/platform_events.yaml.",
        "",
        "Generated-doc mirror of the MVP-A platform event taxonomy from "
        "`configs/kernel/platform_events.yaml`.",
        "",
        "## Platform Events By Group",
        "",
    ]
    for group, events in PLATFORM_EVENT_GROUPS.items():
        lines.append(f"### {group}")
        lines.append("")
        lines.extend(f"- `{event}`" for event in events)
        lines.append("")
    lines.extend(
        [
            "## Required Dimensions Where Applicable",
            "",
            *[f"- `{dimension}`" for dimension in REQUIRED_EVENT_DIMENSIONS],
            "",
            "Product-specific events begin in MVP-B.",
            "",
        ]
    )
    return "\n".join(lines)
