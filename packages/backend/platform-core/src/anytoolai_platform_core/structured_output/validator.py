from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from anytoolai_platform_core.common.storable_text import is_unstorable_char
from anytoolai_platform_core.common.strict_json import parse_strict_json
from anytoolai_platform_core.structured_output.errors import (
    StructuredOutputMalformedJsonError,
    StructuredOutputNonObjectJsonError,
    StructuredOutputSchemaMismatchError,
)
from anytoolai_platform_core.structured_output.schemas import (
    StructuredOutputContract,
    normalize_mapping,
    normalize_schema_mapping,
)
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as validate_json_schema


@dataclass(frozen=True)
class StructuredOutputValidationResult:
    raw_text: str
    normalized_output: Any
    contract: StructuredOutputContract


_TOLERATED_RAW_CONTROLS = frozenset("\t\n\r")
# Deeper model output is malformed: every later pass over it (normalization, JSON Schema,
# persistence) is recursive, and no product schema nests anywhere near this.
_MAX_JSON_DEPTH = 64


def parse_json_value(raw: str) -> Any:
    """Model output may break a JSON string with a raw newline or tab; any other raw control is
    malformed. A NUL or an unpaired surrogate (`\\ud800` without its pair) is malformed raw or
    escaped: PostgreSQL JSONB cannot store either, so it would fail persistence after the output
    had already passed validation. A valid pair decodes to one character (an emoji) and passes.
    Nesting deeper than `_MAX_JSON_DEPTH` is malformed too, so it is retried instead of crashing a
    recursive pass with RecursionError."""
    if any(char < " " and char not in _TOLERATED_RAW_CONTROLS for char in raw):
        raise StructuredOutputMalformedJsonError("Malformed JSON")
    try:
        value = parse_strict_json(raw, allow_control_chars=True)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise StructuredOutputMalformedJsonError("Malformed JSON") from exc
    if not _is_storable(value):
        raise StructuredOutputMalformedJsonError("Malformed JSON")
    return value


def _is_storable(value: Any) -> bool:
    """Iterative, so any depth json.loads returns is walked: bounded depth, no unstorable char."""
    stack = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if isinstance(item, str):
            if any(is_unstorable_char(char) for char in item):
                return False
        elif isinstance(item, (dict, list)):
            if depth > _MAX_JSON_DEPTH:
                return False
            children = [*item.keys(), *item.values()] if isinstance(item, dict) else item
            stack.extend((child, depth + 1) for child in children)
    return True


def parse_json_object(raw: str) -> dict[str, Any]:
    value = parse_json_value(raw)
    if not isinstance(value, dict):
        raise StructuredOutputNonObjectJsonError("Expected JSON object")
    return normalize_mapping(value)


def validate_structured_output(
    raw_text: str,
    *,
    schema: Mapping[str, Any] | None,
    requires_object: bool = True,
    schema_ref: str | None = None,
    schema_version: int | None = None,
) -> StructuredOutputValidationResult:
    return validate_structured_output_value(
        parse_json_value(raw_text),
        raw_text=raw_text,
        schema=schema,
        requires_object=requires_object,
        schema_ref=schema_ref,
        schema_version=schema_version,
    )


def validate_structured_output_value(
    value: Any,
    *,
    schema: Mapping[str, Any] | None,
    requires_object: bool = True,
    schema_ref: str | None = None,
    schema_version: int | None = None,
    raw_text: str = "",
) -> StructuredOutputValidationResult:
    """Validate an already-decoded structured output with the canonical contract."""
    contract = StructuredOutputContract(
        schema=normalize_schema_mapping(schema),
        requires_object=requires_object,
        schema_ref=schema_ref,
        schema_version=schema_version,
    )
    if requires_object and not isinstance(value, dict):
        raise StructuredOutputNonObjectJsonError("Expected JSON object")
    normalized_output = normalize_mapping(value) if isinstance(value, dict) else value
    if requires_object and not isinstance(normalized_output, dict):
        raise StructuredOutputNonObjectJsonError("Expected JSON object")
    if contract.schema is not None:
        try:
            validate_json_schema(instance=normalized_output, schema=contract.schema)
        except JsonSchemaValidationError as exc:
            raise StructuredOutputSchemaMismatchError(
                "Structured output does not match schema"
            ) from exc
    return StructuredOutputValidationResult(
        raw_text=raw_text,
        normalized_output=normalized_output,
        contract=contract,
    )
