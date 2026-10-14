from __future__ import annotations

import re
from typing import Any, Iterator, Mapping

from anytoolai_platform_core.actions.runner import ActionInputValidationError

from ._markup import _has_disallowed_plain_text_markup, _has_html_tag, _has_list, _has_visible_text
from ._shared import (
    _coerce_integer_valued,
    _cross_validation_error,
    _require_output,
    _truncated_repr,
)

# A thousands separator (comma, space, no-break/narrow space) between digit groups is read both ways:
# "3 200" is the one number 3200 and also the two numbers 3 and 200. A text number is accepted when it
# matches either reading of the context, and a text is accepted when either reading of the text is
# fully covered, so "3,200" in the input matches "3 200" in the text and "3 500-word posts" matches
# "3 posts of 500 words". An ASCII space before a digit group that starts a hyphenated unit ("3
# 500-word posts") is never a thousands separator: there it separates two numbers, so "3500" would
# be an invented one. A comma and the no-break spaces are explicit separators ("3,500-word" and
# "3\u00a0500-word" are 3500).
_THOUSANDS_SEPARATOR = re.compile(r"(?<=\d)(?:[,  ](?=\d{3}(?!\d))| (?=\d{3}(?!\d)(?!-[^\W\d_])))")
# A number as a reader sees it: a decimal ("1.5", "1,5") is one number, not 1 and 5, and digits that
# follow a letter belong to a name ("n8n", "v2", "H2O"), not to a quantity. A comma before exactly three
# digits is a thousands separator (handled by _THOUSANDS_SEPARATOR), so only one or two digits make a
# comma decimal; "10.5.2024" is a date, so a dot decimal must not be followed by another group.
_NUMBER = re.compile(r"(?<![^\W\d_])(\d+)(?:\.(\d+)(?![.\d])|,(\d{1,2})(?!\d))?")


def _context_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _context_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _context_strings(item)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield str(value)


def _digit_runs(value: str) -> tuple[set[str], set[str]]:
    """(numbers as written, numbers with thousands separators joined), compared by value: "05" and
    "5" are the same number, so "2024-05-01" in the input covers "May 1" in the text."""
    return _numbers(value), _numbers(_THOUSANDS_SEPARATOR.sub("", value))


def _numbers(value: str) -> set[str]:
    found = set()
    for whole, dot_fraction, comma_fraction in _NUMBER.findall(value):
        fraction = (dot_fraction or comma_fraction).rstrip("0")
        found.add(str(int(whole)) + (f".{fraction}" if fraction else ""))
    return found


class PersuasiveTextInputValidator:
    """Rejects an A06 input.constraints.forbidden_patterns entry that is not a valid regular
    expression before any provider call is made (a bad pattern is a caller bug the model cannot
    fix by retrying)."""

    def validate(self, *, input_payload: Mapping[str, Any]) -> None:
        constraints = input_payload.get("constraints")
        patterns = constraints.get("forbidden_patterns") if isinstance(constraints, Mapping) else None
        for pattern in patterns if isinstance(patterns, list) else []:
            try:
                re.compile(pattern)
            except (re.error, TypeError) as exc:
                raise ActionInputValidationError(
                    f"constraints.forbidden_patterns has an invalid regular expression: {exc}"
                ) from exc


class PersuasiveTextCrossValidator:
    """Validates A06 output.text against the caller-supplied input.constraints
    (length, format, forbidden_patterns, plain_text_lists, numbers_must_appear_in_context) that
    the static output schema cannot express because they vary per call."""

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
        text_format = constraints.get("format")

        # Code review finding (P2): `minLength: 1` on the output schema accepts a
        # whitespace-only string, and an HTML-formatted `<p></p>` has a real tag but no
        # actual content -- neither is usable persuasive text. Judged in the requested
        # format: "&nbsp;" is literal text as plain_text but blank as html.
        if not _has_visible_text(text, text_format):
            raise _cross_validation_error("text_has_no_visible_content")

        length = _coerce_integer_valued(constraints.get("length"))
        if length is not None and len(text) > length:
            raise _cross_validation_error(
                f"text_exceeds_constraints_length:{len(text)}>{length}"
            )

        # Prompt contract: "if it is plain_text or omitted, text must be copy-ready
        # (paragraphs and ordered/unordered lists are allowed; other Markdown/HTML markup
        # is not)".
        if text_format in (None, "plain_text") and _has_disallowed_plain_text_markup(text):
            raise _cross_validation_error("text_contains_markup_for_plain_text_format")
        # Markdown syntax alone doesn't satisfy "html" — it must contain an actual tag. Same
        # as the sibling A07 validator: "markdown" is not required to prove itself with a
        # decorative token (a plain paragraph is valid Markdown too).
        if text_format == "html" and not _has_html_tag(text):
            raise _cross_validation_error("text_missing_markup_for_html_format")

        # Product-level rules (ANY-656): all generic, so any A06 caller can opt in.
        # Case-insensitive on purpose: "Your Name" must also catch "your name".
        for pattern in constraints.get("forbidden_patterns") or []:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raise _cross_validation_error(
                    f"text_matches_forbidden_pattern:{_truncated_repr(match.group(0))}"
                )
        if constraints.get("plain_text_lists") == "forbidden" and _has_list(text):
            raise _cross_validation_error("text_contains_list")
        if constraints.get("numbers_must_appear_in_context"):
            allowed: set[str] = set()
            for chunk in _context_strings(input_payload.get("context")):
                allowed.update(*_digit_runs(chunk))
            as_written, joined = _digit_runs(text)
            if not (as_written <= allowed or joined <= allowed):
                invented = sorted(min(as_written - allowed, joined - allowed, key=len))
                raise _cross_validation_error(
                    f"text_has_numbers_absent_from_context:{_truncated_repr(','.join(invented))}"
                )
