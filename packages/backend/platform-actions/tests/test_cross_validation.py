from __future__ import annotations

import json

import pytest
from anytoolai_platform_actions.structured_llm.cross_validation import (
    DetectIssuesByTaxonomyCrossValidator,
    ExtractStructuredFieldsCrossValidator,
    ExtractStructuredFieldsInputValidator,
    GapRewritesCrossValidator,
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
