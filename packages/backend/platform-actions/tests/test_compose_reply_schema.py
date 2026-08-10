from __future__ import annotations

import pytest
from jsonschema import ValidationError, validate

from schema_support import load_schema as _schema

COMPOSE_REPLY_INPUT = _schema("compose_reply_input.schema.json")
COMPOSE_REPLY_OUTPUT = _schema("compose_reply_output.schema.json")


class TestComposeReplyInputSchema:
    def test_minimal_valid_input(self) -> None:
        validate(
            instance={
                "situation": "The client asked for a status update on the project.",
                "intent": "Reassure the client and confirm the new delivery date.",
                "tone": "neutral",
            },
            schema=COMPOSE_REPLY_INPUT,
        )

    def test_full_valid_input(self) -> None:
        validate(
            instance={
                "situation": "The client asked for a status update on the project.",
                "intent": "Reassure the client and confirm the new delivery date.",
                "tone": "warm",
                "constraints": {
                    "language": "en-US",
                    "max_length": 500,
                    "output_format": "markdown",
                },
            },
            schema=COMPOSE_REPLY_INPUT,
        )

    def test_missing_required_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "situation": "The client asked for a status update.",
                    "tone": "neutral",
                },
                schema=COMPOSE_REPLY_INPUT,
            )

    def test_empty_situation_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"situation": "", "intent": "Confirm the date.", "tone": "neutral"},
                schema=COMPOSE_REPLY_INPUT,
            )

    def test_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "situation": "The client asked for a status update.",
                    "intent": "Confirm the date.",
                    "tone": "neutral",
                    "recipient_name": "Alex",
                },
                schema=COMPOSE_REPLY_INPUT,
            )

    def test_invalid_tone_enum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "situation": "The client asked for a status update.",
                    "intent": "Confirm the date.",
                    "tone": "apologetic",
                },
                schema=COMPOSE_REPLY_INPUT,
            )

    def test_unexpected_constraints_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "situation": "The client asked for a status update.",
                    "intent": "Confirm the date.",
                    "tone": "neutral",
                    "constraints": {"tone_override": "casual"},
                },
                schema=COMPOSE_REPLY_INPUT,
            )

    def test_invalid_max_length_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "situation": "The client asked for a status update.",
                    "intent": "Confirm the date.",
                    "tone": "neutral",
                    "constraints": {"max_length": 0},
                },
                schema=COMPOSE_REPLY_INPUT,
            )

    def test_max_length_above_output_text_limit_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "situation": "The client asked for a status update.",
                    "intent": "Confirm the date.",
                    "tone": "neutral",
                    "constraints": {"max_length": 4001},
                },
                schema=COMPOSE_REPLY_INPUT,
            )

    def test_max_length_at_output_text_limit_allowed(self) -> None:
        validate(
            instance={
                "situation": "The client asked for a status update.",
                "intent": "Confirm the date.",
                "tone": "neutral",
                "constraints": {"max_length": 4000},
            },
            schema=COMPOSE_REPLY_INPUT,
        )


class TestComposeReplyOutputSchema:
    def test_minimal_valid_output(self) -> None:
        validate(instance={"text": "The revised draft will be with you by Friday."}, schema=COMPOSE_REPLY_OUTPUT)

    def test_full_valid_output(self) -> None:
        validate(
            instance={
                "text": "The revised draft will be with you by Friday.",
                "call_to_action": "Let me know if Friday doesn't work.",
            },
            schema=COMPOSE_REPLY_OUTPUT,
        )

    def test_missing_required_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(instance={"call_to_action": "Let me know."}, schema=COMPOSE_REPLY_OUTPUT)

    def test_empty_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(instance={"text": ""}, schema=COMPOSE_REPLY_OUTPUT)

    def test_empty_call_to_action_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"text": "The revised draft will be with you by Friday.", "call_to_action": ""},
                schema=COMPOSE_REPLY_OUTPUT,
            )

    def test_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "text": "The revised draft will be with you by Friday.",
                    "tone_achieved": "warm",
                },
                schema=COMPOSE_REPLY_OUTPUT,
            )

    def test_text_exceeding_max_length_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(instance={"text": "x" * 4001}, schema=COMPOSE_REPLY_OUTPUT)
