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
