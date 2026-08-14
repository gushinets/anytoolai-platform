from __future__ import annotations

import json
import unicodedata

import pytest
from anytoolai_platform_actions.structured_llm.cross_validation import (
    ComposeReplyCrossValidator,
    DetectIssuesByTaxonomyCrossValidator,
    ExtractStructuredFieldsCrossValidator,
    ExtractStructuredFieldsInputValidator,
    GapRewritesCrossValidator,
    GenerateClarifyingQuestionsCrossValidator,
    ScoreMultidimensionalAxesCrossValidator,
    ScoreMultidimensionalAxesInputValidator,
    SynthesizeAngleCrossValidator,
    PersuasiveTextCrossValidator,
    SynthesizeAngleCrossValidator,
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

    def test_integer_type_accepts_integer_valued_float(self) -> None:
        # json.loads('{"budget": 500.0}') decodes to a Python float; that must still satisfy
        # an "integer" field type, not be rejected as a type mismatch.
        self.validator.validate(
            input_payload={"fields": [_field("budget", "integer", required=False)]},
            output={"values": {"budget": 500.0}, "missing_fields": []},
        )
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"fields": [_field("budget", "integer", required=False)]},
                output={"values": {"budget": 500.5}, "missing_fields": []},
            )
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"fields": [_field("budget", "integer", required=False)]},
                output={"values": {"budget": True}, "missing_fields": []},
            )


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
            # Any real HTML5 element tag - not just a fixed set of "common" tag names -
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
            # markdown-it-py lumps a same-line comment and a following real tag into one
            # html_block token when there's no blank line between them - the real tag must
            # still be found even though it isn't at the start of that token's content.
            (
                {"constraints": {"output_format": "html"}},
                {"text": "<!-- note --><p>Real reply.</p>"},
            ),
            (
                {"constraints": {"output_format": "html"}},
                {"text": "<!DOCTYPE html><html>Real reply.</html>"},
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
            # A comment/doctype/CDATA is a real HTML5 construct but renders nothing, so it
            # doesn't satisfy "html" formatting on its own — only an actual element tag does.
            (
                {"constraints": {"output_format": "html"}},
                {"text": "<!-- internal comment -->"},
            ),
            ({"constraints": {"output_format": "html"}}, {"text": "<!DOCTYPE html>"}),
            (
                {"constraints": {"output_format": "html"}},
                {"text": "<![CDATA[ some data ]]>"},
            ),
            # Leading whitespace before a comment-only block must not be mistaken for a
            # missing "<!"/"<?" prefix - it's still just a comment, no real tag.
            (
                {"constraints": {"output_format": "html"}},
                {"text": "  <!-- internal comment -->"},
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


def _rewrite(text: str) -> dict:
    return {"text": text, "explanation": "e", "change_made": "c"}


class TestGapRewritesCrossValidator:
    def setup_method(self) -> None:
        self.validator = GapRewritesCrossValidator()

    def test_accepts_matching_count_and_distinct_rewrites(self) -> None:
        self.validator.validate(
            input_payload={"n": 2},
            output={
                "rewrites": [_rewrite("Alpha version."), _rewrite("Beta version.")],
                "best_pick": 1,
            },
        )

    def test_defaults_requested_count_to_three_when_n_omitted(self) -> None:
        self.validator.validate(
            input_payload={},
            output={
                "rewrites": [_rewrite("Alpha"), _rewrite("Beta"), _rewrite("Gamma")],
                "best_pick": 0,
            },
        )
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={},
                output={"rewrites": [_rewrite("Alpha"), _rewrite("Beta")], "best_pick": 0},
            )

    def test_rejects_rewrite_count_below_requested_n(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"n": 3},
                output={
                    "rewrites": [_rewrite("Alpha"), _rewrite("Beta")],
                    "best_pick": 0,
                },
            )

    def test_rejects_rewrite_count_above_requested_n(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"n": 1},
                output={
                    "rewrites": [_rewrite("Alpha"), _rewrite("Beta")],
                    "best_pick": 0,
                },
            )

    def test_accepts_integer_valued_float_n_from_json_schema_type_integer(self) -> None:
        # JSON Schema `type: integer` also accepts integer-valued floats (2.0), so n=2.0 must
        # be treated as n=2, not silently reset to the default.
        self.validator.validate(
            input_payload={"n": 2.0},
            output={
                "rewrites": [_rewrite("Alpha version."), _rewrite("Beta version.")],
                "best_pick": 0,
            },
        )

    def test_accepts_integer_valued_float_best_pick_from_json_decode(self) -> None:
        # json.loads('{"best_pick": 1.0}') decodes to a Python float; that must still be
        # treated as index 1, not rejected as out of bounds.
        self.validator.validate(
            input_payload={"n": 2},
            output={
                "rewrites": [_rewrite("Alpha version."), _rewrite("Beta version.")],
                "best_pick": 1.0,
            },
        )

    def test_rejects_duplicate_rewrites_differing_only_in_whitespace_and_case(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"n": 2},
                output={
                    "rewrites": [
                        _rewrite("Deliver by March 15."),
                        _rewrite("  deliver   by march 15.  "),
                    ],
                    "best_pick": 0,
                },
            )

    def test_rejects_best_pick_out_of_bounds(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"n": 1},
                output={"rewrites": [_rewrite("Alpha")], "best_pick": 1},
            )

    def test_rejects_negative_best_pick(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"n": 1},
                output={"rewrites": [_rewrite("Alpha")], "best_pick": -1},
            )

    def test_rejects_missing_output(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(input_payload={"n": 1}, output=None)


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
            # Any real HTML5 element tag - not just a fixed set of "common" tag names -
            # satisfies "html", via the same real tokenizer used by A07.
            (
                {"constraints": {"format": "html"}},
                {"text": "Use the <kbd>Enter</kbd> key."},
            ),
            (
                {"constraints": {"format": "html"}},
                {"text": "Custom <x-card>widget</x-card>."},
            ),
            # markdown-it-py lumps a same-line comment and a following real tag into one
            # html_block token when there's no blank line between them - the real tag must
            # still be found even though it isn't at the start of that token's content.
            (
                {"constraints": {"format": "html"}},
                {"text": "<!-- note --><p>Real persuasion.</p>"},
            ),
            (
                {"constraints": {"format": "html"}},
                {"text": "<!DOCTYPE html><html>Real persuasion.</html>"},
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
            # A comment/doctype/CDATA is a real HTML5 construct but renders nothing, so it
            # doesn't satisfy "html" formatting on its own — only an actual element tag does.
            ({"constraints": {"format": "html"}}, {"text": "<!-- internal note -->"}),
            ({"constraints": {"format": "html"}}, {"text": "<!DOCTYPE html>"}),
            ({"constraints": {"format": "html"}}, {"text": "<![CDATA[ some data ]]>"}),
            # Leading whitespace before a comment-only block must not be mistaken for a
            # missing "<!"/"<?" prefix - it's still just a comment, no real tag.
            (
                {"constraints": {"format": "html"}},
                {"text": "  <!-- internal note -->"},
            ),
            ({}, None),
            ({}, {"text": 123}),
        ],
    )
    def test_rejects(self, input_payload: dict, output: dict | None) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(input_payload=input_payload, output=output)


def _axis(axis_id: str, **extra: object) -> dict:
    return {"id": axis_id, "description": f"{axis_id} axis", **extra}


class TestScoreMultidimensionalAxesInputValidator:
    def setup_method(self) -> None:
        self.validator = ScoreMultidimensionalAxesInputValidator()

    def test_accepts_unique_axis_ids(self) -> None:
        self.validator.validate(
            input_payload={"axes": [_axis("clarity"), _axis("structure")]}
        )

    def test_rejects_duplicate_axis_ids(self) -> None:
        with pytest.raises(ActionInputValidationError):
            self.validator.validate(
                input_payload={"axes": [_axis("clarity"), _axis("clarity")]}
            )

    def test_ignores_non_list_axes_payload(self) -> None:
        self.validator.validate(input_payload={"axes": "not-a-list"})


class TestScoreMultidimensionalAxesCrossValidator:
    def setup_method(self) -> None:
        self.validator = ScoreMultidimensionalAxesCrossValidator()

    def _score(self, axis_id: str, score: float) -> dict:
        return {"axis_id": axis_id, "score": score, "commentary": "c"}

    def test_accepts_matching_scores_with_single_dominant_and_weakest(self) -> None:
        self.validator.validate(
            input_payload={"axes": [_axis("clarity"), _axis("structure")]},
            output={
                "scores": [self._score("clarity", 8), self._score("structure", 5)],
                "dominant_axes": ["clarity"],
                "weakest_axes": ["structure"],
            },
        )

    def test_accepts_tied_dominant_axes_in_input_order(self) -> None:
        self.validator.validate(
            input_payload={"axes": [_axis("clarity"), _axis("structure"), _axis("tone")]},
            output={
                "scores": [
                    self._score("clarity", 8),
                    self._score("structure", 8),
                    self._score("tone", 3),
                ],
                "dominant_axes": ["clarity", "structure"],
                "weakest_axes": ["tone"],
            },
        )

    def test_accepts_tied_weakest_axes_in_input_order(self) -> None:
        self.validator.validate(
            input_payload={"axes": [_axis("clarity"), _axis("structure"), _axis("tone")]},
            output={
                "scores": [
                    self._score("clarity", 9),
                    self._score("structure", 3),
                    self._score("tone", 3),
                ],
                "dominant_axes": ["clarity"],
                "weakest_axes": ["structure", "tone"],
            },
        )

    def test_rejects_axis_id_not_in_axes(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"axes": [_axis("clarity")]},
                output={
                    "scores": [self._score("unknown", 8)],
                    "dominant_axes": ["unknown"],
                    "weakest_axes": ["unknown"],
                },
            )

    def test_rejects_duplicate_axis_id_in_scores(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"axes": [_axis("clarity")]},
                output={
                    "scores": [self._score("clarity", 8), self._score("clarity", 5)],
                    "dominant_axes": ["clarity"],
                    "weakest_axes": ["clarity"],
                },
            )

    def test_rejects_axis_missing_from_scores(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"axes": [_axis("clarity"), _axis("structure")]},
                output={
                    "scores": [self._score("clarity", 8)],
                    "dominant_axes": ["clarity"],
                    "weakest_axes": ["clarity"],
                },
            )

    def test_rejects_malformed_scores_not_list(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"axes": [_axis("clarity")]},
                output={"scores": "nope", "dominant_axes": ["clarity"], "weakest_axes": ["clarity"]},
            )

    def test_rejects_malformed_score_entry(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"axes": [_axis("clarity")]},
                output={"scores": ["nope"], "dominant_axes": ["clarity"], "weakest_axes": ["clarity"]},
            )

    @pytest.mark.parametrize("invalid_score", ["high", True, float("nan")])
    def test_rejects_invalid_axis_score(self, invalid_score: object) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"axes": [_axis("clarity")]},
                output={
                    "scores": [{"axis_id": "clarity", "score": invalid_score, "commentary": "c"}],
                    "dominant_axes": ["clarity"],
                    "weakest_axes": ["clarity"],
                },
            )

    def test_rejects_dominant_axes_mismatch(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"axes": [_axis("clarity"), _axis("structure")]},
                output={
                    "scores": [self._score("clarity", 8), self._score("structure", 5)],
                    "dominant_axes": ["structure"],
                    "weakest_axes": ["structure"],
                },
            )

    def test_rejects_dominant_axes_missing_a_tied_entry(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"axes": [_axis("clarity"), _axis("structure")]},
                output={
                    "scores": [self._score("clarity", 8), self._score("structure", 8)],
                    "dominant_axes": ["clarity"],
                    "weakest_axes": ["clarity", "structure"],
                },
            )

    def test_rejects_dominant_axes_wrong_order(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"axes": [_axis("clarity"), _axis("structure")]},
                output={
                    "scores": [self._score("clarity", 8), self._score("structure", 8)],
                    "dominant_axes": ["structure", "clarity"],
                    "weakest_axes": ["structure", "clarity"],
                },
            )

    def test_rejects_weakest_axes_mismatch(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"axes": [_axis("clarity"), _axis("structure")]},
                output={
                    "scores": [self._score("clarity", 8), self._score("structure", 5)],
                    "dominant_axes": ["clarity"],
                    "weakest_axes": ["clarity"],
                },
            )

    def test_ignores_when_axes_missing_from_input(self) -> None:
        self.validator.validate(
            input_payload={},
            output={"scores": [self._score("clarity", 8)], "dominant_axes": [], "weakest_axes": []},
        )

    def test_truncates_rejected_axis_id_in_error_reason(self) -> None:
        overlong_id = "x" * 500
        with pytest.raises(StructuredOutputValidationError) as exc_info:
            self.validator.validate(
                input_payload={"axes": [_axis("clarity")]},
                output={
                    "scores": [self._score(overlong_id, 8)],
                    "dominant_axes": [overlong_id],
                    "weakest_axes": [overlong_id],
                },
            )
        assert len(exc_info.value.reason) < len(overlong_id)
        assert exc_info.value.reason.endswith("...")


class TestRejectDuplicateIdsSharedHelper:
    """Covers the `_reject_duplicate_ids` helper both A01 and A03 input validators share,
    through the two public validators that call it."""

    def test_extract_structured_fields_and_score_multidim_share_duplicate_rejection_behavior(
        self,
    ) -> None:
        extract_validator = ExtractStructuredFieldsInputValidator()
        score_multidim_validator = ScoreMultidimensionalAxesInputValidator()

        with pytest.raises(ActionInputValidationError):
            extract_validator.validate(
                input_payload={
                    "fields": [
                        _field("deadline", "string", required=True),
                        _field("deadline", "number", required=False),
                    ]
                }
            )
        with pytest.raises(ActionInputValidationError):
            score_multidim_validator.validate(
                input_payload={"axes": [_axis("clarity"), _axis("clarity")]}
            )
