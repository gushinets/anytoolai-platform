from __future__ import annotations

import json

import pytest
from anytoolai_platform_actions.structured_llm.cross_validation import (
    DetectIssuesByTaxonomyCrossValidator,
    ExtractStructuredFieldsCrossValidator,
    ExtractStructuredFieldsInputValidator,
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


class TestPersuasiveTextCrossValidator:
    def setup_method(self) -> None:
        self.validator = PersuasiveTextCrossValidator()

    def test_pathological_bracket_text_does_not_hang(self) -> None:
        """Regression: `[` repeated with no closing `]` used to make the markdown link
        pattern's `.search()` retry an O(remaining-length) failed match at every `[`,
        i.e. O(n^2) overall. This must stay fast regardless of input size."""
        self.validator.validate(
            input_payload={}, output={"text": "[" * 20000 + " end of message"}
        )

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
            # Non-markup bracketed text must not be mistaken for HTML.
            ({}, {"text": "Offer expires <Tuesday>."}),
            ({}, {"text": "Reach me at <user@example.com>."}),
            # A single asterisk is common casual emphasis, not markdown bold.
            ({}, {"text": "The *actual* deadline is Friday."}),
            # Short tag names (a/b/i/p/u) followed by ordinary bracketed words are not markup:
            # no self-close and no "=" attribute value.
            ({}, {"text": "Wait <a while longer> before deciding."}),
            ({}, {"text": "<i said hello> to the team."}),
            ({}, {"text": "Please be <b careful> with the budget."}),
            ({}, {"text": "It is <p class or not> your call."}),
            # Common HTML5 tags outside the original allowlist must still be recognized.
            (
                {"constraints": {"format": "html"}},
                {"text": "<section>Act now</section>"},
            ),
            (
                {"constraints": {"format": "html"}},
                {"text": "Offer valid until <time>March 2026</time>, per <cite>the memo</cite>."},
            ),
            # Markdown lists, blockquotes, and inline code are markup too, not just bold/links.
            (
                {"constraints": {"format": "markdown"}},
                {"text": "- Save 20%\n- Free shipping\n- Money-back guarantee"},
            ),
            (
                {"constraints": {"format": "markdown"}},
                {"text": "1. Sign up\n2. Claim the discount"},
            ),
            (
                {"constraints": {"format": "markdown"}},
                {"text": "> Act before the offer expires."},
            ),
            (
                {"constraints": {"format": "markdown"}},
                {"text": "Use code `SAVE20` at checkout."},
            ),
            # An integer-valued float length (schema `type: integer` allows 10.0) is honored.
            ({"constraints": {"length": 20.0}}, {"text": "Short persuasion."}),
            # A dash/digit/quote at the start of a *new sentence* (not a real block start) is
            # prose, not markdown — block markers only count at text-start or after a blank line.
            ({}, {"text": "Deal expires soon.\n- this is not a list, just a dash-prefixed sentence."}),
            ({}, {"text": "Save now.\n3. is the number of days left."}),
            ({}, {"text": "Offer ends.\n> 50% of customers already upgraded."}),
            # A void element (img/br/hr) with a long attribute value must still be recognized
            # as HTML — the detector must not truncate long attribute spans.
            (
                {"constraints": {"format": "html"}},
                {
                    "text": (
                        '<img src="https://cdn.example.com/promo/'
                        + "x" * 220
                        + '.png" alt="Limited time offer">'
                    )
                },
            ),
            # A blank line with trailing whitespace (common LLM artifact) still starts a
            # markdown block.
            (
                {"constraints": {"format": "markdown"}},
                {"text": "Save today.\n \n- 20% off\n- Free shipping"},
            ),
            # mailto:/tel: links are valid markdown link targets too, not just http(s) URLs.
            (
                {"constraints": {"format": "markdown"}},
                {"text": "Ready to upgrade? [Email our team](mailto:sales@example.com) today."},
            ),
            (
                {"constraints": {"format": "markdown"}},
                {"text": "Prefer to talk? [Call us](tel:+15551234567) now."},
            ),
            # Boolean HTML attributes (no "=") are still real markup.
            ({"constraints": {"format": "html"}}, {"text": "Grab it now <img disabled>."}),
            ({"constraints": {"format": "html"}}, {"text": "<hr noshade>"}),
            # Python dunder identifiers are not markdown bold, despite the same __word__ shape.
            ({}, {"text": "Configure __init__ before shipping."}),
            ({}, {"text": "Run __main__ guard first."}),
            # Genuine single-word bold is still detected.
            ({"constraints": {"format": "markdown"}}, {"text": "This is __great__ news."}),
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
            # constraints.format == "markdown" must also require markup, same as "html".
            ({"constraints": {"format": "markdown"}}, {"text": "Plain persuasive text."}),
            # An integer-valued float length (10.0) must still be enforced, not silently
            # ignored because it isn't a plain int.
            ({"constraints": {"length": 5.0}}, {"text": "This text is too long."}),
            # Each format must show its *own* markup kind: markdown-only text doesn't satisfy
            # an html request, and html-only text doesn't satisfy a markdown request.
            ({"constraints": {"format": "html"}}, {"text": "**Act now** and save."}),
            ({"constraints": {"format": "markdown"}}, {"text": "Act <b>now</b> and save."}),
            # Boolean HTML attributes are markup, so plain_text must still reject them.
            ({}, {"text": "Grab it now <img disabled>."}),
            # A dunder identifier is not markdown, so it can't satisfy a markdown format request.
            ({"constraints": {"format": "markdown"}}, {"text": "Configure __init__ before shipping."}),
            ({}, None),
            ({}, {"text": 123}),
        ],
    )
    def test_rejects(self, input_payload: dict, output: dict | None) -> None:
        with pytest.raises(StructuredOutputValidationError):
            self.validator.validate(input_payload=input_payload, output=output)
