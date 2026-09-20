from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pytest
from anytoolai_platform_actions.structured_llm.cross_validation import (
    CompareAndClassifyCrossValidator,
    CompareAndClassifyInputValidator,
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
    ScoreMatchByRubricCrossValidator,
    ScoreMatchByRubricInputValidator,
    SynthesizeAngleCrossValidator,
)
from anytoolai_platform_core.actions.runner import ActionInputValidationError
from anytoolai_platform_core.structured_output.errors import StructuredOutputValidationError


# TestPersuasiveTextCrossValidator (A06) and TestComposeReplyCrossValidator (A07) apply the
# identical ANY-502 plain_text-with-lists policy to their `text` field, so these cases are
# pinned once instead of duplicated byte-for-byte across both classes.
_PLAIN_TEXT_LIST_ACCEPT_CASES: list[tuple[dict, dict]] = [
    ({}, {"text": "1. First\n2. Second"}),
    ({}, {"text": "1) First\n2) Second"}),
    ({}, {"text": "- First\n- Second"}),
    ({}, {"text": "* First\n* Second"}),
    ({}, {"text": "+ First\n+ Second"}),
    ({}, {"text": "Intro paragraph.\n\nSecond paragraph."}),
    # Nested lists are allowed too (round-3 review) — the Linear-decided policy allows
    # "ordered/unordered list markers" without a flat/nesting-depth restriction.
    ({}, {"text": "- Parent\n  - Child"}),
]

_PLAIN_TEXT_LIST_REJECT_CASES: list[tuple[dict, dict]] = [
    # A blockquote is still disallowed markup for plain_text.
    ({}, {"text": "> quote"}),
    # A list item with disallowed nested markup must still fail — allowing list structure
    # doesn't allow markup inside a list item.
    ({}, {"text": "- **Important item**"}),
    # Empty list items ("-", "1)") carry no meaningful content, not a real list.
    ({}, {"text": "-\n-\n-"}),
    ({}, {"text": "1.\n2.\n3."}),
    # GFM task-list checkboxes are checkbox formatting, not a plain list marker — the prompt
    # only allows "ordered/unordered list markers".
    ({}, {"text": "- [ ] Send the invoice\n- [x] Follow up next week"}),
    # A bare checkbox with no task text at all (checkbox is the item's entire content, not
    # just a prefix) must reject too — round-2 review found this false negative.
    ({}, {"text": "- [ ]"}),
    ({}, {"text": "- [x]"}),
    ({}, {"text": "1. [ ]\n2. real item"}),
    # Disallowed markup nested inside a sub-list item must still fail — nesting is allowed,
    # markup inside any item (top-level or nested) is not.
    ({}, {"text": "- Parent\n  - **Child**"}),
    # Inline code (a distinct `code_inline` token from fenced code's `fence`/`code_block`)
    # must reject too — an explicit ANY-502 regression requirement, not covered by the
    # existing fenced-code case.
    ({}, {"text": "Please send the `invoice` today."}),
]


# Code review finding (me #17): whether `text` shows the reader anything depends on the format
# it's rendered as, so these are (format, text) pairs -- A06 and A07 share the identical
# `_has_visible_text` policy and differ only in the constraint key (`format` vs
# `output_format`), so the cases are pinned once and expanded per validator below.
_HTML_DOCUMENT_WITH_TITLE = (
    "<html><head><title>Client update</title></head><body>%s</body></html>"
)

_VISIBLE_TEXT_ACCEPT_CASES: list[tuple[str | None, str]] = [
    # plain_text (or omitted) is copied to the client literally, never entity-decoded: these
    # are six/five/nine visible characters, e.g. a reply answering "which entity is a
    # non-breaking space?".
    ("plain_text", "&nbsp;"),
    ("plain_text", "&#32;"),
    ("plain_text", "&NewLine;"),
    (None, "&nbsp;"),
    # Non-rendered elements next to real message text don't make the message blank.
    ("html", "<style>p { color: red; }</style><p>Ready.</p>"),
    # An escaped tag is literal visible text, not markup to strip.
    ("html", "<p>&lt;p&gt;</p>"),
    # Indented code block and a list of inline-code items are visible markdown content.
    ("markdown", "    npm run build"),
    ("markdown", "- `npm ci`\n- `npm run build`"),
    # Code review finding (me #18): a document title next to a real body, a skipped element
    # next to real text, an escaped literal `<title>`, and an omitted (optional) `</head>`
    # must all stay accepted once title/template content is excluded.
    ("html", _HTML_DOCUMENT_WITH_TITLE % "<p>Ready.</p>"),
    ("markdown", _HTML_DOCUMENT_WITH_TITLE % "<p>Ready.</p>"),
    ("html", "<template>Hidden draft</template><p>Ready.</p>"),
    ("html", "<p>&lt;title&gt;Client update&lt;/title&gt;</p>"),
    ("html", "<head><title>Client update</title><body><p>Ready.</p>"),
    # Code review finding (me #19): html-format tag detection went through the Markdown
    # parser, which reads 4 spaces / a tab as an indented code block -- ordinarily-indented
    # HTML showed no tag at all and was rejected as "missing markup".
    ("html", "    <p>Ready.</p>"),
    ("html", "\t<p>Ready.</p>"),
    ("html", "<div>\n        <p>Ready.</p>\n        <p>Delivered.</p>\n</div>"),
    # `</rp>` is optional in valid HTML and HTMLParser never synthesizes implicit closes, so
    # `rp` must not be tracked as a skipped element (it hid everything after it).
    ("html", "<ruby><rp>(<rt>Ready<rp>)</ruby><p>Delivered.</p>"),
    ("html", "<ruby><rp>(</rp><rt>Ready</rt><rp>)</rp></ruby><p>Delivered.</p>"),
    # A trailing slash really self-closes inside SVG/MathML, and void elements are untouched.
    ("html", "<svg><title/></svg><p>Ready.</p>"),
    ("html", "<p>Ready.<br/></p>"),
    # Code review finding (me #20): real content at an SVG/MathML HTML integration point is
    # still visible, and a non-HTML `annotation-xml` encoding keeps foreign self-closing.
    ("html", "<svg><foreignObject><p>Ready.</p></foreignObject></svg>"),
    ("html", '<math><annotation-xml encoding="text/html"><p>Ready.</p></annotation-xml></math>'),
    (
        "html",
        '<math><annotation-xml encoding="application/mathml+xml"><template/>Shown</annotation-xml></math>',
    ),
    # Ruby base text and annotation stay visible with `rp` skipped again.
    ("html", "<ruby>漢<rp>(<rt>kan<rp>)</ruby>"),
]

_VISIBLE_TEXT_REJECT_CASES: list[tuple[str | None, str]] = [
    # A browser never renders script/style/template content as text -- a real tag is
    # present (so the html-format check alone passes) but the client would see nothing.
    ("html", "<style>p { color: red; }</style>"),
    ("html", "<script>console.log(1)</script>"),
    ("html", "<template>Hidden template text.</template>"),
    ("html", "<template><p>Hidden template text.</p></template>"),
    ("html", "<style>p { color: red; }</style><p>&nbsp;</p>"),
    # markdown renders entities and passes raw HTML through, so the same blanks apply.
    ("markdown", "&nbsp;"),
    ("markdown", "<p>&nbsp;</p>"),
    ("markdown", "<style>p { color: red; }</style>"),
    # A genuinely empty code block is still empty.
    ("markdown", "```\n\n```"),
    # Code review finding (me #18): `<title>` is document metadata, not the client message --
    # a well-formed document with a filled title and an empty/blank body shows nothing.
    ("html", _HTML_DOCUMENT_WITH_TITLE % ""),
    ("html", _HTML_DOCUMENT_WITH_TITLE % "<p>&nbsp;</p>"),
    ("markdown", _HTML_DOCUMENT_WITH_TITLE % ""),
    ("html", "<datalist><option>Hidden option</option></datalist>"),
    # HTMLParser doesn't pair end tags with start tags: a stray `</style>` must not end the
    # enclosing `<template>`'s skipped region, nor may an inner same-name element's end tag.
    ("html", "<template></style>Hidden draft</template>"),
    ("html", "<template><template>Inner</template>Hidden draft</template>"),
    # Code review finding (me #19): HTML ignores a trailing slash on its own elements, so
    # `<template/>` stays open in a browser -- HTMLParser's default start+end would expose
    # the hidden text.
    ("html", "<template/>Hidden draft"),
    ("html", "<script/>Hidden draft"),
    ("html", "<style/>Hidden draft"),
    ("html", "<template><ruby><rp>(<rt>Ready<rp>)</ruby></template>"),
    # Code review finding (me #20): `rp` is fallback parentheses a browser never shows -- a
    # reply made only of them is blank, with explicit or omitted `</rp>`.
    ("html", "<ruby><rp>(</rp><rp>)</rp></ruby>"),
    ("html", "<ruby><rp>(<rp>)</ruby>"),
    ("markdown", "<ruby><rp>(</rp><rp>)</rp></ruby>"),
    # Inside SVG/MathML, children of an HTML integration point are parsed as HTML again, so
    # `<template/>` there is *not* self-closed and its text stays hidden.
    ("html", "<svg><foreignObject><template/>Hidden draft</foreignObject></svg>"),
    ("html", "<svg><desc><template/>Hidden draft</desc></svg>"),
    (
        "html",
        '<math><annotation-xml encoding="text/html"><template/>Hidden draft</annotation-xml></math>',
    ),
    (
        "html",
        '<math><annotation-xml encoding="APPLICATION/XHTML+XML"><template/>Hidden draft</annotation-xml></math>',
    ),
    ("html", "<math><mtext><template/>Hidden draft</mtext></math>"),
]


def _visible_text_cases(cases: list[tuple[str | None, str]], format_key: str) -> list[tuple[dict, dict]]:
    return [
        ({"constraints": {format_key: text_format}} if text_format else {}, {"text": text})
        for text_format, text in cases
    ]


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


class TestCompareAndClassifyInputValidator:
    def setup_method(self) -> None:
        self.validator = CompareAndClassifyInputValidator()

    def test_accepts_unique_criteria_ids(self) -> None:
        self.validator.validate(
            input_payload={
                "criteria": [
                    {"id": "tone", "description": "d"},
                    {"id": "coverage", "description": "d"},
                ]
            }
        )

    def test_rejects_duplicate_criteria_ids(self) -> None:
        with pytest.raises(ActionInputValidationError):
            self.validator.validate(
                input_payload={
                    "criteria": [
                        {"id": "tone", "description": "d1"},
                        {"id": "tone", "description": "d2"},
                    ]
                }
            )

    def test_ignores_non_list_criteria_payload(self) -> None:
        self.validator.validate(input_payload={"criteria": "not-a-list"})


class TestCompareAndClassifyCrossValidator:
    def setup_method(self) -> None:
        self.validator = CompareAndClassifyCrossValidator()
        self.input_payload = {
            "categories": ["meets_bar", "below_bar"],
            "criteria": [
                {"id": "tone", "description": "d"},
                {"id": "coverage", "description": "d"},
            ],
        }

    def _deltas(self, *statuses: tuple[str, str]) -> list[dict]:
        return [
            {"criterion_id": criterion_id, "status": status, "evidence": "e"}
            for criterion_id, status in statuses
        ]

    def test_accepts_verdict_in_categories_and_full_delta_coverage(self) -> None:
        self.validator.validate(
            input_payload=self.input_payload,
            output={
                "verdict": "meets_bar",
                "confidence": 0.9,
                "deltas": self._deltas(("tone", "match"), ("coverage", "partial")),
                "rationale": "r",
            },
        )

    def test_rejects_verdict_outside_categories(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload=self.input_payload,
                output={
                    "verdict": "not_a_category",
                    "confidence": 0.9,
                    "deltas": self._deltas(("tone", "match"), ("coverage", "partial")),
                    "rationale": "r",
                },
            )

    def test_rejects_delta_criterion_id_not_in_criteria(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload=self.input_payload,
                output={
                    "verdict": "meets_bar",
                    "confidence": 0.9,
                    "deltas": self._deltas(("tone", "match"), ("unknown", "match")),
                    "rationale": "r",
                },
            )

    def test_rejects_duplicate_delta_criterion_id(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload=self.input_payload,
                output={
                    "verdict": "meets_bar",
                    "confidence": 0.9,
                    "deltas": self._deltas(("tone", "match"), ("tone", "mismatch")),
                    "rationale": "r",
                },
            )

    def test_rejects_deltas_missing_a_criterion(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload=self.input_payload,
                output={
                    "verdict": "meets_bar",
                    "confidence": 0.9,
                    "deltas": self._deltas(("tone", "match")),
                    "rationale": "r",
                },
            )

    def test_truncates_rejected_verdict_in_error_reason(self) -> None:
        overlong_verdict = "x" * 500
        with pytest.raises(StructuredOutputValidationError) as exc_info:
            self.validator.validate(
                input_payload=self.input_payload,
                output={
                    "verdict": overlong_verdict,
                    "confidence": 0.9,
                    "deltas": self._deltas(("tone", "match"), ("coverage", "partial")),
                    "rationale": "r",
                },
            )
        assert len(exc_info.value.reason) < len(overlong_verdict)
        assert exc_info.value.reason.endswith("...")

    def test_skips_deltas_validation_when_input_criteria_is_not_a_list(self) -> None:
        """Malformed input.criteria (schema-conformant callers never send this) must not get
        misattributed to output.deltas as a model defect - mirrors the early-return pattern
        ExtractStructuredFieldsCrossValidator uses for malformed input.fields."""
        self.validator.validate(
            input_payload={"categories": ["meets_bar", "below_bar"], "criteria": "not-a-list"},
            output={
                "verdict": "meets_bar",
                "confidence": 0.9,
                "deltas": self._deltas(("tone", "match")),
                "rationale": "r",
            },
        )


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
            # plain_text allows ordered/unordered list markers (ANY-502) — a live model
            # naturally reaches for lists on multi-item asks.
            *_PLAIN_TEXT_LIST_ACCEPT_CASES,
            # Code review finding (me #15): _visible_text_content ignored code_inline/fence
            # content entirely, so a schema-valid markdown reply that's *entirely* code (a
            # legitimate answer to "what's the build command?") was wrongly treated as blank.
            ({"constraints": {"output_format": "markdown"}}, {"text": "`npm run build`"}),
            (
                {"constraints": {"output_format": "markdown"}},
                {"text": "```\nnpm run build\n```"},
            ),
            (
                # plain_text keeps its own separate, stricter no-markup rule for
                # call_to_action (unrelated to this blank-content fix) -- markdown format
                # isn't subject to that rule, so it isolates the blank-content check alone.
                {"constraints": {"output_format": "markdown"}},
                {"text": "Plain reply.", "call_to_action": "`npm run build`"},
            ),
            # HTML entities must decode before the blank check -- "&amp;" is real visible
            # content ("&"), not whitespace.
            ({"constraints": {"output_format": "html"}}, {"text": "<p>&amp;</p>"}),
            *_visible_text_cases(_VISIBLE_TEXT_ACCEPT_CASES, "output_format"),
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
            *_PLAIN_TEXT_LIST_REJECT_CASES,
            # text and call_to_action diverge now (ANY-502): list syntax is allowed in text
            # but call_to_action keeps the stricter no-markup contract unchanged.
            ({}, {"text": "Plain reply.", "call_to_action": "- Book a call"}),
            ({}, None),
            ({}, {"text": 123}),
            # Code review finding (P2): `minLength: 1` on the output schema accepts a
            # whitespace-only string, and a real HTML tag with nothing inside it -- neither
            # is a usable client-facing message.
            ({}, {"text": "   "}),
            ({}, {"text": "\n\t"}),
            ({"constraints": {"output_format": "html"}}, {"text": "<p></p>"}),
            ({"constraints": {"output_format": "html"}}, {"text": "<p>  </p>"}),
            ({}, {"text": "Plain reply.", "call_to_action": "   "}),
            # Code review finding (me #15): a raw HTML block's content is never
            # parser-decoded, so an unescaped character reference like "&nbsp;" survived the
            # tag-strip as a literal, non-whitespace string and wrongly counted as content.
            ({"constraints": {"output_format": "html"}}, {"text": "<p>&nbsp;</p>"}),
            ({"constraints": {"output_format": "html"}}, {"text": "<div>&nbsp;</div>"}),
            (
                {"constraints": {"output_format": "html"}},
                {"text": "<p>&#32;&#x09;&#10;</p>"},
            ),
            (
                {"constraints": {"output_format": "html"}},
                {"text": "Plain reply.", "call_to_action": "<p>&nbsp;</p>"},
            ),
            *_visible_text_cases(_VISIBLE_TEXT_REJECT_CASES, "output_format"),
            (
                {"constraints": {"output_format": "html"}},
                {"text": "<p>Reply.</p>", "call_to_action": "<style>p { color: red; }</style>"},
            ),
            (
                {"constraints": {"output_format": "html"}},
                {"text": "<p>Reply.</p>", "call_to_action": "<template/>Hidden draft"},
            ),
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
            # plain_text allows ordered/unordered list markers (ANY-502) — a live model
            # naturally reaches for lists on multi-item asks.
            *_PLAIN_TEXT_LIST_ACCEPT_CASES,
            # Code review finding (me #15): code-only markdown content and a real decoded
            # HTML entity must count as visible text, same as A07's sibling validator.
            ({"constraints": {"format": "markdown"}}, {"text": "`npm run build`"}),
            ({"constraints": {"format": "markdown"}}, {"text": "```\nnpm run build\n```"}),
            ({"constraints": {"format": "html"}}, {"text": "<p>&amp;</p>"}),
            *_visible_text_cases(_VISIBLE_TEXT_ACCEPT_CASES, "format"),
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
            *_PLAIN_TEXT_LIST_REJECT_CASES,
            ({}, None),
            ({}, {"text": 123}),
            # Code review finding (P2): same empty/whitespace-content gap as A07's sibling
            # validator.
            ({}, {"text": "   "}),
            ({}, {"text": "\n\t"}),
            ({"constraints": {"format": "html"}}, {"text": "<p></p>"}),
            ({"constraints": {"format": "html"}}, {"text": "<p>  </p>"}),
            # Code review finding (me #15): same character-reference-decoding gap as A07's
            # sibling validator -- "&nbsp;" survives a raw tag-strip as a literal string.
            ({"constraints": {"format": "html"}}, {"text": "<p>&nbsp;</p>"}),
            ({"constraints": {"format": "html"}}, {"text": "<div>&nbsp;</div>"}),
            ({"constraints": {"format": "html"}}, {"text": "<p>&#32;&#x09;&#10;</p>"}),
            *_visible_text_cases(_VISIBLE_TEXT_REJECT_CASES, "format"),
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

    def test_rejects_non_string_axis_id(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"axes": [_axis("clarity")]},
                output={
                    "scores": [{"axis_id": ["clarity"], "score": 8, "commentary": "c"}],
                    "dominant_axes": ["clarity"],
                    "weakest_axes": ["clarity"],
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

    def test_rejects_non_finite_rubric_weight(self) -> None:
        with pytest.raises(ActionInputValidationError):
            self.validator.validate(input_payload={"rubric": [_rubric_item("tone", float("inf"))]})


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

    def test_rejects_non_mapping_criterion_score_entry(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"rubric": [_rubric_item("tone", 1)]},
                output={"criterion_scores": ["nope"], "score": 80, "strengths": [], "gaps": []},
            )

    def test_rejects_unhashable_criterion_id(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"rubric": [_rubric_item("tone", 1)]},
                output={
                    "criterion_scores": [{"criterion_id": ["tone"], "score": 80, "rationale": "r"}],
                    "score": 80,
                    "strengths": [],
                    "gaps": [],
                },
            )

    def test_rejects_non_finite_criterion_score(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"rubric": [_rubric_item("tone", 1)]},
                output={
                    "criterion_scores": [
                        {"criterion_id": "tone", "score": float("nan"), "rationale": "r"}
                    ],
                    "score": 80,
                    "strengths": [],
                    "gaps": [],
                },
            )

    def test_rejects_missing_aggregate_score(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"rubric": [_rubric_item("tone", 1)]},
                output={
                    "criterion_scores": [{"criterion_id": "tone", "score": 80, "rationale": "r"}],
                    "strengths": [],
                    "gaps": [],
                },
            )

    def test_rejects_zero_total_weight(self) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"rubric": [_rubric_item("tone", 0)]},
                output={
                    "criterion_scores": [{"criterion_id": "tone", "score": 80, "rationale": "r"}],
                    "score": 80,
                    "strengths": [],
                    "gaps": [],
                },
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

    def test_rejects_single_non_finite_rubric_weight(self) -> None:
        """A weight of `inf` (e.g. from a JSON literal like `1e309` overflowing on parse)
        must not be silently dropped from rubric_weights - that would validate output
        against a rubric missing this criterion instead of rejecting the malformed input."""
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={
                    "rubric": [
                        _rubric_item("tone", float("inf")),
                        _rubric_item("completeness", 1),
                    ]
                },
                output={
                    "criterion_scores": [
                        {"criterion_id": "tone", "score": 100, "rationale": "r"},
                        {"criterion_id": "completeness", "score": 0, "rationale": "r"},
                    ],
                    "score": 50,
                    "strengths": [],
                    "gaps": [],
                },
            )

    def test_rejects_when_every_rubric_weight_is_non_finite(self) -> None:
        """If every weight overflows, rubric_weights would be empty and the old code
        returned early - skipping coverage/aggregate checks entirely instead of failing
        closed."""
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(
                input_payload={"rubric": [_rubric_item("tone", float("inf"))]},
                output={
                    "criterion_scores": [{"criterion_id": "tone", "score": 100, "rationale": "r"}],
                    "score": 999999,
                    "strengths": [],
                    "gaps": [],
                },
            )
