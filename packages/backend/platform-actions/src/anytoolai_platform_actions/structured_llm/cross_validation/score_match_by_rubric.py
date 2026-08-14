from __future__ import annotations

import math
from typing import Any, Mapping

from anytoolai_platform_core.actions.runner import ActionInputValidationError

from ._shared import _cross_validation_error, _is_finite_number, _require_output, _truncated_repr


class ScoreMatchByRubricInputValidator:
    """Rejects semantically ambiguous A02 input.rubric before any provider call is made."""

    def validate(self, *, input_payload: Mapping[str, Any]) -> None:
        rubric = input_payload.get("rubric")
        if not isinstance(rubric, list):
            return
        seen_ids: set[str] = set()
        for criterion in rubric:
            if not isinstance(criterion, Mapping):
                continue
            criterion_id = criterion.get("id")
            if not isinstance(criterion_id, str):
                continue
            if criterion_id in seen_ids:
                raise ActionInputValidationError(
                    f"Action input validation failed: duplicate rubric[*].id '{criterion_id}'."
                )
            seen_ids.add(criterion_id)
            # Schema only enforces `weight > 0` with no upper bound, so a JSON literal like
            # `1e309` parses to `inf` and passes schema validation. Reject it here, before any
            # provider call, instead of only in ScoreMatchByRubricCrossValidator - otherwise
            # every PydanticAI validation retry re-invokes the provider against the same
            # unchanged input and fails identically, wasting real provider calls.
            if not _is_finite_number(criterion.get("weight")):
                raise ActionInputValidationError(
                    f"Action input validation failed: rubric[*].weight for '{criterion_id}' "
                    "must be a finite number."
                )


# No existing rubric-weighted-aggregate precedent in this module (every prior cross
# validator does membership/bounds/regex checks, not arithmetic), so this tolerance has no
# codebase default to match. 0.5 covers the model rounding a weighted average to the
# nearest whole point on the 0-100 scale without masking a genuinely wrong aggregate.
# Derived from the prompt's rounding instruction in
# configs/kernel/products/kernel_demo/prompts/score_match_by_rubric.v1.md ("rounded to the
# nearest whole number") -
# TestScoreMatchByRubricAggregateToleranceMatchesPrompt::test_prompt_still_instructs_rounding_to_nearest_whole_number
# in test_cross_validation.py pins that exact phrase so a prompt-side rounding change (e.g.
# to nearest 5 points) can't drift out of sync with this constant unnoticed.
_SCORE_MATCH_AGGREGATE_TOLERANCE = 0.5


class ScoreMatchByRubricCrossValidator:
    """Validates A02 output.criterion_scores/score against the dynamic rubric from A02
    input.rubric: every criterion_id must map exactly once to a rubric item (exists +
    unique + exhaustive), and the aggregate `score` must match the rubric-weighted average
    of criterion_scores within tolerance, recomputed outside the model response."""

    def validate(
        self,
        *,
        input_payload: Mapping[str, Any],
        output: Mapping[str, Any] | None,
    ) -> None:
        output = _require_output(output)
        rubric = input_payload.get("rubric")
        if not isinstance(rubric, list):
            return
        rubric_weights: dict[str, float] = {}
        for criterion in rubric:
            if not isinstance(criterion, Mapping):
                continue
            criterion_id = criterion.get("id")
            if not isinstance(criterion_id, str):
                continue
            weight = criterion.get("weight")
            # Schema only enforces `weight > 0` with no upper bound, so a JSON literal like
            # `1e309` parses to `inf` and passes schema validation. Silently dropping such
            # entries here (instead of failing closed) would validate output against a
            # truncated rubric - or, if every weight overflows, skip cross-validation for
            # this call entirely via the `not rubric_weights` early return below.
            if not _is_finite_number(weight):
                raise _cross_validation_error(
                    f"rubric_weight_not_finite:{criterion_id}:{_truncated_repr(weight)}"
                )
            rubric_weights[criterion_id] = float(weight)
        if not rubric_weights:
            return
        # Summed from the deduplicated dict, not accumulated alongside it - a duplicate
        # rubric id must count once (last write wins, matching rubric_weights) rather than
        # inflating the denominator against a numerator that only sees the deduped weight.
        total_weight = sum(rubric_weights.values())

        criterion_scores = output.get("criterion_scores")
        if not isinstance(criterion_scores, list):
            raise _cross_validation_error("malformed_score_match_output")

        seen_ids: set[str] = set()
        weighted_sum = 0.0
        for entry in criterion_scores:
            if not isinstance(entry, Mapping):
                raise _cross_validation_error("malformed_criterion_score_entry")
            criterion_id = entry.get("criterion_id")
            if not isinstance(criterion_id, str):
                raise _cross_validation_error(
                    f"invalid_criterion_id:{_truncated_repr(criterion_id)}"
                )
            weight = rubric_weights.get(criterion_id)
            if weight is None:
                raise _cross_validation_error(
                    f"criterion_id_not_in_rubric:{_truncated_repr(criterion_id)}"
                )
            if criterion_id in seen_ids:
                raise _cross_validation_error(
                    f"duplicate_criterion_id:{_truncated_repr(criterion_id)}"
                )
            seen_ids.add(criterion_id)
            score = entry.get("score")
            if not _is_finite_number(score):
                raise _cross_validation_error(
                    f"invalid_criterion_score:{_truncated_repr(score)}"
                )
            weighted_sum += weight * float(score)

        missing_ids = rubric_weights.keys() - seen_ids
        if missing_ids:
            raise _cross_validation_error(
                "rubric_criteria_missing_from_output:" + ",".join(sorted(missing_ids))
            )

        # Schema enforces `weight > 0` per rubric item, but that only holds when validate()
        # runs through the executor after schema validation - a direct caller (e.g. a test,
        # or a future non-schema-gated wiring) could still reach total_weight == 0.
        if total_weight == 0:
            raise _cross_validation_error("aggregate_total_weight_is_zero")
        expected_score = weighted_sum / total_weight
        # Individually-finite weights can still overflow float64 to `inf` once summed/
        # multiplied (schema only enforces `weight > 0`, no upper bound), producing
        # `inf / inf = nan`. Every comparison against `nan` is False in Python, so without
        # this check a `nan` expected_score would silently accept any reported_score.
        if not math.isfinite(expected_score):
            raise _cross_validation_error(
                f"aggregate_expected_score_not_finite:{_truncated_repr(expected_score)}"
            )
        reported_score = output.get("score")
        if not _is_finite_number(reported_score):
            raise _cross_validation_error(
                f"invalid_aggregate_score:{_truncated_repr(reported_score)}"
            )
        if abs(float(reported_score) - expected_score) > _SCORE_MATCH_AGGREGATE_TOLERANCE:
            raise _cross_validation_error(
                f"aggregate_score_mismatch:{reported_score}!={expected_score:.4f}"
            )
