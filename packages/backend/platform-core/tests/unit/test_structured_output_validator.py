from __future__ import annotations

import pytest
from anytoolai_platform_core.structured_output.errors import StructuredOutputMalformedJsonError
from anytoolai_platform_core.structured_output.validator import (
    parse_json_object,
    parse_json_value,
)


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_parse_json_value_rejects_non_finite_constants(token: str) -> None:
    with pytest.raises(StructuredOutputMalformedJsonError):
        parse_json_value(token)


def test_parse_json_object_rejects_non_finite_constant_in_nested_value() -> None:
    with pytest.raises(StructuredOutputMalformedJsonError):
        parse_json_object('{"values": {"budget": NaN}}')


def test_parse_json_object_still_accepts_ordinary_numbers() -> None:
    assert parse_json_object('{"values": {"budget": 500}}') == {"values": {"budget": 500}}


def test_parse_json_object_rejects_markdown_fenced_text() -> None:
    """The platform-owned final parser must stay strict -- a fenced response is invalid JSON
    and must be handled by PydanticAI's retry loop (see PydanticAIStructuredRunner._validate_output,
    which re-validates the same raw text with this canonical parser), not silently accepted here
    via a prompt-text parsing heuristic."""
    with pytest.raises(StructuredOutputMalformedJsonError):
        parse_json_object('```json\n{"name": "Ada"}\n```')


def test_parse_json_object_rejects_empty_string() -> None:
    with pytest.raises(StructuredOutputMalformedJsonError):
        parse_json_object("")
