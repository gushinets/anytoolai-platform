from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_ROOT = REPO_ROOT / "configs" / "kernel" / "schemas"


def _schema(name: str) -> dict:
    return json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8"))


COMPARE_CLASSIFY_INPUT = _schema("compare_classify_input.schema.json")
COMPARE_CLASSIFY_OUTPUT = _schema("compare_classify_output.schema.json")

_CRITERION = {"id": "tone", "description": "Matches the reference tone."}
_MINIMAL_INPUT = {
    "subject_text": "Subject copy",
    "reference_text": "Reference copy",
    "categories": ["meets_bar", "below_bar"],
    "criteria": [_CRITERION],
}
_DELTA = {"criterion_id": "tone", "status": "match", "evidence": "e"}
_MINIMAL_OUTPUT = {
    "verdict": "meets_bar",
    "confidence": 0.8,
    "deltas": [_DELTA],
    "rationale": "r",
}


def test_input_minimal_valid() -> None:
    validate(instance=_MINIMAL_INPUT, schema=COMPARE_CLASSIFY_INPUT)


def test_input_full_valid() -> None:
    validate(
        instance={
            **_MINIMAL_INPUT,
            "criteria": [
                {**_CRITERION, "weight": 2.5},
                {"id": "coverage", "description": "Covers the required topics."},
            ],
        },
        schema=COMPARE_CLASSIFY_INPUT,
    )


def test_input_missing_required_field_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(
            instance={k: v for k, v in _MINIMAL_INPUT.items() if k != "criteria"},
            schema=COMPARE_CLASSIFY_INPUT,
        )


def test_input_unexpected_property_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(instance={**_MINIMAL_INPUT, "extra": "nope"}, schema=COMPARE_CLASSIFY_INPUT)


def test_input_unexpected_criterion_property_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(
            instance={**_MINIMAL_INPUT, "criteria": [{**_CRITERION, "score": 1}]},
            schema=COMPARE_CLASSIFY_INPUT,
        )


def test_input_empty_subject_text_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(instance={**_MINIMAL_INPUT, "subject_text": ""}, schema=COMPARE_CLASSIFY_INPUT)


def test_input_empty_reference_text_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(instance={**_MINIMAL_INPUT, "reference_text": ""}, schema=COMPARE_CLASSIFY_INPUT)


def test_input_single_category_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(
            instance={**_MINIMAL_INPUT, "categories": ["only_one"]},
            schema=COMPARE_CLASSIFY_INPUT,
        )


def test_input_duplicate_categories_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(
            instance={**_MINIMAL_INPUT, "categories": ["a", "a"]},
            schema=COMPARE_CLASSIFY_INPUT,
        )


def test_input_empty_criteria_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(instance={**_MINIMAL_INPUT, "criteria": []}, schema=COMPARE_CLASSIFY_INPUT)


def test_input_criterion_missing_description_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(
            instance={**_MINIMAL_INPUT, "criteria": [{"id": "tone"}]},
            schema=COMPARE_CLASSIFY_INPUT,
        )


def test_input_criterion_zero_weight_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(
            instance={**_MINIMAL_INPUT, "criteria": [{**_CRITERION, "weight": 0}]},
            schema=COMPARE_CLASSIFY_INPUT,
        )


def test_input_criterion_negative_weight_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(
            instance={**_MINIMAL_INPUT, "criteria": [{**_CRITERION, "weight": -1}]},
            schema=COMPARE_CLASSIFY_INPUT,
        )


def test_output_minimal_valid() -> None:
    validate(instance=_MINIMAL_OUTPUT, schema=COMPARE_CLASSIFY_OUTPUT)


def test_output_missing_required_field_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(
            instance={k: v for k, v in _MINIMAL_OUTPUT.items() if k != "confidence"},
            schema=COMPARE_CLASSIFY_OUTPUT,
        )


def test_output_unexpected_property_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(instance={**_MINIMAL_OUTPUT, "extra": "nope"}, schema=COMPARE_CLASSIFY_OUTPUT)


def test_output_unexpected_delta_property_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(
            instance={**_MINIMAL_OUTPUT, "deltas": [{**_DELTA, "score": 1}]},
            schema=COMPARE_CLASSIFY_OUTPUT,
        )


def test_output_empty_verdict_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(instance={**_MINIMAL_OUTPUT, "verdict": ""}, schema=COMPARE_CLASSIFY_OUTPUT)


def test_output_confidence_below_zero_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(instance={**_MINIMAL_OUTPUT, "confidence": -0.1}, schema=COMPARE_CLASSIFY_OUTPUT)


def test_output_confidence_above_one_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(instance={**_MINIMAL_OUTPUT, "confidence": 1.1}, schema=COMPARE_CLASSIFY_OUTPUT)


def test_output_confidence_bounds_allowed() -> None:
    validate(instance={**_MINIMAL_OUTPUT, "confidence": 0}, schema=COMPARE_CLASSIFY_OUTPUT)
    validate(instance={**_MINIMAL_OUTPUT, "confidence": 1}, schema=COMPARE_CLASSIFY_OUTPUT)


def test_output_empty_deltas_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(instance={**_MINIMAL_OUTPUT, "deltas": []}, schema=COMPARE_CLASSIFY_OUTPUT)


def test_output_invalid_delta_status_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(
            instance={**_MINIMAL_OUTPUT, "deltas": [{**_DELTA, "status": "unknown"}]},
            schema=COMPARE_CLASSIFY_OUTPUT,
        )


def test_output_empty_delta_evidence_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(
            instance={**_MINIMAL_OUTPUT, "deltas": [{**_DELTA, "evidence": ""}]},
            schema=COMPARE_CLASSIFY_OUTPUT,
        )


def test_output_rationale_exceeding_max_length_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(
            instance={**_MINIMAL_OUTPUT, "rationale": "x" * 501},
            schema=COMPARE_CLASSIFY_OUTPUT,
        )


def test_output_rationale_at_max_length_allowed() -> None:
    validate(
        instance={**_MINIMAL_OUTPUT, "rationale": "x" * 500},
        schema=COMPARE_CLASSIFY_OUTPUT,
    )
