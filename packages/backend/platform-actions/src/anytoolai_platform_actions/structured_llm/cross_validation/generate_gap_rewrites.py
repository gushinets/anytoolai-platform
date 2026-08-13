from __future__ import annotations

from typing import Any, Mapping

from ._shared import (
    _coerce_integer_valued,
    _cross_validation_error,
    _require_output,
    _truncated_repr,
)

# Must match the "default" declared in generate_gap_rewrites_input.schema.json's `n` property
# (asserted by test_generate_gap_rewrites_schema.py) — jsonschema validation does not apply
# JSON Schema defaults to the payload, so this is the actual runtime default, not the schema.
GAP_REWRITES_DEFAULT_N = 3


def _normalized_for_distinctness(text: str) -> str:
    """Whitespace-collapsed, case-insensitive form used to detect near-duplicate rewrites."""
    return " ".join(text.split()).casefold()


class GapRewritesCrossValidator:
    """Validates A08 output.rewrites/best_pick: item count must equal the requested A08
    input.n (default 3), rewrites must be distinct after whitespace/case normalization, and
    best_pick must index into rewrites."""

    def validate(
        self,
        *,
        input_payload: Mapping[str, Any],
        output: Mapping[str, Any] | None,
    ) -> None:
        output = _require_output(output)
        requested_n = _coerce_integer_valued(input_payload.get("n", GAP_REWRITES_DEFAULT_N))
        if requested_n is None:
            requested_n = GAP_REWRITES_DEFAULT_N

        rewrites = output.get("rewrites")
        if not isinstance(rewrites, list):
            raise _cross_validation_error("malformed_gap_rewrites_output")
        if len(rewrites) != requested_n:
            raise _cross_validation_error(
                f"rewrite_count_mismatch:{len(rewrites)}!={requested_n}"
            )

        seen_normalized: set[str] = set()
        for rewrite in rewrites:
            if not isinstance(rewrite, Mapping):
                raise _cross_validation_error("malformed_rewrite_entry")
            text = rewrite.get("text")
            if not isinstance(text, str):
                raise _cross_validation_error("malformed_rewrite_text")
            normalized = _normalized_for_distinctness(text)
            if normalized in seen_normalized:
                raise _cross_validation_error("duplicate_rewrite_after_normalization")
            seen_normalized.add(normalized)

        best_pick = _coerce_integer_valued(output.get("best_pick"))
        if best_pick is None or not (0 <= best_pick < len(rewrites)):
            raise _cross_validation_error(
                f"best_pick_out_of_bounds:{_truncated_repr(output.get('best_pick'))}"
            )
