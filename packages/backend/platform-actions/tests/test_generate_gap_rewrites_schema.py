from __future__ import annotations

import json
from pathlib import Path

import pytest
from anytoolai_platform_actions.structured_llm.cross_validation import GAP_REWRITES_DEFAULT_N
from jsonschema import ValidationError, validate

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_ROOT = REPO_ROOT / "configs" / "kernel" / "schemas"


def _schema(name: str) -> dict:
    return json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8"))


GENERATE_GAP_REWRITES_INPUT = _schema("generate_gap_rewrites_input.schema.json")
GENERATE_GAP_REWRITES_OUTPUT = _schema("generate_gap_rewrites_output.schema.json")

_REWRITE = {
    "text": "The proposal includes a fixed delivery date of March 15.",
    "explanation": "States a concrete delivery date to close the timeline gap.",
    "change_made": "Added an explicit delivery date.",
}


class TestGenerateGapRewritesInputSchema:
    def test_minimal_valid_input(self) -> None:
        validate(
            instance={
                "source_text": "We will deliver the project soon.",
                "gap": "No concrete delivery date is given.",
                "style": "moderate",
            },
            schema=GENERATE_GAP_REWRITES_INPUT,
        )

    def test_full_valid_input(self) -> None:
        validate(
            instance={
                "source_text": "We will deliver the project soon.",
                "gap": "No concrete delivery date is given.",
                "n": 5,
                "style": "bold",
            },
            schema=GENERATE_GAP_REWRITES_INPUT,
        )

    def test_missing_required_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"source_text": "text", "gap": "gap"},
                schema=GENERATE_GAP_REWRITES_INPUT,
            )

    def test_empty_source_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"source_text": "", "gap": "gap", "style": "moderate"},
                schema=GENERATE_GAP_REWRITES_INPUT,
            )

    def test_empty_gap_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"source_text": "text", "gap": "", "style": "moderate"},
                schema=GENERATE_GAP_REWRITES_INPUT,
            )

    def test_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "source_text": "text",
                    "gap": "gap",
                    "style": "moderate",
                    "tone": "warm",
                },
                schema=GENERATE_GAP_REWRITES_INPUT,
            )

    def test_invalid_style_enum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"source_text": "text", "gap": "gap", "style": "aggressive"},
                schema=GENERATE_GAP_REWRITES_INPUT,
            )

    @pytest.mark.parametrize("n", [0, 6, -1])
    def test_n_out_of_range_rejected(self, n: int) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"source_text": "text", "gap": "gap", "style": "moderate", "n": n},
                schema=GENERATE_GAP_REWRITES_INPUT,
            )

    @pytest.mark.parametrize("n", [1, 5])
    def test_n_at_bounds_allowed(self, n: int) -> None:
        validate(
            instance={"source_text": "text", "gap": "gap", "style": "moderate", "n": n},
            schema=GENERATE_GAP_REWRITES_INPUT,
        )

    def test_declared_default_matches_cross_validator_runtime_default(self) -> None:
        # jsonschema validation does not apply JSON Schema "default" to the payload, so the
        # schema's declared default is documentation only — GapRewritesCrossValidator's
        # GAP_REWRITES_DEFAULT_N is the actual runtime default. Keep them in sync.
        assert GENERATE_GAP_REWRITES_INPUT["properties"]["n"]["default"] == GAP_REWRITES_DEFAULT_N


class TestGenerateGapRewritesOutputSchema:
    def test_minimal_valid_output(self) -> None:
        validate(
            instance={"rewrites": [_REWRITE], "best_pick": 0},
            schema=GENERATE_GAP_REWRITES_OUTPUT,
        )

    def test_full_valid_output(self) -> None:
        validate(
            instance={"rewrites": [_REWRITE, _REWRITE, _REWRITE], "best_pick": 2},
            schema=GENERATE_GAP_REWRITES_OUTPUT,
        )

    def test_missing_required_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(instance={"rewrites": [_REWRITE]}, schema=GENERATE_GAP_REWRITES_OUTPUT)

    def test_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"rewrites": [_REWRITE], "best_pick": 0, "reasoning": "chain of thought"},
                schema=GENERATE_GAP_REWRITES_OUTPUT,
            )

    def test_empty_rewrites_array_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(instance={"rewrites": [], "best_pick": 0}, schema=GENERATE_GAP_REWRITES_OUTPUT)

    def test_rewrites_above_max_items_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"rewrites": [_REWRITE] * 6, "best_pick": 0},
                schema=GENERATE_GAP_REWRITES_OUTPUT,
            )

    def test_negative_best_pick_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"rewrites": [_REWRITE], "best_pick": -1},
                schema=GENERATE_GAP_REWRITES_OUTPUT,
            )

    @pytest.mark.parametrize("missing_key", ["text", "explanation", "change_made"])
    def test_rewrite_missing_required_field_rejected(self, missing_key: str) -> None:
        rewrite = {key: value for key, value in _REWRITE.items() if key != missing_key}
        with pytest.raises(ValidationError):
            validate(
                instance={"rewrites": [rewrite], "best_pick": 0},
                schema=GENERATE_GAP_REWRITES_OUTPUT,
            )

    def test_rewrite_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "rewrites": [{**_REWRITE, "confidence": 0.9}],
                    "best_pick": 0,
                },
                schema=GENERATE_GAP_REWRITES_OUTPUT,
            )

    def test_rewrite_empty_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"rewrites": [{**_REWRITE, "text": ""}], "best_pick": 0},
                schema=GENERATE_GAP_REWRITES_OUTPUT,
            )
