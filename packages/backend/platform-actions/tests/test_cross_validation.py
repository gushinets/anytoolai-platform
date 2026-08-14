from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pytest
from anytoolai_platform_actions.structured_llm.cross_validation import (
    ComposeReplyCrossValidator,
    DetectIssuesByTaxonomyCrossValidator,
    ExtractStructuredFieldsCrossValidator,
    ExtractStructuredFieldsInputValidator,
    GenerateClarifyingQuestionsCrossValidator,
    ScoreMatchByRubricCrossValidator,
    ScoreMatchByRubricInputValidator,
    SynthesizeAngleCrossValidator,
    PersuasiveTextCrossValidator,
)
from anytoolai_platform_core.actions.runner import ActionInputValidationError
from anytoolai_platform_core.structured_output.errors import StructuredOutputValidationError


def _field(name: str, field_type: str, *, required: bool) -> dict:
    return {
        "name": name,
        "type": field_type,
        "description": f"{name} field",
        "required": required,
    }


class TestExtractStructuredFieldsInputValidator:
    def setup_method(self) -> None:
        self.validator = ExtractStructuredFieldsInputValidator()

    def test_accepts_unique_field_names(self) -> None:
        self.validator.validate(
            input_payload={
                "fields": [
                    _field("deadline", "string", required=True),
                    _field("budget", "number", required=False),
                ],
            }
        )

    def test_rejects_duplicate_field_names_even_with_different_types(self) -> None:
        with pytest.raises(ActionInputValidationError):
            self.validator.validate(
                input_payload={
                    "fields": [
                        _field("deadline", "string", required=True),
                        _field("deadline", "number", required=False),
                    ],
                }
            )

    def test_ignores_non_list_fields_payload(self) -> None:
        self.validator.validate(input_payload={"fields": "not-a-list"})


class TestExtractStructuredFieldsCrossValidator:
    def setup_method(self) -> None:
        self.validator = ExtractStructuredFieldsCrossValidator()

    def test_accepts_matching_typed_values(self) -> None:
        self.validator.validate(
            input_payload={
                "fields": [
                    _field("deadline", "string", required=True),
                    _field("budget", "number", required=False),
                ],
            },
            output={
                "values": {"deadline": "next Friday", "budget": 500},
                "missing_fields": [],
            },
        )

    def test_accepts_partial_result_with_missing_fields_reported(self) -> None:
        self.validator.validate(
            input_payload={
                "fields": [
                    _field("deadline", "string", required=True),
                    _field("budget", "number", required=False),
                ],
                "strict": False,
            },
            output={
                "values": {"deadline": "next Friday"},
                "missing_fields": ["budget"],
            },
        )

    def test_rejects_unknown_field_type_instead_of_skipping_the_check(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"fields": [_field("deadline", "timestamp", required=False)]},
                output={"values": {"deadline": "anything at all"}, "missing_fields": []},
            )

    def test_rejects_unknown_field_type_even_when_reported_in_missing_fields(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"fields": [_field("deadline", "timestamp", required=False)]},
                output={"values": {}, "missing_fields": ["deadline"]},
            )

    def test_rejects_duplicate_entries_in_missing_fields(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"fields": [_field("deadline", "string", required=False)]},
                output={"values": {}, "missing_fields": ["deadline", "deadline"]},
            )

    def test_rejects_type_mismatch(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"fields": [_field("budget", "number", required=False)]},
                output={"values": {"budget": "not a number"}, "missing_fields": []},
            )

    def test_rejects_non_finite_number_from_exponent_overflow(self) -> None:
        # json.loads("1e309") overflows to float("inf") via ordinary float parsing, not the
        # NaN/Infinity/-Infinity literal tokens parse_strict_json's parse_constant intercepts, so
        # this must be caught by the field type check itself, not by JSON parsing.
        overflowed = json.loads("1e309")
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"fields": [_field("budget", "number", required=False)]},
                output={"values": {"budget": overflowed}, "missing_fields": []},
            )

    def test_accepts_large_but_finite_number(self) -> None:
        self.validator.validate(
            input_payload={"fields": [_field("budget", "number", required=False)]},
            output={"values": {"budget": 1e100}, "missing_fields": []},
        )

    def test_accepts_valid_iso_date(self) -> None:
        self.validator.validate(
            input_payload={"fields": [_field("deadline", "date", required=False)]},
            output={"values": {"deadline": "2026-08-07"}, "missing_fields": []},
        )

    @pytest.mark.parametrize(
        "value",
        [
            "banana",
            "2026-13-40",
            "08/07/2026",
            "2026-8-7",
            "next Friday",
        ],
    )
    def test_rejects_non_iso_date_values(self, value: str) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"fields": [_field("deadline", "date", required=False)]},
                output={"values": {"deadline": value}, "missing_fields": []},
            )

    def test_rejects_value_for_unrequested_field(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"fields": [_field("deadline", "string", required=True)]},
                output={
                    "values": {"deadline": "Friday", "extra": "unexpected"},
                    "missing_fields": [],
                },
            )

    def test_rejects_field_marked_both_present_and_missing(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"fields": [_field("deadline", "string", required=True)]},
                output={
                    "values": {"deadline": "Friday"},
                    "missing_fields": ["deadline"],
                },
            )

    def test_strict_true_requires_all_required_fields_present(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={
                    "fields": [_field("deadline", "string", required=True)],
                    "strict": True,
                },
                output={"values": {}, "missing_fields": ["deadline"]},
            )

    def test_strict_false_allows_missing_required_fields(self) -> None:
        self.validator.validate(
            input_payload={
                "fields": [_field("deadline", "string", required=True)],
                "strict": False,
            },
            output={"values": {}, "missing_fields": ["deadline"]},
        )

    def test_rejects_requested_field_missing_from_both_values_and_missing_fields(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={
                    "fields": [
                        _field("deadline", "string", required=True),
                        _field("budget", "number", required=False),
                    ],
                },
                output={"values": {"deadline": "Friday"}, "missing_fields": []},
            )

    def test_rejects_confidence_for_field_absent_from_values(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"fields": [_field("deadline", "string", required=True)]},
                output={
                    "values": {},
                    "missing_fields": ["deadline"],
                    "confidence": {"deadline": 0.9},
                },
            )

    def test_accepts_confidence_only_for_populated_fields(self) -> None:
        self.validator.validate(
            input_payload={"fields": [_field("deadline", "string", required=True)]},
            output={
                "values": {"deadline": "Friday"},
                "missing_fields": [],
                "confidence": {"deadline": 0.9},
            },
        )

    def test_rejects_duplicate_field_names_in_input(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={
                    "fields": [
                        _field("deadline", "string", required=True),
                        _field("deadline", "string", required=False),
                    ],
                },
                output={"values": {"deadline": "Friday"}, "missing_fields": []},
            )

    def test_array_of_strings_type_check(self) -> None:
        self.validator.validate(
            input_payload={"fields": [_field("deliverables", "array_of_strings", required=False)]},
            output={"values": {"deliverables": ["logo", "site"]}, "missing_fields": []},
        )
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"fields": [_field("deliverables", "array_of_strings", required=False)]},
                output={"values": {"deliverables": "not a list"}, "missing_fields": []},
            )

    def test_truncates_rejected_unrequested_field_name_in_error_reason(self) -> None:
        overlong_name = "x" * 500
        with pytest.raises(StructuredOutputValidationError) as exc_info:
            self.validator.validate(
                input_payload={"fields": [_field("deadline", "string", required=True)]},
                output={
                    "values": {"deadline": "Friday", overlong_name: "anything"},
                    "missing_fields": [],
                },
            )
        assert len(exc_info.value.reason) < len(overlong_name)
        assert exc_info.value.reason.endswith("...")


class TestDetectIssuesByTaxonomyCrossValidator:
    def setup_method(self) -> None:
        self.validator = DetectIssuesByTaxonomyCrossValidator()

    def test_accepts_category_within_taxonomy(self) -> None:
        self.validator.validate(
            input_payload={"taxonomy": ["timeline", "scope"]},
            output={"issues": [{"category": "timeline", "description": "d", "severity": "high"}]},
        )

    def test_rejects_category_outside_taxonomy(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"taxonomy": ["timeline"]},
                output={"issues": [{"category": "scope", "description": "d", "severity": "high"}]},
            )

    def test_allows_free_form_category_when_taxonomy_omitted(self) -> None:
        self.validator.validate(
            input_payload={},
            output={"issues": [{"category": "anything", "description": "d", "severity": "low"}]},
        )

    def test_allows_empty_issues_list(self) -> None:
        self.validator.validate(
            input_payload={"taxonomy": ["timeline"]},
            output={"issues": []},
        )

    def test_truncates_rejected_category_in_error_reason(self) -> None:
        overlong_category = "x" * 500
        with pytest.raises(StructuredOutputValidationError) as exc_info:
            self.validator.validate(
                input_payload={"taxonomy": ["timeline"]},
                output={
                    "issues": [
                        {"category": overlong_category, "description": "d", "severity": "low"}
                    ]
                },
            )
        assert len(exc_info.value.reason) < len(overlong_category)
        assert exc_info.value.reason.endswith("...")


class TestSynthesizeAngleCrossValidator:
    def setup_method(self) -> None:
        self.validator = SynthesizeAngleCrossValidator()

    def test_allows_open_synthesis_when_options_omitted(self) -> None:
        self.validator.validate(
            input_payload={},
            output={"angle": "Anything the model chooses", "rationale": "r"},
        )

    def test_allows_open_synthesis_when_options_empty(self) -> None:
        self.validator.validate(
            input_payload={"options": []},
            output={"angle": "Anything the model chooses", "rationale": "r"},
        )

    def test_accepts_angle_within_options(self) -> None:
        self.validator.validate(
            input_payload={"options": ["Lead with urgency", "Lead with value"]},
            output={"angle": "Lead with urgency", "rationale": "r"},
        )

    def test_rejects_angle_outside_options(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"options": ["Lead with urgency", "Lead with value"]},
                output={"angle": "Something else entirely", "rationale": "r"},
            )

    def test_accepts_secondary_angle_within_options(self) -> None:
        self.validator.validate(
            input_payload={"options": ["Lead with urgency", "Lead with value"]},
            output={
                "angle": "Lead with urgency",
                "rationale": "r",
                "secondary_angle": "Lead with value",
            },
        )

    def test_rejects_secondary_angle_outside_options(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"options": ["Lead with urgency", "Lead with value"]},
                output={
                    "angle": "Lead with urgency",
                    "rationale": "r",
                    "secondary_angle": "Something else entirely",
                },
            )

    def test_ignores_missing_secondary_angle_when_options_supplied(self) -> None:
        self.validator.validate(
            input_payload={"options": ["Lead with urgency"]},
            output={"angle": "Lead with urgency", "rationale": "r"},
        )

    def test_truncates_rejected_angle_in_error_reason(self) -> None:
        overlong_angle = "x" * 500
        with pytest.raises(StructuredOutputValidationError) as exc_info:
            self.validator.validate(
                input_payload={"options": ["Lead with urgency"]},
                output={"angle": overlong_angle, "rationale": "r"},
            )
        assert len(exc_info.value.reason) < len(overlong_angle)
        assert exc_info.value.reason.endswith("...")


class TestComposeReplyCrossValidator:
    def setup_method(self) -> None:
        self.validator = ComposeReplyCrossValidator()

    @pytest.mark.parametrize(
        ("input_payload", "output"),
        [
            ({}, {"text": "Plain reply."}),
            ({"constraints": {"max_length": 20}}, {"text": "Short reply."}),
            (
                {"constraints": {"max_length": True}},
                {"text": "This reply is longer than one character."},
            ),
            ({"constraints": {"output_format": "plain_text"}}, {"text": "Plain reply."}),
            (
                {"constraints": {"output_format": "html"}},
                {"text": "Reply with <b>markup</b>."},
            ),
            (
                {"constraints": {"output_format": "markdown"}},
                {"text": "**Bold** reply with *markdown* markers."},
            ),
            # An unpaired asterisk is common casual usage (multiplication, footnotes), not
            # markdown emphasis.
            ({}, {"text": "5 * 3 is 15, not * asterisk footnote."}),
            # Unspaced arithmetic/dimension expressions aren't markdown italic either, even
            # though CommonMark's real intraword-emphasis rule for `*` would otherwise flag
            # them - numeric, variable, and symbolic alike.
            ({}, {"text": "2*3*4"}),
            ({}, {"text": "Use 2*4*8 packing."}),
            ({}, {"text": "a*b*c"}),
            ({}, {"text": "L*W*H"}),
            ({}, {"text": "2*x*4"}),
            # Unicode-aware: non-ASCII alphanumeric flanking (Cyrillic, Greek, CJK) must be
            # excluded too, not only ASCII letters/digits.
            ({}, {"text": "Д*Ш*В"}),
            ({}, {"text": "α*β*γ"}),
            ({}, {"text": "宽*高*深"}),
            # A base letter followed by a combining diacritic (NFD form) must still count as
            # flanking material, not only precomposed (NFC) letters.
            ({}, {"text": unicodedata.normalize("NFD", "café*2*")}),
            # Scripts with no precomposed base+mark form at all (Hebrew niqud, Arabic tashkil,
            # Devanagari matras, ...) - not just NFD-decomposable Latin - must flank correctly
            # too. A single combining mark (niqud) between the base letter and `*`:
            ({}, {"text": "בָ*2*3"}),
            # Two stacked combining marks (niqud + shin dot) - the walk-back must skip past
            # both, not stop at the first one, to reach the alphanumeric base letter.
            ({}, {"text": "בָׁ*2*3"}),
            ({}, {"text": "Plain reply.", "call_to_action": "Book a call."}),
            # Any real HTML5 construct - not just a fixed set of "common" tag names -
            # satisfies "html", via a real tokenizer rather than a name allowlist.
            (
                {"constraints": {"output_format": "html"}},
                {"text": "Use the <kbd>Enter</kbd> key."},
            ),
            (
                {"constraints": {"output_format": "html"}},
                {"text": "Reply with <script>alert(1)</script>."},
            ),
            (
                {"constraints": {"output_format": "html"}},
                {"text": "Custom <x-card>widget</x-card>."},
            ),
        ],
    )
    def test_accepts(self, input_payload: dict, output: dict) -> None:
        self.validator.validate(input_payload=input_payload, output=output)

    @pytest.mark.parametrize(
        ("input_payload", "output"),
        [
            ({"constraints": {"max_length": 5}}, {"text": "This reply is too long."}),
            (
                {"constraints": {"output_format": "plain_text"}},
                {"text": "Reply with <b>markup</b>."},
            ),
            ({"constraints": {}}, {"text": "Reply with <b>markup</b>."}),
            ({}, {"text": "Reply with <b>markup</b>."}),
            # A lone closing tag is still markup.
            ({}, {"text": "Thanks for your patience.</p>"}),
            ({"constraints": {"output_format": "html"}}, {"text": "Plain reply."}),
            # Markdown syntax is markup too, not just HTML tags.
            ({}, {"text": "Reply with **bold** text."}),
            ({}, {"text": "See [details](https://example.com)."}),
            ({}, {"text": "# Heading\nBody."}),
            ({}, {"text": "The *actual* deadline is Friday."}),
            # A combining mark attached to punctuation right before `*` must not itself count
            # as alphanumeric-flanking material - real emphasis here must still be detected.
            ({}, {"text": "Wait!́*urgent* now"}),
            ({}, {"text": "Plain reply.", "call_to_action": "**Book** a call."}),
            # GFM constructs beyond core CommonMark: tables, strikethrough.
            ({}, {"text": "| a | b |\n|---|---|\n| 1 | 2 |"}),
            ({}, {"text": "This is ~~struck~~ text."}),
            # A fenced code block is markup too.
            ({}, {"text": "```\ncode block\n```"}),
            # A real but non-formatting tag (e.g. <kbd>) is markup too.
            ({}, {"text": "Use the <kbd>Enter</kbd> key."}),
            # <email@domain> is CommonMark autolink syntax, not just plain bracketed text.
            ({}, {"text": "Reach me at <user@example.com>."}),
            # A real HTML tokenizer treats any well-formed "<word>" as a (possibly unknown)
            # tag, same as a browser would - unlike a hand-maintained name allowlist, it
            # doesn't special-case ordinary words that happen to be in brackets.
            ({}, {"text": "Please confirm <Tuesday> works for the call."}),
            # SVG/MathML integration points, custom elements, comments, and doctypes are all
            # real HTML5 constructs a name allowlist can never fully enumerate.
            ({}, {"text": "Reply with <svg>content</svg>."}),
            ({}, {"text": "Use <math>x</math> notation."}),
            ({}, {"text": "Custom <x-card>widget</x-card>."}),
            ({}, {"text": "Note: <!-- internal comment -->."}),
            ({}, {"text": "<!DOCTYPE html>"}),
            # Markdown alone doesn't satisfy "html" — it must contain a real tag.
            (
                {"constraints": {"output_format": "html"}},
                {"text": "Reply with **bold** text."},
            ),
            ({}, None),
            ({}, {"text": 123}),
        ],
    )
    def test_rejects(self, input_payload: dict, output: dict | None) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(input_payload=input_payload, output=output)


_ISSUES = [
    {"category": "timeline", "description": "d0", "severity": "high"},
    {"category": "scope", "description": "d1", "severity": "medium"},
    {"category": "budget", "description": "d2", "severity": "low"},
]


def _question(*, priority: str, source_issue_index: int) -> dict:
    return {
        "question": "q",
        "rationale": "r",
        "priority": priority,
        "category": "timeline",
        "source_issue_index": source_issue_index,
    }


class TestGenerateClarifyingQuestionsCrossValidator:
    def setup_method(self) -> None:
        self.validator = GenerateClarifyingQuestionsCrossValidator()

    def test_accepts_empty_questions_when_no_issue_is_actionable(self) -> None:
        self.validator.validate(input_payload={"issues": _ISSUES}, output={"questions": []})

    def test_accepts_in_bounds_deterministically_ordered_questions(self) -> None:
        self.validator.validate(
            input_payload={"issues": _ISSUES},
            output={
                "questions": [
                    _question(priority="high", source_issue_index=0),
                    _question(priority="medium", source_issue_index=1),
                    _question(priority="medium", source_issue_index=2),
                    _question(priority="low", source_issue_index=1),
                ]
            },
        )

    def test_accepts_up_to_max_questions_default_of_five(self) -> None:
        self.validator.validate(
            input_payload={"issues": _ISSUES * 2},
            output={
                "questions": [
                    _question(priority="high", source_issue_index=i) for i in range(5)
                ]
            },
        )

    def test_rejects_source_issue_index_out_of_bounds(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"issues": _ISSUES},
                output={"questions": [_question(priority="high", source_issue_index=3)]},
            )

    def test_rejects_negative_source_issue_index(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"issues": _ISSUES},
                output={"questions": [_question(priority="high", source_issue_index=-1)]},
            )

    def test_rejects_questions_when_no_issues_supplied(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"issues": []},
                output={"questions": [_question(priority="high", source_issue_index=0)]},
            )

    def test_rejects_questions_exceeding_default_max_questions(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"issues": _ISSUES * 2},
                output={
                    "questions": [
                        _question(priority="high", source_issue_index=i) for i in range(6)
                    ]
                },
            )

    def test_rejects_questions_exceeding_explicit_max_questions(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"issues": _ISSUES, "max_questions": 2},
                output={
                    "questions": [
                        _question(priority="high", source_issue_index=0),
                        _question(priority="medium", source_issue_index=1),
                        _question(priority="low", source_issue_index=2),
                    ]
                },
            )

    def test_rejects_questions_out_of_priority_order(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"issues": _ISSUES},
                output={
                    "questions": [
                        _question(priority="medium", source_issue_index=0),
                        _question(priority="high", source_issue_index=1),
                    ]
                },
            )

    def test_rejects_questions_out_of_source_order_within_same_priority(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"issues": _ISSUES},
                output={
                    "questions": [
                        _question(priority="high", source_issue_index=2),
                        _question(priority="high", source_issue_index=0),
                    ]
                },
            )

    def test_rejects_unknown_priority(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"issues": _ISSUES},
                output={"questions": [_question(priority="urgent", source_issue_index=0)]},
            )

    def test_rejects_missing_output(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(input_payload={"issues": _ISSUES}, output=None)

    def test_rejects_malformed_questions(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(input_payload={"issues": _ISSUES}, output={"questions": "nope"})


class TestPersuasiveTextCrossValidator:
    def setup_method(self) -> None:
        self.validator = PersuasiveTextCrossValidator()

    @pytest.mark.parametrize(
        ("input_payload", "output"),
        [
            ({}, {"text": "Plain persuasive text."}),
            ({"constraints": {"length": 20}}, {"text": "Short persuasion."}),
            (
                {"constraints": {"length": True}},
                {"text": "This text is longer than one character."},
            ),
            ({"constraints": {"format": "plain_text"}}, {"text": "Plain persuasive text."}),
            (
                {"constraints": {"format": "html"}},
                {"text": "Persuasive <b>markup</b>."},
            ),
            (
                {"constraints": {"format": "markdown"}},
                {"text": "**Bold** persuasion with *markdown* markers."},
            ),
            # Markdown is not required to prove itself with a decorative token — a plain
            # paragraph is valid Markdown too, same as the sibling A07 validator.
            ({"constraints": {"format": "markdown"}}, {"text": "Plain persuasive text."}),
            # Unspaced arithmetic/dimension expressions aren't markdown italic (CommonMark's
            # intraword-emphasis rule for `*` is escaped for alnum-flanked asterisks).
            ({}, {"text": "L*W*H"}),
            # An integer-valued float length (schema `type: integer` allows 10.0) is honored.
            ({"constraints": {"length": 20.0}}, {"text": "Short persuasion."}),
            # Any real HTML5 construct - not just a fixed set of "common" tag names - satisfies
            # "html", via the same real tokenizer used by A07.
            (
                {"constraints": {"format": "html"}},
                {"text": "Use the <kbd>Enter</kbd> key."},
            ),
            (
                {"constraints": {"format": "html"}},
                {"text": "Custom <x-card>widget</x-card>."},
            ),
        ],
    )
    def test_accepts(self, input_payload: dict, output: dict) -> None:
        self.validator.validate(input_payload=input_payload, output=output)

    @pytest.mark.parametrize(
        ("input_payload", "output"),
        [
            ({"constraints": {"length": 5}}, {"text": "This text is too long."}),
            (
                {"constraints": {"format": "plain_text"}},
                {"text": "Persuasive <b>markup</b>."},
            ),
            ({"constraints": {}}, {"text": "Persuasive <b>markup</b>."}),
            ({}, {"text": "Persuasive <b>markup</b>."}),
            # A lone closing tag is still markup.
            ({}, {"text": "Act now.</p>"}),
            ({"constraints": {"format": "html"}}, {"text": "Plain persuasive text."}),
            # Markdown syntax is markup too, not just HTML tags.
            ({}, {"text": "Act **now** to save."}),
            ({}, {"text": "See [details](https://example.com)."}),
            ({}, {"text": "# Heading\nBody."}),
            # A well-formed "<word>" is a (possibly unknown) HTML tag to a real tokenizer.
            ({}, {"text": "Offer expires <Tuesday>."}),
            # "<email@domain>" is CommonMark autolink syntax, not just plain bracketed text.
            ({}, {"text": "Reach me at <user@example.com>."}),
            # Spaced single-asterisk emphasis is real markdown italic, unlike unspaced
            # arithmetic/dimension expressions (e.g. "L*W*H").
            ({}, {"text": "The *actual* deadline is Friday."}),
            # An integer-valued float length (10.0) must still be enforced, not silently
            # ignored because it isn't a plain int.
            ({"constraints": {"length": 5.0}}, {"text": "This text is too long."}),
            # "html" must show its own markup kind: markdown-only text doesn't satisfy it.
            ({"constraints": {"format": "html"}}, {"text": "**Act now** and save."}),
            ({}, None),
            ({}, {"text": 123}),
        ],
    )
    def test_rejects(self, input_payload: dict, output: dict | None) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(input_payload=input_payload, output=output)


def _rubric_item(criterion_id: str, weight: float) -> dict:
    return {"id": criterion_id, "description": f"{criterion_id} criterion", "weight": weight}


class TestScoreMatchByRubricInputValidator:
    def setup_method(self) -> None:
        self.validator = ScoreMatchByRubricInputValidator()

    def test_accepts_unique_rubric_ids(self) -> None:
        self.validator.validate(
            input_payload={"rubric": [_rubric_item("tone", 1), _rubric_item("completeness", 2)]}
        )

    def test_rejects_duplicate_rubric_ids(self) -> None:
        with pytest.raises(ActionInputValidationError):
            self.validator.validate(
                input_payload={"rubric": [_rubric_item("tone", 1), _rubric_item("tone", 2)]}
            )

    def test_ignores_non_list_rubric_payload(self) -> None:
        self.validator.validate(input_payload={"rubric": "not-a-list"})


class TestScoreMatchByRubricCrossValidator:
    def setup_method(self) -> None:
        self.validator = ScoreMatchByRubricCrossValidator()

    def _output(self, aggregate_score: float) -> dict:
        return {
            "criterion_scores": [
                {"criterion_id": "tone", "score": 100, "rationale": "r"},
                {"criterion_id": "completeness", "score": 0, "rationale": "r"},
            ],
            "score": aggregate_score,
            "strengths": [],
            "gaps": [],
        }

    def test_accepts_matching_criteria_and_exact_aggregate(self) -> None:
        self.validator.validate(
            input_payload={"rubric": [_rubric_item("tone", 1), _rubric_item("completeness", 3)]},
            output=self._output(25),
        )

    def test_accepts_aggregate_within_tolerance(self) -> None:
        self.validator.validate(
            input_payload={"rubric": [_rubric_item("tone", 1), _rubric_item("completeness", 3)]},
            output=self._output(25.5),
        )

    def test_rejects_aggregate_beyond_tolerance(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={
                    "rubric": [_rubric_item("tone", 1), _rubric_item("completeness", 3)]
                },
                output=self._output(26),
            )

    def test_rejects_criterion_id_not_in_rubric(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"rubric": [_rubric_item("tone", 1)]},
                output={
                    "criterion_scores": [{"criterion_id": "unknown", "score": 80, "rationale": "r"}],
                    "score": 80,
                    "strengths": [],
                    "gaps": [],
                },
            )

    def test_rejects_duplicate_criterion_id(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"rubric": [_rubric_item("tone", 1)]},
                output={
                    "criterion_scores": [
                        {"criterion_id": "tone", "score": 80, "rationale": "r"},
                        {"criterion_id": "tone", "score": 90, "rationale": "r"},
                    ],
                    "score": 85,
                    "strengths": [],
                    "gaps": [],
                },
            )

    def test_rejects_rubric_criterion_missing_from_output(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"rubric": [_rubric_item("tone", 1), _rubric_item("completeness", 1)]},
                output={
                    "criterion_scores": [{"criterion_id": "tone", "score": 80, "rationale": "r"}],
                    "score": 80,
                    "strengths": [],
                    "gaps": [],
                },
            )

    def test_rejects_malformed_criterion_scores(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"rubric": [_rubric_item("tone", 1)]},
                output={"criterion_scores": "nope", "score": 80, "strengths": [], "gaps": []},
            )

    def test_ignores_when_rubric_missing_from_input(self) -> None:
        self.validator.validate(input_payload={}, output=self._output(0))

    def test_duplicate_rubric_id_weight_counted_once_in_denominator(self) -> None:
        """In production ScoreMatchByRubricInputValidator always rejects duplicate rubric
        ids before this cross-validator runs, but the cross-validator must stay correct on
        its own: a duplicate id must not inflate total_weight past what rubric_weights (the
        deduplicated numerator source) actually uses."""
        self.validator.validate(
            input_payload={
                "rubric": [_rubric_item("tone", 1), _rubric_item("tone", 3), _rubric_item("completeness", 1)]
            },
            output={
                "criterion_scores": [
                    {"criterion_id": "tone", "score": 100, "rationale": "r"},
                    {"criterion_id": "completeness", "score": 0, "rationale": "r"},
                ],
                "score": 75,
                "strengths": [],
                "gaps": [],
            },
        )

    def test_truncates_rejected_criterion_id_in_error_reason(self) -> None:
        overlong_id = "x" * 500
        with pytest.raises(StructuredOutputValidationError) as exc_info:
            self.validator.validate(
                input_payload={"rubric": [_rubric_item("tone", 1)]},
                output={
                    "criterion_scores": [{"criterion_id": overlong_id, "score": 80, "rationale": "r"}],
                    "score": 80,
                    "strengths": [],
                    "gaps": [],
                },
            )
        assert len(exc_info.value.reason) < len(overlong_id)
        assert exc_info.value.reason.endswith("...")


class TestScoreMatchByRubricAggregateToleranceMatchesPrompt:
    """Pins the prompt wording that `_SCORE_MATCH_AGGREGATE_TOLERANCE` (0.5) is derived
    from, so a prompt-side rounding-granularity change can't silently drift out of sync
    with the validator's tolerance (see the comment above the constant)."""

    def test_prompt_still_instructs_rounding_to_nearest_whole_number(self) -> None:
        prompt_path = (
            Path(__file__).resolve().parents[4]
            / "configs"
            / "kernel"
            / "products"
            / "kernel_demo"
            / "prompts"
            / "score_match_by_rubric.v1.md"
        )
        normalized = " ".join(prompt_path.read_text(encoding="utf-8").split())
        assert "rounded to the nearest whole number" in normalized


class TestScoreMatchByRubricCrossValidatorOverflow:
    def setup_method(self) -> None:
        self.validator = ScoreMatchByRubricCrossValidator()

    def test_rejects_when_extreme_weights_overflow_to_nan_expected_score(self) -> None:
        """Two individually-finite weights that overflow float64 once summed/multiplied
        must not silently bypass the aggregate check via `inf / inf = nan` (every
        comparison against `nan` is False in Python)."""
        huge_weight = 1.5e308
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={
                    "rubric": [
                        _rubric_item("tone", huge_weight),
                        _rubric_item("completeness", huge_weight),
                    ]
                },
                output={
                    "criterion_scores": [
                        {"criterion_id": "tone", "score": 100, "rationale": "r"},
                        {"criterion_id": "completeness", "score": 0, "rationale": "r"},
                    ],
                    "score": 0,
                    "strengths": [],
                    "gaps": [],
                },
            )
