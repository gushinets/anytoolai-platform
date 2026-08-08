from __future__ import annotations

import re
from datetime import date
from typing import Any, Mapping

from anytoolai_platform_core.actions.runner import ActionInputValidationError
from anytoolai_platform_core.structured_output.errors import StructuredOutputValidationError

_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_iso_date_string(value: Any) -> bool:
    if not isinstance(value, str) or not _ISO_DATE_PATTERN.match(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


_FIELD_TYPE_CHECKS: Mapping[str, Any] = {
    "string": lambda value: isinstance(value, str),
    "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "boolean": lambda value: isinstance(value, bool),
    "date": _is_iso_date_string,
    "array_of_strings": lambda value: isinstance(value, list)
    and all(isinstance(item, str) for item in value),
}


def _cross_validation_error(reason: str) -> StructuredOutputValidationError:
    return StructuredOutputValidationError(
        reason=reason,
        error_type="ActionOutputCrossValidationError",
    )


class ExtractStructuredFieldsInputValidator:
    """Rejects semantically ambiguous A01 input.fields before any provider call is made."""

    def validate(self, *, input_payload: Mapping[str, Any]) -> None:
        field_specs = input_payload.get("fields")
        if not isinstance(field_specs, list):
            return
        seen_names: set[str] = set()
        for spec in field_specs:
            if not isinstance(spec, Mapping):
                continue
            name = spec.get("name")
            if not isinstance(name, str):
                continue
            if name in seen_names:
                raise ActionInputValidationError(
                    f"Action input validation failed: duplicate fields[*].name '{name}'."
                )
            seen_names.add(name)


class ExtractStructuredFieldsCrossValidator:
    """Validates A01 output.values against the dynamic field specs from A01 input.fields."""

    def validate(
        self,
        *,
        input_payload: Mapping[str, Any],
        output: Mapping[str, Any] | None,
    ) -> None:
        if output is None:
            raise _cross_validation_error("missing_output")
        field_specs = input_payload.get("fields")
        if not isinstance(field_specs, list):
            return
        values = output.get("values")
        missing_fields = output.get("missing_fields")
        confidence = output.get("confidence")
        if not isinstance(values, Mapping) or not isinstance(missing_fields, list):
            raise _cross_validation_error("malformed_extraction_output")

        known_names = set()
        required_names = set()
        seen_names: set[str] = set()
        for spec in field_specs:
            if not isinstance(spec, Mapping):
                continue
            name = spec.get("name")
            if not isinstance(name, str):
                continue
            if name in seen_names:
                raise _cross_validation_error(f"duplicate_field_name:{name}")
            seen_names.add(name)
            known_names.add(name)
            if spec.get("required") is True:
                required_names.add(name)
            field_type = spec.get("type")
            type_check = _FIELD_TYPE_CHECKS.get(field_type)
            if type_check is None:
                raise _cross_validation_error(f"unknown_field_type:{name}:{field_type}")
            if name not in values:
                continue
            if not type_check(values[name]):
                raise _cross_validation_error(f"field_type_mismatch:{name}")

        for name in values:
            if name not in known_names:
                raise _cross_validation_error(f"unrequested_field:{name}")
        seen_missing_names: set[str] = set()
        for name in missing_fields:
            if name not in known_names:
                raise _cross_validation_error(f"unrequested_missing_field:{name}")
            if name in values:
                raise _cross_validation_error(f"field_marked_missing_but_present:{name}")
            if name in seen_missing_names:
                raise _cross_validation_error(f"duplicate_missing_field:{name}")
            seen_missing_names.add(name)

        missing_field_set = set(missing_fields)
        for name in known_names:
            if name not in values and name not in missing_field_set:
                raise _cross_validation_error(f"unreported_requested_field:{name}")

        if isinstance(confidence, Mapping):
            for name in confidence:
                if name not in values:
                    raise _cross_validation_error(f"confidence_for_unpopulated_field:{name}")

        strict = input_payload.get("strict") is True
        if strict:
            unresolved_required = [
                name for name in required_names if name not in values
            ]
            if unresolved_required:
                raise _cross_validation_error(
                    "strict_missing_required_fields:" + ",".join(sorted(unresolved_required))
                )


class DetectIssuesByTaxonomyCrossValidator:
    """Validates A04 output.issues categories against the taxonomy from A04 input.taxonomy."""

    def validate(
        self,
        *,
        input_payload: Mapping[str, Any],
        output: Mapping[str, Any] | None,
    ) -> None:
        if output is None:
            raise _cross_validation_error("missing_output")
        taxonomy = input_payload.get("taxonomy")
        if not isinstance(taxonomy, list) or not taxonomy:
            return
        allowed_categories = set(taxonomy)
        issues = output.get("issues")
        if not isinstance(issues, list):
            raise _cross_validation_error("malformed_issue_detection_output")
        for issue in issues:
            if not isinstance(issue, Mapping):
                raise _cross_validation_error("malformed_issue_entry")
            category = issue.get("category")
            if category not in allowed_categories:
                raise _cross_validation_error(f"category_not_in_taxonomy:{category}")
