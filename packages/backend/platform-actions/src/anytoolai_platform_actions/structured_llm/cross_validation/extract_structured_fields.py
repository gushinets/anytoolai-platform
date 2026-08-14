from __future__ import annotations

from typing import Any, Mapping

from ._shared import (
    _coerce_integer_valued,
    _cross_validation_error,
    _is_finite_number,
    _is_iso_date_string,
    _reject_duplicate_ids,
    _require_output,
    _truncated_repr,
)

_FIELD_TYPE_CHECKS: Mapping[str, Any] = {
    "string": lambda value: isinstance(value, str),
    "number": _is_finite_number,
    "integer": lambda value: _coerce_integer_valued(value) is not None,
    "boolean": lambda value: isinstance(value, bool),
    "date": _is_iso_date_string,
    "array_of_strings": lambda value: isinstance(value, list)
    and all(isinstance(item, str) for item in value),
}


class ExtractStructuredFieldsInputValidator:
    """Rejects semantically ambiguous A01 input.fields before any provider call is made."""

    def validate(self, *, input_payload: Mapping[str, Any]) -> None:
        _reject_duplicate_ids(
            input_payload.get("fields"), id_field="name", error_label="fields[*].name"
        )


class ExtractStructuredFieldsCrossValidator:
    """Validates A01 output.values against the dynamic field specs from A01 input.fields."""

    def validate(
        self,
        *,
        input_payload: Mapping[str, Any],
        output: Mapping[str, Any] | None,
    ) -> None:
        output = _require_output(output)
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
                raise _cross_validation_error(f"unrequested_field:{_truncated_repr(name)}")
        seen_missing_names: set[str] = set()
        for name in missing_fields:
            if name not in known_names:
                raise _cross_validation_error(
                    f"unrequested_missing_field:{_truncated_repr(name)}"
                )
            if name in values:
                raise _cross_validation_error(
                    f"field_marked_missing_but_present:{_truncated_repr(name)}"
                )
            if name in seen_missing_names:
                raise _cross_validation_error(f"duplicate_missing_field:{_truncated_repr(name)}")
            seen_missing_names.add(name)

        missing_field_set = set(missing_fields)
        for name in known_names:
            if name not in values and name not in missing_field_set:
                raise _cross_validation_error(f"unreported_requested_field:{name}")

        if isinstance(confidence, Mapping):
            for name in confidence:
                if name not in values:
                    raise _cross_validation_error(
                        f"confidence_for_unpopulated_field:{_truncated_repr(name)}"
                    )

        strict = input_payload.get("strict") is True
        if strict:
            unresolved_required = [
                name for name in required_names if name not in values
            ]
            if unresolved_required:
                raise _cross_validation_error(
                    "strict_missing_required_fields:" + ",".join(sorted(unresolved_required))
                )
