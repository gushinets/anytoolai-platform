from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_ROOT = REPO_ROOT / "configs" / "kernel" / "schemas"


def _schema(name: str) -> dict:
    return json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8"))


SCORE_MULTIDIM_INPUT = _schema("score_multidim_input.schema.json")
SCORE_MULTIDIM_OUTPUT = _schema("score_multidim_output.schema.json")

_AXIS = {"id": "clarity", "description": "How clearly the text states its point."}


class TestScoreMultidimensionalAxesInputSchema:
    def test_minimal_valid_input(self) -> None:
        validate(instance={"text": "Some text.", "axes": [_AXIS]}, schema=SCORE_MULTIDIM_INPUT)

    def test_full_valid_input(self) -> None:
        validate(
            instance={
                "text": "Some text.",
                "axes": [
                    {**_AXIS, "weight": 1},
                    {"id": "structure", "description": "How well organized the text is.", "weight": 2.5},
                ],
            },
            schema=SCORE_MULTIDIM_INPUT,
        )

    def test_missing_required_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(instance={"text": "Some text."}, schema=SCORE_MULTIDIM_INPUT)

    def test_empty_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(instance={"text": "", "axes": [_AXIS]}, schema=SCORE_MULTIDIM_INPUT)

    def test_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"text": "Some text.", "axes": [_AXIS], "product_hint": "freelancer"},
                schema=SCORE_MULTIDIM_INPUT,
            )

    def test_empty_axes_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(instance={"text": "Some text.", "axes": []}, schema=SCORE_MULTIDIM_INPUT)

    def test_axis_missing_description_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"text": "Some text.", "axes": [{"id": "clarity"}]},
                schema=SCORE_MULTIDIM_INPUT,
            )

    def test_axis_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"text": "Some text.", "axes": [{**_AXIS, "category": "style"}]},
                schema=SCORE_MULTIDIM_INPUT,
            )

    def test_axis_zero_weight_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"text": "Some text.", "axes": [{**_AXIS, "weight": 0}]},
                schema=SCORE_MULTIDIM_INPUT,
            )

    def test_axis_negative_weight_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"text": "Some text.", "axes": [{**_AXIS, "weight": -1}]},
                schema=SCORE_MULTIDIM_INPUT,
            )


class TestScoreMultidimensionalAxesOutputSchema:
    _SCORE = {"axis_id": "clarity", "score": 8, "commentary": "States its point directly."}

    def test_minimal_valid_output(self) -> None:
        validate(
            instance={"scores": [self._SCORE], "dominant_axes": ["clarity"], "weakest_axes": ["clarity"]},
            schema=SCORE_MULTIDIM_OUTPUT,
        )

    def test_full_valid_output(self) -> None:
        second_score = {"axis_id": "structure", "score": 5, "commentary": "Lacks clear breaks."}
        validate(
            instance={
                "scores": [self._SCORE, second_score],
                "dominant_axes": ["clarity"],
                "weakest_axes": ["structure"],
            },
            schema=SCORE_MULTIDIM_OUTPUT,
        )

    def test_tied_dominant_axes_allowed(self) -> None:
        tied_score = {"axis_id": "structure", "score": 8, "commentary": "Also strong."}
        validate(
            instance={
                "scores": [self._SCORE, tied_score],
                "dominant_axes": ["clarity", "structure"],
                "weakest_axes": ["clarity", "structure"],
            },
            schema=SCORE_MULTIDIM_OUTPUT,
        )

    def test_missing_required_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(instance={"scores": [self._SCORE], "dominant_axes": ["clarity"]}, schema=SCORE_MULTIDIM_OUTPUT)

    def test_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "scores": [self._SCORE],
                    "dominant_axes": ["clarity"],
                    "weakest_axes": ["clarity"],
                    "confidence": 0.9,
                },
                schema=SCORE_MULTIDIM_OUTPUT,
            )

    def test_empty_scores_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"scores": [], "dominant_axes": ["clarity"], "weakest_axes": ["clarity"]},
                schema=SCORE_MULTIDIM_OUTPUT,
            )

    def test_empty_dominant_axes_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"scores": [self._SCORE], "dominant_axes": [], "weakest_axes": ["clarity"]},
                schema=SCORE_MULTIDIM_OUTPUT,
            )

    def test_empty_weakest_axes_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"scores": [self._SCORE], "dominant_axes": ["clarity"], "weakest_axes": []},
                schema=SCORE_MULTIDIM_OUTPUT,
            )

    def test_score_below_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "scores": [{**self._SCORE, "score": 0}],
                    "dominant_axes": ["clarity"],
                    "weakest_axes": ["clarity"],
                },
                schema=SCORE_MULTIDIM_OUTPUT,
            )

    def test_score_above_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "scores": [{**self._SCORE, "score": 11}],
                    "dominant_axes": ["clarity"],
                    "weakest_axes": ["clarity"],
                },
                schema=SCORE_MULTIDIM_OUTPUT,
            )

    def test_empty_commentary_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "scores": [{**self._SCORE, "commentary": ""}],
                    "dominant_axes": ["clarity"],
                    "weakest_axes": ["clarity"],
                },
                schema=SCORE_MULTIDIM_OUTPUT,
            )

    def test_score_entry_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "scores": [{**self._SCORE, "confidence": 0.9}],
                    "dominant_axes": ["clarity"],
                    "weakest_axes": ["clarity"],
                },
                schema=SCORE_MULTIDIM_OUTPUT,
            )
