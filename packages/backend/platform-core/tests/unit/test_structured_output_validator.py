from __future__ import annotations

import pytest
from anytoolai_platform_core.structured_output.errors import StructuredOutputMalformedJsonError
from anytoolai_platform_core.structured_output.validator import (
    parse_json_object,
    parse_json_value,
    validate_structured_output,
)

_TEXT_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "additionalProperties": True,
}


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


def test_provider_output_may_contain_a_raw_newline_inside_a_string() -> None:
    """Some models write paragraph breaks as a literal newline inside the JSON string. The text is
    kept exactly; a config-owned literal stays strict (see test_strict_json)."""
    assert parse_json_object('{"text":"First.\n\nSecond."}') == {"text": "First.\n\nSecond."}


@pytest.mark.parametrize(
    "raw",
    [
        '{"text":"hello\x00world"}',
        '{"text":"hello\\u0000world"}',
        '{"te\\u0000xt":"hello"}',
        '{"text":"bell\x07"}',
    ],
    ids=["raw-nul", "escaped-nul", "escaped-nul-key", "raw-bell"],
)
def test_provider_output_rejects_a_nul_or_a_raw_control_other_than_a_line_break(raw: str) -> None:
    """Only a raw newline/tab is tolerated; a NUL cannot be persisted to PostgreSQL JSONB at all."""
    with pytest.raises(StructuredOutputMalformedJsonError):
        validate_structured_output(raw, schema=_TEXT_SCHEMA)


def test_provider_output_keeps_a_raw_newline_and_tab_at_the_structured_output_boundary() -> None:
    result = validate_structured_output('{"text":"First.\n\tSecond."}', schema=_TEXT_SCHEMA)

    assert result.normalized_output == {"text": "First.\n\tSecond."}


def test_config_owned_literal_json_stays_strict_about_control_characters() -> None:
    from anytoolai_platform_core.common.strict_json import parse_strict_json

    with pytest.raises(ValueError, match="control character"):
        parse_strict_json('{"a":"x\ny"}')
