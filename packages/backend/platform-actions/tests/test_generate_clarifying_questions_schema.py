from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_ROOT = REPO_ROOT / "configs" / "kernel" / "schemas"


def _schema(name: str) -> dict:
    return json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8"))


QUESTIONS_INPUT = _schema("generate_questions_input.schema.json")
QUESTIONS_OUTPUT = _schema("generate_questions_output.schema.json")

_ISSUE = {"category": "timeline", "description": "Delivery date not specified.", "severity": "high"}


class TestGenerateClarifyingQuestionsInputSchema:
    def test_minimal_valid_input(self) -> None:
        validate(
            instance={
                "issues": [_ISSUE],
                "context": "Client project kickoff conversation.",
                "target_audience": "client stakeholder",
            },
            schema=QUESTIONS_INPUT,
        )

    def test_full_valid_input(self) -> None:
        validate(
            instance={
                "issues": [_ISSUE, {**_ISSUE, "category": "scope", "evidence": "quote"}],
                "context": "Client project kickoff conversation.",
                "target_audience": "client stakeholder",
                "max_questions": 3,
            },
            schema=QUESTIONS_INPUT,
        )

    def test_missing_required_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"issues": [_ISSUE], "context": "context"},
                schema=QUESTIONS_INPUT,
            )

    def test_empty_issues_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"issues": [], "context": "context", "target_audience": "audience"},
                schema=QUESTIONS_INPUT,
            )

    def test_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "issues": [_ISSUE],
                    "context": "context",
                    "target_audience": "audience",
                    "product": "not allowed",
                },
                schema=QUESTIONS_INPUT,
            )

    def test_unexpected_issue_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "issues": [{**_ISSUE, "resolved": True}],
                    "context": "context",
                    "target_audience": "audience",
                },
                schema=QUESTIONS_INPUT,
            )

    def test_invalid_issue_severity_enum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "issues": [{**_ISSUE, "severity": "critical"}],
                    "context": "context",
                    "target_audience": "audience",
                },
                schema=QUESTIONS_INPUT,
            )

    def test_max_questions_below_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "issues": [_ISSUE],
                    "context": "context",
                    "target_audience": "audience",
                    "max_questions": 0,
                },
                schema=QUESTIONS_INPUT,
            )

    def test_max_questions_above_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "issues": [_ISSUE],
                    "context": "context",
                    "target_audience": "audience",
                    "max_questions": 11,
                },
                schema=QUESTIONS_INPUT,
            )

    def test_max_questions_at_bounds_allowed(self) -> None:
        for value in (1, 10):
            validate(
                instance={
                    "issues": [_ISSUE],
                    "context": "context",
                    "target_audience": "audience",
                    "max_questions": value,
                },
                schema=QUESTIONS_INPUT,
            )


class TestGenerateClarifyingQuestionsOutputSchema:
    _QUESTION = {
        "question": "What is the exact delivery date?",
        "rationale": "The timeline issue has no concrete date to plan around.",
        "priority": "high",
        "category": "timeline",
        "source_issue_index": 0,
    }

    def test_empty_questions_is_valid(self) -> None:
        validate(instance={"questions": []}, schema=QUESTIONS_OUTPUT)

    def test_full_valid_output(self) -> None:
        validate(
            instance={
                "questions": [
                    self._QUESTION,
                    {**self._QUESTION, "priority": "medium", "source_issue_index": 1},
                ]
            },
            schema=QUESTIONS_OUTPUT,
        )

    def test_missing_required_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            question = dict(self._QUESTION)
            del question["rationale"]
            validate(instance={"questions": [question]}, schema=QUESTIONS_OUTPUT)

    def test_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"questions": [{**self._QUESTION, "answer_hint": "not allowed"}]},
                schema=QUESTIONS_OUTPUT,
            )

    def test_invalid_priority_enum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"questions": [{**self._QUESTION, "priority": "urgent"}]},
                schema=QUESTIONS_OUTPUT,
            )

    def test_negative_source_issue_index_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"questions": [{**self._QUESTION, "source_issue_index": -1}]},
                schema=QUESTIONS_OUTPUT,
            )

    def test_empty_question_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"questions": [{**self._QUESTION, "question": ""}]},
                schema=QUESTIONS_OUTPUT,
            )

    def test_more_than_ten_questions_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "questions": [
                        {**self._QUESTION, "source_issue_index": i} for i in range(11)
                    ]
                },
                schema=QUESTIONS_OUTPUT,
            )
