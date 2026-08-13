from __future__ import annotations

import math
import re
import unicodedata
from datetime import date
from typing import Any, Mapping

from anytoolai_platform_core.actions.runner import ActionInputValidationError
from anytoolai_platform_core.structured_output.errors import StructuredOutputValidationError
from markdown_it import MarkdownIt

_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_iso_date_string(value: Any) -> bool:
    if not isinstance(value, str) or not _ISO_DATE_PATTERN.match(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return not isinstance(value, float) or math.isfinite(value)


_FIELD_TYPE_CHECKS: Mapping[str, Any] = {
    "string": lambda value: isinstance(value, str),
    "number": _is_finite_number,
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "boolean": lambda value: isinstance(value, bool),
    "date": _is_iso_date_string,
    "array_of_strings": lambda value: isinstance(value, list)
    and all(isinstance(item, str) for item in value),
}


def _cross_validation_error(reason: str) -> StructuredOutputValidationError:
    return StructuredOutputValidationError(
        reason=reason,
        error_type="ActionOutputCrossValidationError",
    )


def _require_output(output: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if output is None:
        raise _cross_validation_error("missing_output")
    return output


def _optional_membership_set(values: Any) -> set[Any] | None:
    """A non-empty list becomes an allow-set; a missing/empty list means "no constraint"."""
    if not isinstance(values, list) or not values:
        return None
    return set(values)


_TRUNCATED_REPR_LIMIT = 100


def _truncated_repr(value: Any) -> str:
    """Bounds free-form model text before it lands in exc.reason (retry prompt + debug artifact)."""
    text = str(value)
    if len(text) <= _TRUNCATED_REPR_LIMIT:
        return text
    return text[:_TRUNCATED_REPR_LIMIT] + "..."


def _reject_duplicate_ids(items: Any, *, id_field: str, error_label: str) -> None:
    """Raises ActionInputValidationError on the first repeated string `id_field` value
    across `items`. Malformed entries are ignored here - the input JSON schema already
    enforces their shape; this only adds the cross-item uniqueness a schema can't express."""
    if not isinstance(items, list):
        return
    seen_ids: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            continue
        item_id = item.get(id_field)
        if not isinstance(item_id, str):
            continue
        if item_id in seen_ids:
            raise ActionInputValidationError(
                f"Action input validation failed: duplicate {error_label} '{item_id}'."
            )
        seen_ids.add(item_id)


class ExtractStructuredFieldsInputValidator:
    """Rejects semantically ambiguous A01 input.fields before any provider call is made."""

    def validate(self, *, input_payload: Mapping[str, Any]) -> None:
        _reject_duplicate_ids(
            input_payload.get("fields"), id_field="name", error_label="fields[*].name"
        )


class ExtractStructuredFieldsCrossValidator:
    """Validates A01 output.values against the dynamic field specs from A01 input.fields."""

    def validate(
        self,
        *,
        input_payload: Mapping[str, Any],
        output: Mapping[str, Any] | None,
    ) -> None:
        output = _require_output(output)
        field_specs = input_payload.get("fields")
        if not isinstance(field_specs, list):
            return
        values = output.get("values")
        missing_fields = output.get("missing_fields")
        confidence = output.get("confidence")
        if not isinstance(values, Mapping) or not isinstance(missing_fields, list):
            raise _cross_validation_error("malformed_extraction_output")

        known_names = set()
        required_names = set()
        seen_names: set[str] = set()
        for spec in field_specs:
            if not isinstance(spec, Mapping):
                continue
            name = spec.get("name")
            if not isinstance(name, str):
                continue
            if name in seen_names:
                raise _cross_validation_error(f"duplicate_field_name:{name}")
            seen_names.add(name)
            known_names.add(name)
            if spec.get("required") is True:
                required_names.add(name)
            field_type = spec.get("type")
            type_check = _FIELD_TYPE_CHECKS.get(field_type)
            if type_check is None:
                raise _cross_validation_error(f"unknown_field_type:{name}:{field_type}")
            if name not in values:
                continue
            if not type_check(values[name]):
                raise _cross_validation_error(f"field_type_mismatch:{name}")

        for name in values:
            if name not in known_names:
                raise _cross_validation_error(f"unrequested_field:{_truncated_repr(name)}")
        seen_missing_names: set[str] = set()
        for name in missing_fields:
            if name not in known_names:
                raise _cross_validation_error(
                    f"unrequested_missing_field:{_truncated_repr(name)}"
                )
            if name in values:
                raise _cross_validation_error(
                    f"field_marked_missing_but_present:{_truncated_repr(name)}"
                )
            if name in seen_missing_names:
                raise _cross_validation_error(f"duplicate_missing_field:{_truncated_repr(name)}")
            seen_missing_names.add(name)

        missing_field_set = set(missing_fields)
        for name in known_names:
            if name not in values and name not in missing_field_set:
                raise _cross_validation_error(f"unreported_requested_field:{name}")

        if isinstance(confidence, Mapping):
            for name in confidence:
                if name not in values:
                    raise _cross_validation_error(
                        f"confidence_for_unpopulated_field:{_truncated_repr(name)}"
                    )

        strict = input_payload.get("strict") is True
        if strict:
            unresolved_required = [
                name for name in required_names if name not in values
            ]
            if unresolved_required:
                raise _cross_validation_error(
                    "strict_missing_required_fields:" + ",".join(sorted(unresolved_required))
                )


_QUESTION_PRIORITY_RANK: Mapping[str, int] = {"high": 0, "medium": 1, "low": 2}
_DEFAULT_MAX_QUESTIONS = 5


class GenerateClarifyingQuestionsCrossValidator:
    """Validates A05 output.questions against dynamic constraints from A05 input that the
    static output schema cannot express: each source_issue_index must be in bounds of
    input.issues, the list must not exceed input.max_questions (default 5), and questions must
    be ordered deterministically by priority (high, medium, low) then source issue order."""

    def validate(
        self,
        *,
        input_payload: Mapping[str, Any],
        output: Mapping[str, Any] | None,
    ) -> None:
        if output is None:
            raise _cross_validation_error("missing_output")
        questions = output.get("questions")
        if not isinstance(questions, list):
            raise _cross_validation_error("malformed_generate_clarifying_questions_output")

        issues = input_payload.get("issues")
        issue_count = len(issues) if isinstance(issues, list) else 0

        max_questions = input_payload.get("max_questions")
        if not isinstance(max_questions, int) or isinstance(max_questions, bool):
            max_questions = _DEFAULT_MAX_QUESTIONS
        if len(questions) > max_questions:
            raise _cross_validation_error(
                f"questions_exceed_max_questions:{len(questions)}>{max_questions}"
            )

        previous_rank: tuple[int, int] | None = None
        for question in questions:
            if not isinstance(question, Mapping):
                raise _cross_validation_error("malformed_question_entry")
            source_issue_index = question.get("source_issue_index")
            if (
                not isinstance(source_issue_index, int)
                or isinstance(source_issue_index, bool)
                or not (0 <= source_issue_index < issue_count)
            ):
                raise _cross_validation_error(
                    f"source_issue_index_out_of_bounds:{source_issue_index}"
                )
            priority_rank = _QUESTION_PRIORITY_RANK.get(question.get("priority"))
            if priority_rank is None:
                raise _cross_validation_error(f"unknown_priority:{question.get('priority')}")
            rank = (priority_rank, source_issue_index)
            if previous_rank is not None and rank < previous_rank:
                raise _cross_validation_error("questions_not_deterministically_ordered")
            previous_rank = rank


class DetectIssuesByTaxonomyCrossValidator:
    """Validates A04 output.issues categories against the taxonomy from A04 input.taxonomy."""

    def validate(
        self,
        *,
        input_payload: Mapping[str, Any],
        output: Mapping[str, Any] | None,
    ) -> None:
        output = _require_output(output)
        allowed_categories = _optional_membership_set(input_payload.get("taxonomy"))
        if allowed_categories is None:
            return
        issues = output.get("issues")
        if not isinstance(issues, list):
            raise _cross_validation_error("malformed_issue_detection_output")
        for issue in issues:
            if not isinstance(issue, Mapping):
                raise _cross_validation_error("malformed_issue_entry")
            category = issue.get("category")
            if category not in allowed_categories:
                raise _cross_validation_error(
                    f"category_not_in_taxonomy:{_truncated_repr(category)}"
                )


class ScoreMatchByRubricInputValidator:
    """Rejects semantically ambiguous A02 input.rubric before any provider call is made."""

    def validate(self, *, input_payload: Mapping[str, Any]) -> None:
        _reject_duplicate_ids(
            input_payload.get("rubric"), id_field="id", error_label="rubric[*].id"
        )


# No existing rubric-weighted-aggregate precedent in this module (every prior cross
# validator does membership/bounds/regex checks, not arithmetic), so this tolerance has no
# codebase default to match. 0.5 covers the model rounding a weighted average to the
# nearest whole point on the 0-100 scale without masking a genuinely wrong aggregate.
# Derived from the prompt's rounding instruction in
# configs/kernel/products/kernel_demo/prompts/score_match_by_rubric.v1.md ("rounded to the
# nearest whole number") -
# TestScoreMatchByRubricAggregateToleranceMatchesPrompt::test_prompt_still_instructs_rounding_to_nearest_whole_number
# in test_cross_validation.py pins that exact phrase so a prompt-side rounding change (e.g.
# to nearest 5 points) can't drift out of sync with this constant unnoticed.
_SCORE_MATCH_AGGREGATE_TOLERANCE = 0.5


class ScoreMatchByRubricCrossValidator:
    """Validates A02 output.criterion_scores/score against the dynamic rubric from A02
    input.rubric: every criterion_id must map exactly once to a rubric item (exists +
    unique + exhaustive), and the aggregate `score` must match the rubric-weighted average
    of criterion_scores within tolerance, recomputed outside the model response."""

    def validate(
        self,
        *,
        input_payload: Mapping[str, Any],
        output: Mapping[str, Any] | None,
    ) -> None:
        output = _require_output(output)
        rubric = input_payload.get("rubric")
        if not isinstance(rubric, list):
            return
        rubric_weights: dict[str, float] = {}
        total_weight = 0.0
        for criterion in rubric:
            if not isinstance(criterion, Mapping):
                continue
            criterion_id = criterion.get("id")
            weight = criterion.get("weight")
            if isinstance(criterion_id, str) and _is_finite_number(weight):
                rubric_weights[criterion_id] = float(weight)
                total_weight += float(weight)
        if not rubric_weights:
            return

        criterion_scores = output.get("criterion_scores")
        if not isinstance(criterion_scores, list):
            raise _cross_validation_error("malformed_score_match_output")

        seen_ids: set[str] = set()
        weighted_sum = 0.0
        for entry in criterion_scores:
            if not isinstance(entry, Mapping):
                raise _cross_validation_error("malformed_criterion_score_entry")
            criterion_id = entry.get("criterion_id")
            weight = rubric_weights.get(criterion_id)
            if weight is None:
                raise _cross_validation_error(
                    f"criterion_id_not_in_rubric:{_truncated_repr(criterion_id)}"
                )
            if criterion_id in seen_ids:
                raise _cross_validation_error(
                    f"duplicate_criterion_id:{_truncated_repr(criterion_id)}"
                )
            seen_ids.add(criterion_id)
            score = entry.get("score")
            if not _is_finite_number(score):
                raise _cross_validation_error(
                    f"invalid_criterion_score:{_truncated_repr(score)}"
                )
            weighted_sum += weight * float(score)

        missing_ids = rubric_weights.keys() - seen_ids
        if missing_ids:
            raise _cross_validation_error(
                "rubric_criteria_missing_from_output:" + ",".join(sorted(missing_ids))
            )

        expected_score = weighted_sum / total_weight
        # Individually-finite weights can still overflow float64 to `inf` once summed/
        # multiplied (schema only enforces `weight > 0`, no upper bound), producing
        # `inf / inf = nan`. Every comparison against `nan` is False in Python, so without
        # this check a `nan` expected_score would silently accept any reported_score.
        if not math.isfinite(expected_score):
            raise _cross_validation_error(
                f"aggregate_expected_score_not_finite:{_truncated_repr(expected_score)}"
            )
        reported_score = output.get("score")
        if not _is_finite_number(reported_score):
            raise _cross_validation_error(
                f"invalid_aggregate_score:{_truncated_repr(reported_score)}"
            )
        if abs(float(reported_score) - expected_score) > _SCORE_MATCH_AGGREGATE_TOLERANCE:
            raise _cross_validation_error(
                f"aggregate_score_mismatch:{reported_score}!={expected_score:.4f}"
            )


class SynthesizeAngleCrossValidator:
    """Validates A09 output.angle/secondary_angle against the options from A09 input.options."""

    def validate(
        self,
        *,
        input_payload: Mapping[str, Any],
        output: Mapping[str, Any] | None,
    ) -> None:
        output = _require_output(output)
        allowed_options = _optional_membership_set(input_payload.get("options"))
        if allowed_options is None:
            return
        angle = output.get("angle")
        if angle not in allowed_options:
            raise _cross_validation_error(f"angle_not_in_options:{_truncated_repr(angle)}")
        secondary_angle = output.get("secondary_angle")
        if secondary_angle is not None and secondary_angle not in allowed_options:
            raise _cross_validation_error(
                f"secondary_angle_not_in_options:{_truncated_repr(secondary_angle)}"
            )


# A hand-rolled tag-name allowlist keeps missing real constructs (svg/math, custom
# elements like <x-card>, comments, doctypes) no matter how many names get added, and a
# bare `<[a-zA-Z][^>]*>` regex over-matches non-markup bracketed text like "<Tuesday>". A
# real HTML tokenizer resolves both: markdown-it-py's `html_inline`/`html_block` rules
# recognize every HTML5 construct (tags of any name, comments, doctypes, CDATA, ...) by
# parsing the actual grammar, not by enumerating known names.
_HTML_RENDERER = MarkdownIt("gfm-like")
_HTML_RENDERER.options["linkify"] = False
_HTML_RENDERER.options["html"] = True

# With `html` disabled, raw "<...>" is inert (never a markup signal here — _has_html_tag
# covers it separately), so only genuine CommonMark/GFM syntax (bold, tables, code fences,
# strikethrough, emphasis pairing rules, ...) is left to detect, all by the same real
# parser instead of a growing pile of regexes.
_MARKDOWN_RENDERER = MarkdownIt("gfm-like")
_MARKDOWN_RENDERER.options["linkify"] = False
_MARKDOWN_RENDERER.options["html"] = False

# Token types a plain paragraph of text (no formatting) produces on its own.
_PLAIN_TEXT_TOKEN_TYPES = frozenset({"paragraph_open", "paragraph_close", "inline", "text", "softbreak"})

# CommonMark's real emphasis rule allows an unspaced `*` to open/close emphasis intraword
# (unlike `_`), so a parser alone flags plain arithmetic/dimension expressions - numeric
# ("2*3*4"), variable ("a*b*c", "2*x*4"), symbolic ("L*W*H"), or localized (
# "Д*Ш*в", "宽*高*深") - as italic. Escaping a `*` sitting directly between two alphanumeric
# characters makes CommonMark treat it as literal punctuation instead, while leaving
# whitespace/punctuation-flanked emphasis (e.g. "*actual*") to the parser's real rules.
# `str.isalnum()` is Unicode-aware (unlike an `[A-Za-z0-9]` character class), so this also
# covers non-ASCII scripts. A combining mark (Unicode category Mn/Mc/Me - accents, niqud,
# tashkil, matras, ...) is not itself alphanumeric but always attaches to whatever character
# precedes it, so a `*` right after one must be judged by that base character, not the mark -
# otherwise a mark stuck to punctuation (e.g. "!" + combining acute) would wrongly count as
# flanking material and swallow real emphasis. Only the left side needs this walk-back: marks
# trail their base character, so they never sit between `*` and the start of a word on the
# right.
_ASTERISK = re.compile(r"\*")


def _base_character_before(value: str, index: int) -> str | None:
    while index >= 0 and unicodedata.category(value[index]).startswith("M"):
        index -= 1
    return value[index] if index >= 0 else None


def _escape_alnum_flanked_asterisks(value: str) -> str:
    def _escape(match: re.Match[str]) -> str:
        index = match.start()
        before = _base_character_before(value, index - 1)
        after = value[index + 1] if index + 1 < len(value) else None
        if before is not None and before.isalnum() and after is not None and after.isalnum():
            return "\\*"
        return "*"

    return _ASTERISK.sub(_escape, value)


def _flatten_token_types(tokens: Any) -> Any:
    for token in tokens:
        yield token.type
        for child in token.children or ():
            yield child.type


def _has_html_tag(value: str) -> bool:
    # html_inline/html_block are the only token types the "html"-enabled parser adds on
    # top of the plain/markdown ones, so this is unaffected by any markdown syntax also
    # present in the same text.
    return any(
        token_type.startswith("html_")
        for token_type in _flatten_token_types(_HTML_RENDERER.parse(value))
    )


def _has_markdown(value: str) -> bool:
    value = _escape_alnum_flanked_asterisks(value)
    return any(
        token_type not in _PLAIN_TEXT_TOKEN_TYPES
        for token_type in _flatten_token_types(_MARKDOWN_RENDERER.parse(value))
    )


def _has_markup(value: str) -> bool:
    return _has_html_tag(value) or _has_markdown(value)


class PersuasiveTextCrossValidator:
    """Validates A06 output.text against the caller-supplied input.constraints
    (length, format) that the static output schema cannot express because they vary per
    call."""

    def validate(
        self,
        *,
        input_payload: Mapping[str, Any],
        output: Mapping[str, Any] | None,
    ) -> None:
        output = _require_output(output)
        text = output.get("text")
        if not isinstance(text, str):
            raise _cross_validation_error("malformed_compose_persuasive_text_output")
        constraints = input_payload.get("constraints")
        constraints = constraints if isinstance(constraints, Mapping) else {}

        # JSON Schema `type: integer` also accepts integer-valued floats (10.0), so a plain
        # `isinstance(length, int)` check silently drops the limit for those.
        length = constraints.get("length")
        if isinstance(length, bool):
            length = None
        elif isinstance(length, float) and length.is_integer():
            length = int(length)
        elif not isinstance(length, int):
            length = None
        if length is not None and len(text) > length:
            raise _cross_validation_error(
                f"text_exceeds_constraints_length:{len(text)}>{length}"
            )

        # Prompt contract: "if it is plain_text or omitted, text must contain no markup".
        text_format = constraints.get("format")
        if text_format in (None, "plain_text") and _has_markup(text):
            raise _cross_validation_error("text_contains_markup_for_plain_text_format")
        # Markdown syntax alone doesn't satisfy "html" — it must contain an actual tag. Same
        # as the sibling A07 validator: "markdown" is not required to prove itself with a
        # decorative token (a plain paragraph is valid Markdown too).
        if text_format == "html" and not _has_html_tag(text):
            raise _cross_validation_error("text_missing_markup_for_html_format")


class ComposeReplyCrossValidator:
    """Validates A07 output.text against the caller-supplied input.constraints
    (max_length, output_format) that the static output schema cannot express because they
    vary per call."""

    def validate(
        self,
        *,
        input_payload: Mapping[str, Any],
        output: Mapping[str, Any] | None,
    ) -> None:
        if output is None:
            raise _cross_validation_error("missing_output")
        text = output.get("text")
        if not isinstance(text, str):
            raise _cross_validation_error("malformed_compose_reply_output")
        call_to_action = output.get("call_to_action")
        constraints = input_payload.get("constraints")
        constraints = constraints if isinstance(constraints, Mapping) else {}

        max_length = constraints.get("max_length")
        if (
            isinstance(max_length, int)
            and not isinstance(max_length, bool)
            and len(text) > max_length
        ):
            raise _cross_validation_error(
                f"text_exceeds_constraints_max_length:{len(text)}>{max_length}"
            )

        # Prompt contract: "if it is plain_text or omitted, text must contain no markup".
        output_format = constraints.get("output_format")
        if output_format in (None, "plain_text") and _has_markup(text):
            raise _cross_validation_error("text_contains_markup_for_plain_text_format")
        # Only the main body is required to *prove* html-ness; a short call_to_action
        # (e.g. "Book a call") is plausibly plain text even inside an HTML-formatted reply.
        # Markdown syntax alone doesn't satisfy "html" — it must contain an actual tag.
        if output_format == "html" and not _has_html_tag(text):
            raise _cross_validation_error("text_missing_markup_for_html_format")
        if (
            output_format in (None, "plain_text")
            and isinstance(call_to_action, str)
            and _has_markup(call_to_action)
        ):
            raise _cross_validation_error(
                "call_to_action_contains_markup_for_plain_text_format"
            )
