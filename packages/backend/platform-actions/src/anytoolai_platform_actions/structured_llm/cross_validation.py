from __future__ import annotations

import math
import re
from datetime import date
from typing import Any, Mapping

from anytoolai_platform_core.actions.runner import ActionInputValidationError
from anytoolai_platform_core.structured_output.errors import StructuredOutputValidationError

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


# ponytail: allowlisted common HTML5 tag names, not a full tokenizer — a real tokenizer
# would also accept "<a while longer>" as a start tag with boolean attributes, reintroducing
# the false-positive class the `=`/`/>` requirement below guards against. Upgrade to
# html.parser.HTMLParser + a real tag-name set only if callers need arbitrary/uncommon tags.
_HTML_TAG_NAMES = (
    "a|abbr|article|aside|b|blockquote|br|cite|code|dd|del|div|dl|dt|em|figcaption|figure|"
    "footer|h[1-6]|header|hr|i|img|ins|kbd|li|mark|nav|ol|p|pre|q|s|samp|section|small|span|"
    "strong|sub|summary|sup|table|tbody|td|tfoot|th|thead|time|tr|u|ul|var|wbr"
)
# ponytail: allowlisted HTML5 boolean-attribute names (disabled/checked/...), not arbitrary
# bare words — "<img disabled>" is real markup but "<b careful>" (round-1 false positive) has
# the same shape ("<tag> <one bare word> >"). Only a known attribute name distinguishes them.
_HTML_BOOLEAN_ATTRS = (
    "async|autofocus|autoplay|checked|compact|controls|default|defer|disabled|"
    "formnovalidate|hidden|ismap|loop|multiple|muted|nohref|noresize|noshade|"
    "novalidate|nowrap|open|readonly|required|reversed|scoped|selected"
)
# A short tag name (a/b/i/p/u) followed by ordinary bracketed words — e.g. "<a while longer>"
# — is not markup: it has no "/>" close, no "=" attribute, and no known boolean attribute, so
# require one of those after the tag name instead of accepting any `[^>]*` filler. The
# lookahead only *checks* for "="; the actual span is consumed possessively (`*+`, no
# backtracking into it), so this stays linear-time regardless of attribute length — unlike a
# `pre=post>` split with two backtracking `[^>]*` groups (quadratic on adversarial input) or a
# length-bounded split (wrongly rejects real long attributes, e.g. a long `<img src="...">` URL).
_HTML_TAG_PATTERN = re.compile(
    rf"</(?:{_HTML_TAG_NAMES})\b\s*>"
    rf"|<(?:{_HTML_TAG_NAMES})\b(?:"
    rf"\s*/?>"
    rf"|\s+(?=[^>]*=)[^>]*+>"
    rf"|(?:\s+(?:{_HTML_BOOLEAN_ATTRS})\b)+\s*/?>"
    rf")",
    re.IGNORECASE,
)

# Covers the common markdown constructs (bold, links, headings, lists, blockquotes, inline
# code). Deliberately excludes single `*`/`_` italics — too common in plain English asides
# ("the *actual* deadline") to blacklist without false-positiving on legitimate plain text.
# Block markers (list/numbered-list/blockquote) only count at the very start of the text or
# after a blank line (allowing trailing whitespace on that blank line — a common LLM
# formatting artifact), matching real markdown block syntax — a stray "\n- " or "\n> " inside
# an otherwise plain sentence is prose, not markdown (e.g. "Deal expires soon.\n- just a
# dash-prefixed sentence"). The link pattern requires a URL- or mailto:/tel:-shaped target so
# incidental "[word](word)" adjacency in prose doesn't count. Link *text* is bounded to 200
# chars (real link labels are short phrases, unlike the URL) — same quadratic-backtracking
# hazard as the earlier HTML-attribute regex: on input with many "[" and no "]", an unbounded
# `[^\]\n]+` makes `.search()` retry an O(remaining-length) failed match at every "[".
# Python dunder identifiers (__init__, __main__, ...) have the exact same shape as single-word
# markdown bold (__word__) — exclude the common ones by name so "Configure __init__ before
# shipping." isn't mistaken for bold, same allowlist tradeoff as the HTML tag names above.
_PYTHON_DUNDER_NAMES = (
    "init|main|str|repr|eq|ne|lt|le|gt|ge|hash|len|iter|next|enter|exit|call|new|del|"
    "getitem|setitem|delitem|contains|add|sub|mul|truediv|name|all|file|doc|version|"
    "dict|class|module|slots"
)
_MARKDOWN_BLOCK_START = r"(?:\A|\n[ \t]*\n)"
_MARKDOWN_PATTERN = re.compile(
    r"\*\*[^*\n]+\*\*"                                  # **bold**
    rf"|__(?!(?:{_PYTHON_DUNDER_NAMES})__)[^_\n]+__"     # __bold__, not __dunder__
    r"|\[[^\]\n]{1,200}\]\((?:https?://|mailto:|tel:|/|#)[^)\n]++\)"  # [text](url)
    rf"|{_MARKDOWN_BLOCK_START}#{{1,6}}\s"                # # heading
    rf"|{_MARKDOWN_BLOCK_START}[-*+]\s"                   # - bullet list item
    rf"|{_MARKDOWN_BLOCK_START}\d+\.\s"                   # 1. numbered list item
    rf"|{_MARKDOWN_BLOCK_START}>\s"                       # > blockquote
    r"|`[^`\n]+`",                                        # `inline code`
)


def _has_html_markup(value: str) -> bool:
    return _HTML_TAG_PATTERN.search(value) is not None


def _has_markdown_markup(value: str) -> bool:
    return _MARKDOWN_PATTERN.search(value) is not None


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

        # Only run the detector(s) the requested format actually needs — `_has_markdown_markup`
        # in particular can cost orders of magnitude more than `_has_html_markup` on the same
        # input, and an "html"/"markdown" request only ever needs one of the two.
        text_format = constraints.get("format")
        # Prompt contract: "if it is plain_text or omitted, text must contain no markup".
        if text_format in (None, "plain_text") and (
            _has_html_markup(text) or _has_markdown_markup(text)
        ):
            raise _cross_validation_error("text_contains_markup_for_plain_text_format")
        # Prompt contract: "if constraints.format is markdown or html, format text
        # accordingly" — each format must show its *own* kind of markup, not either kind
        # (plain markdown text shouldn't satisfy an html format request, and vice versa).
        if text_format == "html" and not _has_html_markup(text):
            raise _cross_validation_error("text_missing_markup_for_html_format")
        if text_format == "markdown" and not _has_markdown_markup(text):
            raise _cross_validation_error("text_missing_markup_for_markdown_format")
