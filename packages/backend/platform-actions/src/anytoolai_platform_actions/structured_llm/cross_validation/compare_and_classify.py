from __future__ import annotations

from typing import Any, Mapping

from anytoolai_platform_core.actions.runner import ActionInputValidationError

from ._shared import (
    _cross_validation_error,
    _optional_membership_set,
    _require_output,
    _truncated_repr,
)


class CompareAndClassifyInputValidator:
    """Rejects A11 input.criteria with duplicate ids before any provider call is made -
    a duplicate id would make the output.deltas full-coverage check ambiguous."""

    def validate(self, *, input_payload: Mapping[str, Any]) -> None:
        criteria = input_payload.get("criteria")
        if not isinstance(criteria, list):
            return
        seen_ids: set[str] = set()
        for criterion in criteria:
            if not isinstance(criterion, Mapping):
                continue
            criterion_id = criterion.get("id")
            if not isinstance(criterion_id, str):
                continue
            if criterion_id in seen_ids:
                raise ActionInputValidationError(
                    f"Action input validation failed: duplicate criteria[*].id '{criterion_id}'."
                )
            seen_ids.add(criterion_id)


class CompareAndClassifyCrossValidator:
    """Validates A11 output.verdict/deltas against the dynamic categories/criteria from A11
    input: verdict must be one of input.categories, and deltas must cover every
    input.criteria id exactly once (existence + uniqueness + full coverage)."""

    def validate(
        self,
        *,
        input_payload: Mapping[str, Any],
        output: Mapping[str, Any] | None,
    ) -> None:
        output = _require_output(output)
        verdict = output.get("verdict")
        allowed_categories = _optional_membership_set(input_payload.get("categories"))
        if allowed_categories is not None and verdict not in allowed_categories:
            raise _cross_validation_error(
                f"verdict_not_in_categories:{_truncated_repr(verdict)}"
            )

        criteria = input_payload.get("criteria")
        if not isinstance(criteria, list):
            return
        known_criterion_ids: set[str] = set()
        for criterion in criteria:
            if isinstance(criterion, Mapping) and isinstance(criterion.get("id"), str):
                known_criterion_ids.add(criterion["id"])

        deltas = output.get("deltas")
        if not isinstance(deltas, list):
            raise _cross_validation_error("malformed_compare_and_classify_output")

        seen_criterion_ids: set[str] = set()
        for delta in deltas:
            if not isinstance(delta, Mapping):
                raise _cross_validation_error("malformed_delta_entry")
            criterion_id = delta.get("criterion_id")
            if criterion_id not in known_criterion_ids:
                raise _cross_validation_error(
                    f"delta_criterion_id_not_in_criteria:{_truncated_repr(criterion_id)}"
                )
            if criterion_id in seen_criterion_ids:
                raise _cross_validation_error(
                    f"duplicate_delta_criterion_id:{_truncated_repr(criterion_id)}"
                )
            seen_criterion_ids.add(criterion_id)

        missing_criterion_ids = known_criterion_ids - seen_criterion_ids
        if missing_criterion_ids:
            raise _cross_validation_error(
                "deltas_missing_criteria:" + ",".join(sorted(missing_criterion_ids))
            )
