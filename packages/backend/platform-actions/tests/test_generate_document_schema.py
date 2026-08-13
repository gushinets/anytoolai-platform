from __future__ import annotations

import pytest
from jsonschema import ValidationError, validate

from schema_support import load_schema as _schema

GENERATE_DOCUMENT_INPUT = _schema("generate_document_input.schema.json")
GENERATE_DOCUMENT_OUTPUT = _schema("generate_document_output.schema.json")


class TestGenerateDocumentInputSchema:
    def test_minimal_valid_input(self) -> None:
        validate(
            instance={"template_ref": "kernel_demo.report_v1", "data": {}},
            schema=GENERATE_DOCUMENT_INPUT,
        )

    def test_full_valid_input(self) -> None:
        validate(
            instance={
                "template_ref": "kernel_demo.report_v1",
                "data": {"source_text": "...", "extracted": {"values": {}}, "issues": {"issues": []}},
                "style": "detailed",
            },
            schema=GENERATE_DOCUMENT_INPUT,
        )

    def test_missing_required_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(instance={"data": {}}, schema=GENERATE_DOCUMENT_INPUT)

    def test_empty_template_ref_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"template_ref": "", "data": {}},
                schema=GENERATE_DOCUMENT_INPUT,
            )

    def test_whitespace_only_template_ref_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"template_ref": "   ", "data": {}},
                schema=GENERATE_DOCUMENT_INPUT,
            )

    def test_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "template_ref": "kernel_demo.report_v1",
                    "data": {},
                    "product_slug": "freelancer",
                },
                schema=GENERATE_DOCUMENT_INPUT,
            )

    def test_invalid_style_enum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "template_ref": "kernel_demo.report_v1",
                    "data": {},
                    "style": "casual",
                },
                schema=GENERATE_DOCUMENT_INPUT,
            )


class TestGenerateDocumentOutputSchema:
    def test_minimal_valid_output(self) -> None:
        validate(
            instance={
                "sections": [{"id": "overview", "title": "Overview", "content": "All set."}],
                "summary": "All set.",
            },
            schema=GENERATE_DOCUMENT_OUTPUT,
        )

    def test_full_valid_output(self) -> None:
        validate(
            instance={
                "sections": [
                    {
                        "id": "risks",
                        "title": "Risks",
                        "content": "Timeline is underspecified.",
                        "metadata": {"kind": "note"},
                    }
                ],
                "summary": "One open risk.",
            },
            schema=GENERATE_DOCUMENT_OUTPUT,
        )

    def test_missing_required_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"sections": [{"id": "a", "title": "A", "content": "c"}]},
                schema=GENERATE_DOCUMENT_OUTPUT,
            )

    def test_empty_sections_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(instance={"sections": [], "summary": "Empty."}, schema=GENERATE_DOCUMENT_OUTPUT)

    def test_section_missing_required_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"sections": [{"id": "a", "title": "A"}], "summary": "s"},
                schema=GENERATE_DOCUMENT_OUTPUT,
            )

    def test_unexpected_property_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "sections": [{"id": "a", "title": "A", "content": "c"}],
                    "summary": "s",
                    "word_count": 42,
                },
                schema=GENERATE_DOCUMENT_OUTPUT,
            )

    def test_invalid_section_metadata_kind_enum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "sections": [
                        {"id": "a", "title": "A", "content": "c", "metadata": {"kind": "banner"}}
                    ],
                    "summary": "s",
                },
                schema=GENERATE_DOCUMENT_OUTPUT,
            )

    def test_empty_section_metadata_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "sections": [{"id": "a", "title": "A", "content": "c", "metadata": {}}],
                    "summary": "s",
                },
                schema=GENERATE_DOCUMENT_OUTPUT,
            )

    def test_malformed_section_missing_content_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={"sections": [{"id": "a", "title": "A", "content": ""}], "summary": "s"},
                schema=GENERATE_DOCUMENT_OUTPUT,
            )

    def test_whitespace_only_section_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "sections": [{"id": "   ", "title": "A", "content": "c"}],
                    "summary": "s",
                },
                schema=GENERATE_DOCUMENT_OUTPUT,
            )

    def test_whitespace_only_section_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "sections": [{"id": "a", "title": "   ", "content": "c"}],
                    "summary": "s",
                },
                schema=GENERATE_DOCUMENT_OUTPUT,
            )

    def test_whitespace_only_section_content_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "sections": [{"id": "a", "title": "A", "content": "   "}],
                    "summary": "s",
                },
                schema=GENERATE_DOCUMENT_OUTPUT,
            )

    def test_whitespace_only_summary_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate(
                instance={
                    "sections": [{"id": "a", "title": "A", "content": "c"}],
                    "summary": "   ",
                },
                schema=GENERATE_DOCUMENT_OUTPUT,
            )
