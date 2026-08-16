from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_ROOT = REPO_ROOT / "configs" / "kernel" / "schemas"


def _schema(name: str) -> dict:
    return json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8"))


SCORE_MATCH_INPUT = _schema("score_match_input.schema.json")
SCORE_MATCH_OUTPUT = _schema("score_match_output.schema.json")

_RUBRIC_ITEM = {"id": "tone", "description": "Matches the requested tone.", "weight": 1}


class TestScoreMatchByRubricInputSchema:
    def test_minimal_valid_input(self) -> None:
        validate(
            instance={"text_a": "Source text.", "text_b": "Candidate text.", "rubric": [_RUBRIC_ITEM]},
            schema=SCORE_MATCH_INPUT,
        )

    def test_full_valid_input(self) -> None:
        validate(
            instance={
                "text_a": "Source text.",
                "text_b": "Candidate text.",
                "rubric": [
                    _RUBRIC_ITEM,
                    {"id": "completeness", "description": "Covers all key points.", "weight": 2.5},
                ],
            },
            schema=SCORE_MATCH_INPUT,
        )

    def test_missing_required_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(instance={"text_a": "a", "text_b": "b"}, schema=SCORE_MATCH_INPUT)

    def test_empty_text_a_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"text_a": "", "text_b": "b", "rubric": [_RUBRIC_ITEM]},
                schema=SCORE_MATCH_INPUT,
            )

    def test_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "text_a": "a",
                    "text_b": "b",
                    "rubric": [_RUBRIC_ITEM],
                    "product_hint": "freelancer",
                },
                schema=SCORE_MATCH_INPUT,
            )

    def test_empty_rubric_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"text_a": "a", "text_b": "b", "rubric": []},
                schema=SCORE_MATCH_INPUT,
            )

    def test_rubric_item_missing_description_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "text_a": "a",
                    "text_b": "b",
                    "rubric": [{"id": "tone", "weight": 1}],
                },
                schema=SCORE_MATCH_INPUT,
            )

    def test_rubric_item_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "text_a": "a",
                    "text_b": "b",
                    "rubric": [{**_RUBRIC_ITEM, "category": "style"}],
                },
                schema=SCORE_MATCH_INPUT,
            )

    def test_rubric_item_zero_weight_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "text_a": "a",
                    "text_b": "b",
                    "rubric": [{**_RUBRIC_ITEM, "weight": 0}],
                },
                schema=SCORE_MATCH_INPUT,
            )

    def test_rubric_item_negative_weight_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "text_a": "a",
                    "text_b": "b",
                    "rubric": [{**_RUBRIC_ITEM, "weight": -1}],
                },
                schema=SCORE_MATCH_INPUT,
            )


class TestScoreMatchByRubricOutputSchema:
    _CRITERION_SCORE = {"criterion_id": "tone", "score": 80, "rationale": "Matches well."}

    def test_minimal_valid_output(self) -> None:
        validate(
            instance={
                "criterion_scores": [self._CRITERION_SCORE],
                "score": 80,
                "strengths": [],
                "gaps": [],
            },
            schema=SCORE_MATCH_OUTPUT,
        )

    def test_full_valid_output(self) -> None:
        validate(
            instance={
                "criterion_scores": [self._CRITERION_SCORE],
                "score": 80,
                "strengths": ["Tone matches closely."],
                "gaps": ["Missing budget detail."],
            },
            schema=SCORE_MATCH_OUTPUT,
        )

    def test_missing_required_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(instance={"criterion_scores": [self._CRITERION_SCORE], "score": 80}, schema=SCORE_MATCH_OUTPUT)

    def test_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "criterion_scores": [self._CRITERION_SCORE],
                    "score": 80,
                    "strengths": [],
                    "gaps": [],
                    "confidence": 0.9,
                },
                schema=SCORE_MATCH_OUTPUT,
            )

    def test_empty_criterion_scores_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"criterion_scores": [], "score": 80, "strengths": [], "gaps": []},
                schema=SCORE_MATCH_OUTPUT,
            )

    def test_criterion_score_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "criterion_scores": [{**self._CRITERION_SCORE, "score": 101}],
                    "score": 80,
                    "strengths": [],
                    "gaps": [],
                },
                schema=SCORE_MATCH_OUTPUT,
            )

    def test_aggregate_score_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "criterion_scores": [self._CRITERION_SCORE],
                    "score": -1,
                    "strengths": [],
                    "gaps": [],
                },
                schema=SCORE_MATCH_OUTPUT,
            )

    def test_empty_strength_string_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "criterion_scores": [self._CRITERION_SCORE],
                    "score": 80,
                    "strengths": [""],
                    "gaps": [],
                },
                schema=SCORE_MATCH_OUTPUT,
            )

    def test_criterion_score_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "criterion_scores": [{**self._CRITERION_SCORE, "confidence": 0.9}],
                    "score": 80,
                    "strengths": [],
                    "gaps": [],
                },
                schema=SCORE_MATCH_OUTPUT,
            )
