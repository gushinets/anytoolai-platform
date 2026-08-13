from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_ROOT = REPO_ROOT / "configs" / "kernel" / "schemas"


def _schema(name: str) -> dict:
    return json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8"))


COMPOSE_PERSUASIVE_TEXT_INPUT = _schema("compose_persuasive_text_input.schema.json")
COMPOSE_PERSUASIVE_TEXT_OUTPUT = _schema("compose_persuasive_text_output.schema.json")


class TestComposePersuasiveTextInputSchema:
    def test_minimal_valid_input(self) -> None:
        validate(
            instance={
                "context": {"product": "Widget Pro", "deadline": "March"},
                "objective": "Convince the reader to upgrade before March.",
            },
            schema=COMPOSE_PERSUASIVE_TEXT_INPUT,
        )

    def test_full_valid_input(self) -> None:
        validate(
            instance={
                "context": {"product": "Widget Pro", "deadline": "March", "discount_pct": 20},
                "objective": "Convince the reader to upgrade before March.",
                "audience": "Existing customers on the legacy plan.",
                "angle": "Limited-time discount expiring at quarter end.",
                "constraints": {
                    "tone": "warm",
                    "length": 500,
                    "language": "en-US",
                    "format": "markdown",
                },
            },
            schema=COMPOSE_PERSUASIVE_TEXT_INPUT,
        )

    def test_missing_required_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"context": {"product": "Widget Pro"}},
                schema=COMPOSE_PERSUASIVE_TEXT_INPUT,
            )

    def test_empty_objective_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"context": {"product": "Widget Pro"}, "objective": ""},
                schema=COMPOSE_PERSUASIVE_TEXT_INPUT,
            )

    def test_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "context": {"product": "Widget Pro"},
                    "objective": "Convince the reader to upgrade.",
                    "product_name": "Widget Pro",
                },
                schema=COMPOSE_PERSUASIVE_TEXT_INPUT,
            )

    def test_invalid_tone_enum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "context": {"product": "Widget Pro"},
                    "objective": "Convince the reader to upgrade.",
                    "constraints": {"tone": "aggressive"},
                },
                schema=COMPOSE_PERSUASIVE_TEXT_INPUT,
            )

    def test_unexpected_constraints_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "context": {"product": "Widget Pro"},
                    "objective": "Convince the reader to upgrade.",
                    "constraints": {"anti_ai": True},
                },
                schema=COMPOSE_PERSUASIVE_TEXT_INPUT,
            )

    def test_invalid_length_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "context": {"product": "Widget Pro"},
                    "objective": "Convince the reader to upgrade.",
                    "constraints": {"length": 0},
                },
                schema=COMPOSE_PERSUASIVE_TEXT_INPUT,
            )

    def test_length_above_output_text_limit_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "context": {"product": "Widget Pro"},
                    "objective": "Convince the reader to upgrade.",
                    "constraints": {"length": 4001},
                },
                schema=COMPOSE_PERSUASIVE_TEXT_INPUT,
            )

    def test_length_at_output_text_limit_allowed(self) -> None:
        validate(
            instance={
                "context": {"product": "Widget Pro"},
                "objective": "Convince the reader to upgrade.",
                "constraints": {"length": 4000},
            },
            schema=COMPOSE_PERSUASIVE_TEXT_INPUT,
        )

    def test_context_wrong_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"context": "Widget Pro", "objective": "Convince the reader."},
                schema=COMPOSE_PERSUASIVE_TEXT_INPUT,
            )


class TestComposePersuasiveTextOutputSchema:
    def test_minimal_valid_output(self) -> None:
        validate(
            instance={"text": "Upgrade before March to lock in this quarter's rate."},
            schema=COMPOSE_PERSUASIVE_TEXT_OUTPUT,
        )

    def test_missing_required_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(instance={}, schema=COMPOSE_PERSUASIVE_TEXT_OUTPUT)

    def test_empty_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(instance={"text": ""}, schema=COMPOSE_PERSUASIVE_TEXT_OUTPUT)

    def test_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "text": "Upgrade before March.",
                    "word_count": 4,
                },
                schema=COMPOSE_PERSUASIVE_TEXT_OUTPUT,
            )

    def test_text_exceeding_max_length_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(instance={"text": "x" * 4001}, schema=COMPOSE_PERSUASIVE_TEXT_OUTPUT)
