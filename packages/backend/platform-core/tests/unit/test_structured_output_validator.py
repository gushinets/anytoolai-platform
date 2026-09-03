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


def test_parse_json_object_strips_markdown_fences() -> None:
    """PydanticAI's own object output processor tolerates a ```json fenced response before
    validating it (pydantic_ai._utils.strip_markdown_fences); AnyToolAI's mandatory final
    re-validation of the same raw text must accept it too, or a schema-bound response PydanticAI
    already validated successfully would fail final validation on the still-fenced text."""
    assert parse_json_object('```json\n{"name": "Ada"}\n```') == {"name": "Ada"}


def test_parse_json_object_leaves_unfenced_text_untouched() -> None:
    with pytest.raises(StructuredOutputMalformedJsonError):
        parse_json_object("not json, and not fenced either")
