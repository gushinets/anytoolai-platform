from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_ROOT = REPO_ROOT / "configs" / "kernel" / "schemas"


def _schema(name: str) -> dict:
    return json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8"))


SYNTHESIZE_ANGLE_INPUT = _schema("synthesize_angle_input.schema.json")
SYNTHESIZE_ANGLE_OUTPUT = _schema("synthesize_angle_output.schema.json")

_SIGNAL = {"id": "s1", "label": "Timeline gap", "value": "unconfirmed deadline"}


def test_input_minimal_valid() -> None:
    validate(
        instance={"signals": [_SIGNAL], "objective": "Win the deal"},
        schema=SYNTHESIZE_ANGLE_INPUT,
    )


def test_input_full_valid() -> None:
    validate(
        instance={
            "signals": [
                {**_SIGNAL, "evidence": "We haven't heard back on dates."},
                {"id": "s2", "label": "Budget confirmed", "value": 5000},
            ],
            "objective": "Win the deal",
            "options": ["Lead with urgency", "Lead with value"],
        },
        schema=SYNTHESIZE_ANGLE_INPUT,
    )


@pytest.mark.parametrize(
    "value",
    ["a string", 5000, 5.5, True, False, None, ["array", "value"], {"nested": "object"}],
)
def test_input_signal_value_accepts_any_json_type(value: object) -> None:
    validate(
        instance={
            "signals": [{"id": "s1", "label": "Signal", "value": value}],
            "objective": "Win the deal",
        },
        schema=SYNTHESIZE_ANGLE_INPUT,
    )


def test_input_missing_required_field_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(instance={"signals": [_SIGNAL]}, schema=SYNTHESIZE_ANGLE_INPUT)


def test_input_unexpected_property_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(
            instance={
                "signals": [_SIGNAL],
                "objective": "Win the deal",
                "goal_enum": "close_deal",
            },
            schema=SYNTHESIZE_ANGLE_INPUT,
        )


def test_input_unexpected_signal_property_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(
            instance={
                "signals": [{**_SIGNAL, "confidence": 0.9}],
                "objective": "Win the deal",
            },
            schema=SYNTHESIZE_ANGLE_INPUT,
        )


def test_input_empty_signals_array_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(
            instance={"signals": [], "objective": "Win the deal"},
            schema=SYNTHESIZE_ANGLE_INPUT,
        )


def test_input_empty_objective_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(
            instance={"signals": [_SIGNAL], "objective": ""},
            schema=SYNTHESIZE_ANGLE_INPUT,
        )


def test_input_duplicate_options_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(
            instance={
                "signals": [_SIGNAL],
                "objective": "Win the deal",
                "options": ["A", "A"],
            },
            schema=SYNTHESIZE_ANGLE_INPUT,
        )


def test_input_empty_options_allowed_as_open_synthesis() -> None:
    validate(
        instance={"signals": [_SIGNAL], "objective": "Win the deal", "options": []},
        schema=SYNTHESIZE_ANGLE_INPUT,
    )


def test_output_minimal_valid() -> None:
    validate(instance={"angle": "Lead with urgency", "rationale": "r"}, schema=SYNTHESIZE_ANGLE_OUTPUT)


def test_output_full_valid() -> None:
    validate(
        instance={
            "angle": "Lead with urgency",
            "rationale": "r",
            "secondary_angle": "Lead with value",
        },
        schema=SYNTHESIZE_ANGLE_OUTPUT,
    )


def test_output_missing_required_field_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(instance={"angle": "Lead with urgency"}, schema=SYNTHESIZE_ANGLE_OUTPUT)


def test_output_unexpected_property_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(
            instance={
                "angle": "Lead with urgency",
                "rationale": "r",
                "goal": "close_deal",
            },
            schema=SYNTHESIZE_ANGLE_OUTPUT,
        )


def test_output_empty_angle_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(instance={"angle": "", "rationale": "r"}, schema=SYNTHESIZE_ANGLE_OUTPUT)


def test_output_empty_secondary_angle_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(
            instance={"angle": "Lead with urgency", "rationale": "r", "secondary_angle": ""},
            schema=SYNTHESIZE_ANGLE_OUTPUT,
        )


def test_output_rationale_exceeding_max_length_rejected() -> None:
    with pytest.raises(ValidationError):
        validate(
            instance={"angle": "Lead with urgency", "rationale": "x" * 501},
            schema=SYNTHESIZE_ANGLE_OUTPUT,
        )


def test_output_rationale_at_max_length_allowed() -> None:
    validate(
        instance={"angle": "Lead with urgency", "rationale": "x" * 500},
        schema=SYNTHESIZE_ANGLE_OUTPUT,
    )
