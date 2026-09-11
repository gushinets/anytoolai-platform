from __future__ import annotations

from pathlib import Path

from anytoolai_platform_core.events.client_events import WebClientEventType
from anytoolai_platform_core.events.envelope import EventEnvelope
from anytoolai_platform_core.events.taxonomy import (
    PLATFORM_EVENT_GROUPS,
    REQUIRED_EVENT_DIMENSIONS,
    render_event_catalog_markdown,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_event_envelope_has_required_dimensions() -> None:
    fields = set(EventEnvelope.__dataclass_fields__)
    assert set(REQUIRED_EVENT_DIMENSIONS) <= fields


def test_event_taxonomy_covers_required_groups() -> None:
    required_groups = {
        "guest",
        "quota",
        "scenario",
        "workflow",
        "action",
        "provider",
        "artifact",
        "handoff",
        "client",
        "web",
    }
    assert required_groups <= set(PLATFORM_EVENT_GROUPS)


def test_event_taxonomy_contains_required_client_events() -> None:
    required = {"client.result_copied", "client.next_action_clicked"}
    assert required <= set(PLATFORM_EVENT_GROUPS["client"])


def test_event_taxonomy_web_group_matches_client_event_allowlist_enum() -> None:
    # `WebClientEventType` is a hand-maintained StrEnum (closed HTTP fields must be an enum, not
    # a plain `str` -- docs/agent/coding-conventions.md), not generated from
    # configs/kernel/platform_events.yaml. This is the drift check between the two sources.
    assert set(PLATFORM_EVENT_GROUPS["web"]) == {member.value for member in WebClientEventType}


def test_generated_event_catalog_matches_taxonomy_source() -> None:
    catalog_path = _repo_root() / "docs" / "generated" / "event-catalog.md"
    assert catalog_path.read_text(encoding="utf-8") == render_event_catalog_markdown()
