from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Iterator, Mapping

import re2
from anytoolai_platform_core.actions.runner import ActionInputValidationError

from ._markup import _has_disallowed_plain_text_markup, _has_html_tag, _has_list, _has_visible_text
from ._shared import (
    _coerce_integer_valued,
    _cross_validation_error,
    _require_output,
    _truncated_repr,
)

# How a brief or a proposal is read for numbers. There is no list of locale formats: a number token
# is an optional sign, digit groups joined by separators (".", ",", "'", "\u2019", a no-break space,
# or a plain space before exactly three digits that do not start a hyphenated unit) and an optional
# "k"/"K"/"M" scale, and its shape alone decides what it means:
#   1. the last separator is "." or "," and differs from the one grouping before it: a fraction
#      ("1,234.50", "1.234,50", "3 200,50", "1'500.50");
#   2. one repeated separator before groups of three digits (or Indian "1,50,000"): thousands
#      ("1,500", "1.500", "1'500", "3 200", "1,234,000") -- "1.500" is 1500, never 1.5, so
#      ambiguity fails closed -- except that a single "." or "," before a scale is the decimal mark
#      ("$1.234k" is 1234, "1,5k" is 1500);
#   3. a single "." or "," before any other group: a fraction ("1.5", "12,50", ".5M" is 500000);
#   4. anything else is a sequence of numbers, each offered on its own (a date "10.5.2024", "1.2.3").
# A number is compared by value ("05" is 5, "1,500" is 1500) and never by its digit groups, so a
# "$1,500" budget never offers "$500" and a "CHF 1'500" fee never offers "CHF 1". The sign is part
# of the value ("-20%" is not "+20%", "+20" is 20) when nothing but space or punctuation precedes it:
# "10-20%", "2-3 weeks" and "2-to-3-week" are ranges. "3 500-word" is 3 and 500.
#
# Letters next to digits are decided by one rule, the first character of the word: a word that starts
# with a letter is a name and offers no number at all ("n8n", "v2", "GPT-4.1-mini", "gpt_4o",
# "task_id_42", "ANY-656", "H.265"); a word that starts with a digit is a quantity, read by the
# grammar, whose trailing letters are a unit and are ignored ("16GB", "12V", "60Hz", "50ms", "2FA",
# "3500-word", "10th"), except that a whole suffix "k"/"K"/"M" scales the number ("$20k" is 20000,
# "4K" is 4000, "1.5M" is 1500000; "5km" is 5). There is no unit list and no case rule: a word starts
# with a letter or with a digit, and that is the whole decision. Fixed contract (ANY-656): whether a
# digit inside a word is a quantity ("4K" footage, "2FA") and who may assert a number (the client's
# budget is not the freelancer's fee) are semantic questions; they are not decided here and are not
# bugs of this rule. A false rejection of a realistic input is.
# A word that starts with a letter. Not right after "<digit>-": that is a numeric range
# ("2-to-3-week" keeps its 3); a name like "GPT-4.1-mini" starts at its letter and absorbs its hyphens.
_NAME = re.compile(r"(?<!\w)(?<!\d-)[^\W\d_]\w*(?:[.-]\w+)*")
_NUMBER_TOKEN = re.compile(
    r"""(?<![^\W_])                                 # not after a letter, digit or underscore
    (?P<sign>[-+\u2212](?=[.,]?\d))?
    (?P<body>(?:\d+|[.,]\d+)(?:(?:[.,'\u2019\u00a0\u202f]|\x20(?=\d{3}(?!\d|-[^\W\d_])))\d+)*)
    (?P<scale>[kKM](?![^\W\d_]))?""",
    re.VERBOSE,
)
_SCALE = {"k": 1000, "K": 1000, "M": 1_000_000}
_DECIMAL_MARKS = ".,"
_MINUS = ("-", "\u2212")
# the typographic hyphens join a word like "-" does ("3 500\u2011word", "GPT\u20114.1"); dashes do not
_HYPHENS = str.maketrans("\u2010\u2011", "--")


def _without_names(value: str) -> str:
    """Blank every word that starts with a letter and carries a digit; "May 5" and "16GB" stay."""
    return _NAME.sub(lambda m: " " if any(c.isdigit() for c in m.group(0)) else m.group(0), value)


def _is_grouped(groups: list[str], separators: list[str]) -> bool:
    """Digit groups split by one repeated separator: 1,500 / 1.234.567 / 1'500 / 3 200 / 1,50,000."""
    if len(set(separators)) != 1 or len(groups[-1]) != 3:
        return False
    first, middle = groups[0], groups[1:-1]
    if len(first) <= 3 and all(len(group) == 3 for group in middle):
        return True
    return separators[0] == "," and len(first) <= 2 and all(len(group) == 2 for group in middle)  # lakh


def _magnitude(body: str, scaled: bool) -> Decimal | None:
    """The one value a token body means by the rules above, or None for a sequence of numbers."""
    if body[0] in _DECIMAL_MARKS:
        return Decimal("0." + body[1:]) if body[1:].isdigit() else None
    parts = re.split(r"(\D)", body)
    groups, separators = parts[0::2], parts[1::2]
    if not separators:
        return Decimal(body)
    *grouping, last = separators
    if last in _DECIMAL_MARKS and grouping and last not in grouping and _is_grouped(groups[:-1], grouping):
        return Decimal("".join(groups[:-1]) + "." + groups[-1])
    if _is_grouped(groups, separators) and not (scaled and not grouping and last in _DECIMAL_MARKS):
        return Decimal("".join(groups))
    if not grouping and last in _DECIMAL_MARKS:
        return Decimal(groups[0] + "." + groups[1])
    return None


def _canonical(value: Decimal) -> str:
    """A number by value: "05" is 5, "1234.50" is 1234.5, "-0" is 0."""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def _token_numbers(match: re.Match[str]) -> set[str]:
    body, scale = match.group("body"), match.group("scale")
    value = _magnitude(body, scaled=scale is not None)
    if value is None:
        return {_canonical(Decimal(group)) for group in re.split(r"\D", body) if group}
    if scale:
        value *= _SCALE[scale]  # exact: 1.2345k is 1234.5
    return {_canonical(-value if match.group("sign") in _MINUS else value)}


def _numbers(value: str) -> set[str]:
    value = _without_names(value.translate(_HYPHENS))
    return {number for match in _NUMBER_TOKEN.finditer(value) for number in _token_numbers(match)}


def numbers_absent_from_context(text: str, context: Any) -> list[str]:
    """The numbers in `text` that no number in `context` offers, shortest first; empty when every
    text number is covered. Shared with the ProposalAI eval script."""
    allowed = {number for chunk in _context_strings(context) for number in _numbers(chunk)}
    return sorted(_numbers(text) - allowed, key=len)


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


# A caller's forbidden_patterns run on Google RE2, not on a backtracking engine (`re`, `regex`):
# RE2 matches in linear time, caps its memory and refuses a repetition count above 1000 at
# compile time, so no pattern within the schema bounds (at most 32 patterns of at most 200
# characters) can hold a worker or exhaust its memory, whatever the model output. The price is the
# RE2 syntax: no lookaround or backreference, and `\w`, `\d`, `\s`, `\b` are ASCII (use `\pL` for
# any letter). An expression RE2 cannot compile is a caller bug, rejected before any provider call.
_FORBIDDEN_PATTERNS_MAX_ITEMS = 32
_FORBIDDEN_PATTERN_MAX_LENGTH = 200


def _compile_forbidden_pattern(pattern: str) -> re2._Regexp:
    options = re2.Options()
    options.case_sensitive = False  # "Your Name" must also catch "your name"
    options.log_errors = False  # a caller's bad pattern is reported by the exception, not stderr
    return re2.compile(pattern, options)


class PersuasiveTextInputValidator:
    """Rejects an A06 input.constraints.forbidden_patterns entry that is not a valid regular
    expression before any provider call is made (a bad pattern is a caller bug the model cannot
    fix by retrying)."""

    def validate(self, *, input_payload: Mapping[str, Any]) -> None:
        constraints = input_payload.get("constraints")
        patterns = constraints.get("forbidden_patterns") if isinstance(constraints, Mapping) else None
        if not isinstance(patterns, list):
            return
        if len(patterns) > _FORBIDDEN_PATTERNS_MAX_ITEMS:
            raise ActionInputValidationError(
                f"constraints.forbidden_patterns has {len(patterns)} entries, at most "
                f"{_FORBIDDEN_PATTERNS_MAX_ITEMS} are allowed"
            )
        for pattern in patterns:
            if isinstance(pattern, str) and len(pattern) > _FORBIDDEN_PATTERN_MAX_LENGTH:
                raise ActionInputValidationError(
                    "constraints.forbidden_patterns entry is longer than "
                    f"{_FORBIDDEN_PATTERN_MAX_LENGTH} characters"
                )
            try:
                _compile_forbidden_pattern(pattern)
            except (re2.error, TypeError) as exc:
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
        for pattern in constraints.get("forbidden_patterns") or []:
            match = _compile_forbidden_pattern(pattern).search(text)
            if match:
                raise _cross_validation_error(
                    f"text_matches_forbidden_pattern:{_truncated_repr(match.group(0))}"
                )
        if constraints.get("plain_text_lists") == "forbidden" and _has_list(text):
            raise _cross_validation_error("text_contains_list")
        if constraints.get("numbers_must_appear_in_context"):
            invented = numbers_absent_from_context(text, input_payload.get("context"))
            if invented:
                raise _cross_validation_error(
                    f"text_has_numbers_absent_from_context:{_truncated_repr(','.join(invented))}"
                )
