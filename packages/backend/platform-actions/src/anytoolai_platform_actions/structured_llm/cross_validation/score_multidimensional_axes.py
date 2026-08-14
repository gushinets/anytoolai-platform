from __future__ import annotations

from typing import Any, Mapping

from ._shared import (
    _cross_validation_error,
    _is_finite_number,
    _reject_duplicate_ids,
    _require_output,
    _truncated_repr,
)


class ScoreMultidimensionalAxesInputValidator:
    """Rejects semantically ambiguous A03 input.axes before any provider call is made."""

    def validate(self, *, input_payload: Mapping[str, Any]) -> None:
        _reject_duplicate_ids(
            input_payload.get("axes"), id_field="id", error_label="axes[*].id"
        )


class ScoreMultidimensionalAxesCrossValidator:
    """Validates A03 output.scores/dominant_axes/weakest_axes against the dynamic axes from
    A03 input.axes: every axis_id must map exactly once onto an input axis (exists + unique +
    exhaustive), and dominant_axes/weakest_axes must equal the tie-preserving, input-order set
    of axis ids at the max/min reported score, recomputed outside the model response."""

    def validate(
        self,
        *,
        input_payload: Mapping[str, Any],
        output: Mapping[str, Any] | None,
    ) -> None:
        output = _require_output(output)
        axes = input_payload.get("axes")
        if not isinstance(axes, list):
            return
        axis_order: list[str] = []
        known_axis_ids: set[str] = set()
        for axis in axes:
            if isinstance(axis, Mapping) and isinstance(axis.get("id"), str):
                axis_order.append(axis["id"])
                known_axis_ids.add(axis["id"])
        if not axis_order:
            return

        scores = output.get("scores")
        if not isinstance(scores, list):
            raise _cross_validation_error("malformed_score_multidim_output")

        score_by_axis: dict[str, float] = {}
        for entry in scores:
            if not isinstance(entry, Mapping):
                raise _cross_validation_error("malformed_score_entry")
            axis_id = entry.get("axis_id")
            if axis_id not in known_axis_ids:
                raise _cross_validation_error(
                    f"axis_id_not_in_axes:{_truncated_repr(axis_id)}"
                )
            if axis_id in score_by_axis:
                raise _cross_validation_error(
                    f"duplicate_axis_id:{_truncated_repr(axis_id)}"
                )
            score = entry.get("score")
            if not _is_finite_number(score):
                raise _cross_validation_error(f"invalid_axis_score:{_truncated_repr(score)}")
            score_by_axis[axis_id] = score

        missing_axis_ids = known_axis_ids - score_by_axis.keys()
        if missing_axis_ids:
            raise _cross_validation_error(
                "axes_missing_from_scores:" + ",".join(sorted(missing_axis_ids))
            )

        max_score = max(score_by_axis.values())
        min_score = min(score_by_axis.values())
        expected_dominant = [aid for aid in axis_order if score_by_axis[aid] == max_score]
        expected_weakest = [aid for aid in axis_order if score_by_axis[aid] == min_score]

        dominant_axes = output.get("dominant_axes")
        if dominant_axes != expected_dominant:
            raise _cross_validation_error(
                f"dominant_axes_mismatch:{_truncated_repr(dominant_axes)}"
            )
        weakest_axes = output.get("weakest_axes")
        if weakest_axes != expected_weakest:
            raise _cross_validation_error(
                f"weakest_axes_mismatch:{_truncated_repr(weakest_axes)}"
            )
