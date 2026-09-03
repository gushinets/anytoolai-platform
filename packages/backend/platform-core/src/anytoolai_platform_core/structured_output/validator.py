from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

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


# Mirrors pydantic_ai's own markdown-fence tolerance (pydantic_ai._utils.strip_markdown_fences)
# so AnyToolAI's mandatory final-validate parses the same text PydanticAI already accepted for a
# schema-bound structured action -- otherwise a fenced response PydanticAI validates successfully
# (spending no retry budget) fails final validation on the still-fenced raw text and surfaces an
# uncaught error instead of the intended PydanticAI ModelRetry/exhaustion path.
_MARKDOWN_FENCES_PATTERN = re.compile(r"```(?:\w+)?\r?\n(\{.*?\})\s*(?:\r?\n?```|\Z)", flags=re.DOTALL)


def _strip_markdown_fences(text: str) -> str:
    if text.startswith("{"):
        return text
    match = _MARKDOWN_FENCES_PATTERN.search(text)
    if match:
        return match.group(1)
    return text


def parse_json_value(raw: str) -> Any:
    try:
        return parse_strict_json(_strip_markdown_fences(raw))
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
