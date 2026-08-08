from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_ROOT = REPO_ROOT / "configs" / "kernel" / "schemas"


def _schema(name: str) -> dict:
    return json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8"))


EXTRACT_INPUT = _schema("extract_input.schema.json")
EXTRACT_OUTPUT = _schema("extract_output.schema.json")
ISSUE_INPUT = _schema("issue_detection_input.schema.json")
ISSUE_OUTPUT = _schema("issue_detection_output.schema.json")


class TestExtractInputSchema:
    def test_minimal_valid_input(self) -> None:
        validate(
            instance={
                "source_text": "text",
                "fields": [
                    {"name": "deadline", "type": "string", "description": "d", "required": True}
                ],
            },
            schema=EXTRACT_INPUT,
        )

    def test_full_valid_input(self) -> None:
        validate(
            instance={
                "source_text": "text",
                "fields": [
                    {"name": "deadline", "type": "string", "description": "d", "required": True},
                    {"name": "budget", "type": "number", "description": "b", "required": False},
                ],
                "strict": True,
            },
            schema=EXTRACT_INPUT,
        )

    def test_missing_required_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(instance={"source_text": "text"}, schema=EXTRACT_INPUT)

    def test_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "source_text": "text",
                    "fields": [
                        {"name": "deadline", "type": "string", "description": "d", "required": True}
                    ],
                    "field_names": ["deadline"],
                },
                schema=EXTRACT_INPUT,
            )

    def test_invalid_field_type_enum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "source_text": "text",
                    "fields": [
                        {"name": "deadline", "type": "not_a_type", "description": "d", "required": True}
                    ],
                },
                schema=EXTRACT_INPUT,
            )

    def test_empty_fields_array_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(instance={"source_text": "text", "fields": []}, schema=EXTRACT_INPUT)


class TestExtractOutputSchema:
    def test_minimal_valid_output(self) -> None:
        validate(instance={"values": {}, "missing_fields": ["deadline"]}, schema=EXTRACT_OUTPUT)

    def test_full_valid_output(self) -> None:
        validate(
            instance={
                "values": {"deadline": "Friday"},
                "missing_fields": [],
                "confidence": {"deadline": 0.8},
            },
            schema=EXTRACT_OUTPUT,
        )

    def test_missing_required_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(instance={"values": {}}, schema=EXTRACT_OUTPUT)

    def test_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"values": {}, "missing_fields": [], "title": "not allowed"},
                schema=EXTRACT_OUTPUT,
            )

    def test_confidence_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"values": {}, "missing_fields": [], "confidence": {"deadline": 1.5}},
                schema=EXTRACT_OUTPUT,
            )


class TestIssueDetectionInputSchema:
    def test_minimal_valid_input(self) -> None:
        validate(instance={"source_text": "text"}, schema=ISSUE_INPUT)

    def test_full_valid_input(self) -> None:
        validate(
            instance={
                "source_text": "text",
                "context": "extra context",
                "taxonomy": ["timeline", "scope"],
            },
            schema=ISSUE_INPUT,
        )

    def test_missing_required_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(instance={"taxonomy": ["timeline"]}, schema=ISSUE_INPUT)

    def test_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"source_text": "text", "categories": ["timeline"]},
                schema=ISSUE_INPUT,
            )

    def test_empty_taxonomy_allowed(self) -> None:
        validate(instance={"source_text": "text", "taxonomy": []}, schema=ISSUE_INPUT)


class TestIssueDetectionOutputSchema:
    def test_empty_issues_is_valid(self) -> None:
        validate(instance={"issues": []}, schema=ISSUE_OUTPUT)

    def test_multi_category_multi_severity_valid(self) -> None:
        validate(
            instance={
                "issues": [
                    {"category": "timeline", "description": "d1", "severity": "high"},
                    {"category": "scope", "description": "d2", "severity": "low", "evidence": "quote"},
                    {"category": "budget", "description": "d3", "severity": "medium"},
                ]
            },
            schema=ISSUE_OUTPUT,
        )

    def test_missing_required_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"issues": [{"category": "timeline", "severity": "high"}]},
                schema=ISSUE_OUTPUT,
            )

    def test_invalid_severity_enum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "issues": [
                        {"category": "timeline", "description": "d", "severity": "critical"}
                    ]
                },
                schema=ISSUE_OUTPUT,
            )

    def test_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "issues": [
                        {
                            "category": "timeline",
                            "description": "d",
                            "severity": "high",
                            "issue": "legacy field",
                        }
                    ]
                },
                schema=ISSUE_OUTPUT,
            )
