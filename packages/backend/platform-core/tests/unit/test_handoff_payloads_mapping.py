from __future__ import annotations

import pytest
from anytoolai_platform_core.handoffs.payloads import HandoffPayloadError, _apply_mapping


def test_apply_mapping_resolves_literal_source_when_allowed() -> None:
    result = _apply_mapping(
        {"fields": 'literal:[{"name":"deadline"}]'},
        {},
        allow_literal=True,
    )

    assert result == {"fields": [{"name": "deadline"}]}


def test_apply_mapping_rejects_literal_source_when_disallowed() -> None:
    with pytest.raises(HandoffPayloadError) as exc_info:
        _apply_mapping(
            {"fields": 'literal:[{"name":"deadline"}]'},
            {},
            allow_literal=False,
        )

    assert "not allowed here" in str(exc_info.value)


def test_apply_mapping_still_resolves_artifact_paths_regardless_of_allow_literal() -> None:
    artifact = {"values": {"deadline": "Friday"}}

    for allow_literal in (True, False):
        result = _apply_mapping(
            {"deadline": "artifact.content_json.values.deadline"},
            artifact,
            allow_literal=allow_literal,
        )
        assert result == {"deadline": "Friday"}
