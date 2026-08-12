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


def _coerce_integer_valued(value: Any) -> int | None:
    """JSON Schema `type: integer` also accepts integer-valued floats (2.0), and JSON floats
    like `1.0` decode to Python `float` — a plain `isinstance(value, int)` check would wrongly
    reject those. Returns None for bools and non-integer-valued numbers."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


_FIELD_TYPE_CHECKS: Mapping[str, Any] = {
    "string": lambda value: isinstance(value, str),
    "number": _is_finite_number,
    "integer": lambda value: _coerce_integer_valued(value) is not None,
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


def _normalized_for_distinctness(text: str) -> str:
    """Whitespace-collapsed, case-insensitive form used to detect near-duplicate rewrites."""
    return " ".join(text.split()).casefold()


# Must match the "default" declared in generate_gap_rewrites_input.schema.json's `n` property
# (asserted by test_generate_gap_rewrites_schema.py) — jsonschema validation does not apply
# JSON Schema defaults to the payload, so this is the actual runtime default, not the schema.
GAP_REWRITES_DEFAULT_N = 3


class ExtractStructuredFieldsInputValidator:
    """Rejects semantically ambiguous A01 input.fields before any provider call is made."""

    def validate(self, *, input_payload: Mapping[str, Any]) -> None:
        field_specs = input_payload.get("fields")
        if not isinstance(field_specs, list):
            return
        seen_names: set[str] = set()
        for spec in field_specs:
            if not isinstance(spec, Mapping):
                continue
            name = spec.get("name")
            if not isinstance(name, str):
                continue
            if name in seen_names:
                raise ActionInputValidationError(
                    f"Action input validation failed: duplicate fields[*].name '{name}'."
                )
            seen_names.add(name)


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
                raise _cross_validation_error(f"unrequested_field:{name}")
        seen_missing_names: set[str] = set()
        for name in missing_fields:
            if name not in known_names:
                raise _cross_validation_error(f"unrequested_missing_field:{name}")
            if name in values:
                raise _cross_validation_error(f"field_marked_missing_but_present:{name}")
            if name in seen_missing_names:
                raise _cross_validation_error(f"duplicate_missing_field:{name}")
            seen_missing_names.add(name)

        missing_field_set = set(missing_fields)
        for name in known_names:
            if name not in values and name not in missing_field_set:
                raise _cross_validation_error(f"unreported_requested_field:{name}")

        if isinstance(confidence, Mapping):
            for name in confidence:
                if name not in values:
                    raise _cross_validation_error(f"confidence_for_unpopulated_field:{name}")

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
        taxonomy = input_payload.get("taxonomy")
        if not isinstance(taxonomy, list) or not taxonomy:
            return
        allowed_categories = set(taxonomy)
        issues = output.get("issues")
        if not isinstance(issues, list):
            raise _cross_validation_error("malformed_issue_detection_output")
        for issue in issues:
            if not isinstance(issue, Mapping):
                raise _cross_validation_error("malformed_issue_entry")
            category = issue.get("category")
            if category not in allowed_categories:
                raise _cross_validation_error(f"category_not_in_taxonomy:{category}")


class GapRewritesCrossValidator:
    """Validates A08 output.rewrites/best_pick: item count must equal the requested A08
    input.n (default 3), rewrites must be distinct after whitespace/case normalization, and
    best_pick must index into rewrites."""

    def validate(
        self,
        *,
        input_payload: Mapping[str, Any],
        output: Mapping[str, Any] | None,
    ) -> None:
        output = _require_output(output)
        requested_n = _coerce_integer_valued(input_payload.get("n", GAP_REWRITES_DEFAULT_N))
        if requested_n is None:
            requested_n = GAP_REWRITES_DEFAULT_N

        rewrites = output.get("rewrites")
        if not isinstance(rewrites, list):
            raise _cross_validation_error("malformed_gap_rewrites_output")
        if len(rewrites) != requested_n:
            raise _cross_validation_error(
                f"rewrite_count_mismatch:{len(rewrites)}!={requested_n}"
            )

        seen_normalized: set[str] = set()
        for rewrite in rewrites:
            if not isinstance(rewrite, Mapping):
                raise _cross_validation_error("malformed_rewrite_entry")
            text = rewrite.get("text")
            if not isinstance(text, str):
                raise _cross_validation_error("malformed_rewrite_text")
            normalized = _normalized_for_distinctness(text)
            if normalized in seen_normalized:
                raise _cross_validation_error("duplicate_rewrite_after_normalization")
            seen_normalized.add(normalized)

        best_pick = _coerce_integer_valued(output.get("best_pick"))
        if best_pick is None or not (0 <= best_pick < len(rewrites)):
            raise _cross_validation_error(f"best_pick_out_of_bounds:{output.get('best_pick')}")


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
# "Д*Ш*В", "宽*高*深") - as italic. Escaping a `*` sitting directly between two alphanumeric
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
