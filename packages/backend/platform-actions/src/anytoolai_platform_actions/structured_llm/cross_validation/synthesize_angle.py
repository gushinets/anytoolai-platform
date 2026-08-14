from __future__ import annotations

from typing import Any, Mapping

from ._shared import (
    _cross_validation_error,
    _optional_membership_set,
    _require_output,
    _truncated_repr,
)


class SynthesizeAngleCrossValidator:
    """Validates A09 output.angle/secondary_angle against the options from A09 input.options."""

    def validate(
        self,
        *,
        input_payload: Mapping[str, Any],
        output: Mapping[str, Any] | None,
    ) -> None:
        output = _require_output(output)
        allowed_options = _optional_membership_set(input_payload.get("options"))
        if allowed_options is None:
            return
        angle = output.get("angle")
        if angle not in allowed_options:
            raise _cross_validation_error(f"angle_not_in_options:{_truncated_repr(angle)}")
        secondary_angle = output.get("secondary_angle")
        if secondary_angle is not None and secondary_angle not in allowed_options:
            raise _cross_validation_error(
                f"secondary_angle_not_in_options:{_truncated_repr(secondary_angle)}"
            )
