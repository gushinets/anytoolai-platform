from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as validate_json_schema

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


@dataclass(frozen=True)
class StructuredOutputValidationResult:
    raw_text: str
    normalized_output: Any
    contract: StructuredOutputContract


def parse_json_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StructuredOutputMalformedJsonError("Malformed JSON") from exc


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
    contract = StructuredOutputContract(
        schema=normalize_schema_mapping(schema),
        requires_object=requires_object,
        schema_ref=schema_ref,
        schema_version=schema_version,
    )
    parsed = parse_json_value(raw_text)
    if requires_object and not isinstance(parsed, dict):
        raise StructuredOutputNonObjectJsonError("Expected JSON object")
    normalized_output = normalize_mapping(parsed) if isinstance(parsed, dict) else parsed
    if requires_object and not isinstance(normalized_output, dict):
        raise StructuredOutputNonObjectJsonError("Expected JSON object")
    if contract.schema is not None:
        try:
            validate_json_schema(instance=normalized_output, schema=contract.schema)
        except JsonSchemaValidationError as exc:
            raise StructuredOutputSchemaMismatchError("Structured output does not match schema") from exc
    return StructuredOutputValidationResult(
        raw_text=raw_text,
        normalized_output=normalized_output,
        contract=contract,
    )
