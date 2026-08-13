from __future__ import annotations

from typing import Any, Mapping

from ._shared import (
    _cross_validation_error,
    _optional_membership_set,
    _require_output,
    _truncated_repr,
)


class DetectIssuesByTaxonomyCrossValidator:
    """Validates A04 output.issues categories against the taxonomy from A04 input.taxonomy."""

    def validate(
        self,
        *,
        input_payload: Mapping[str, Any],
        output: Mapping[str, Any] | None,
    ) -> None:
        output = _require_output(output)
        allowed_categories = _optional_membership_set(input_payload.get("taxonomy"))
        if allowed_categories is None:
            return
        issues = output.get("issues")
        if not isinstance(issues, list):
            raise _cross_validation_error("malformed_issue_detection_output")
        for issue in issues:
            if not isinstance(issue, Mapping):
                raise _cross_validation_error("malformed_issue_entry")
            category = issue.get("category")
            if category not in allowed_categories:
                raise _cross_validation_error(
                    f"category_not_in_taxonomy:{_truncated_repr(category)}"
                )
