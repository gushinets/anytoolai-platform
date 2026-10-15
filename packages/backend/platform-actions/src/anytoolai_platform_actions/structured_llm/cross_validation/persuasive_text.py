from __future__ import annotations

import re
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

# The number formats a brief or a proposal is read in. Each token is one of these, longest form
# first, and yields one or more readings: a set of numbers it may mean. A text token is covered when
# any of its readings is in the context; the context offers every reading of every token. A number is
# compared by value ("05" is 5, "1,500" is 1500) and never by its digit groups, so a "$1,500" budget
# never offers "$500" as a price. A grouped figure has one magnitude: "1.500" is 1500, never 1.5,
# so a brief's "1.5 years" cannot cover a claimed "1,500 projects" (ambiguity fails closed).
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
_NAME = re.compile(r"(?<!\w)[^\W\d_]\w*(?:[.-]\w+)*")  # a word that starts with a letter
_NUMBER_TOKEN = re.compile(
    r"""(?<![^\W_])(?:  # not after a letter or digit
    (?P<date>\d{1,2}[./]\d{1,2}[./]\d{2,4})                              # 10.5.2024, 05/01/24: three numbers
  | (?P<us>\d{1,3}(?:,\d{3})+)(?P<us_fraction>\.\d+)?                     # 1,500 and 1,234.50
  | (?P<eu>\d{1,3}(?:\.\d{3})+)(?P<eu_fraction>,\d+)?                     # 1.500 and 1.234,50
  | (?P<nbsp>\d{1,3}(?:[\u00a0\u202f]\d{3})+)(?P<nbsp_fraction>[.,]\d+)?  # 3\u202f500: an explicit group
  | (?P<space>\d{1,3}(?:\x20\d{3})+)(?P<space_fraction>[.,]\d+)?(?!-[^\W\d_])  # 3 200: 3200, or 3 and 200
  | (?P<decimal>\d+)(?P<decimal_fraction>[.,]\d+)                         # 1.5 and 1,5
  | (?P<integer>\d+)
)(?!\d)(?P<scale>[kKM](?![^\W\d_]))?""",
    re.VERBOSE,
)
_SCALE = {"k": 1000, "K": 1000, "M": 1_000_000}
_GROUP_SEPARATORS = str.maketrans("", "", ",.\u00a0\u202f\x20")


def _without_names(value: str) -> str:
    """Blank every word that starts with a letter and carries a digit; "May 5" and "16GB" stay."""
    return _NAME.sub(lambda m: " " if any(c.isdigit() for c in m.group(0)) else m.group(0), value)


def _scaled(number: str, scale: str | None) -> str:
    if not scale:
        return number
    whole, _, fraction = number.partition(".")
    return str(int(whole) * _SCALE[scale] + (int(fraction) * _SCALE[scale] // 10 ** len(fraction) if fraction else 0))


def _number(whole_digits: str, fraction: str = "") -> str:
    """A number by value: "05" is 5, "1234" with fraction "50" is 1234.5."""
    fraction = fraction.rstrip("0")
    return str(int(whole_digits)) + (f".{fraction}" if fraction else "")


def _readings(match: re.Match[str]) -> list[set[str]]:
    return [{_scaled(number, match.group("scale")) for number in reading} for reading in _unscaled_readings(match)]


def _unscaled_readings(match: re.Match[str]) -> list[set[str]]:
    groups = match.groupdict()
    if groups["date"]:
        return [{_number(part) for part in re.split(r"[./]", groups["date"])}]
    if groups["decimal"]:
        return [{_number(groups["decimal"], groups["decimal_fraction"][1:])}]
    if groups["integer"]:
        return [{_number(groups["integer"])}]
    for kind in ("us", "eu", "nbsp", "space"):
        if groups[kind]:
            break
    grouped, fraction = groups[kind], groups[f"{kind}_fraction"] or ""
    readings = [{_number(grouped.translate(_GROUP_SEPARATORS), fraction[1:])}]
    if kind == "space":
        # an ASCII space may just separate two numbers ("3 posts of 200 words" written "3 200");
        # a fraction stays on the last of them: "3 200,50" is 3 and 200.5, never a separate 50
        *parts, last = grouped.split("\x20")
        readings.append({_number(part) for part in parts} | {_number(last, fraction[1:])})
    return readings


def _number_tokens(value: str) -> list[list[set[str]]]:
    return [_readings(match) for match in _NUMBER_TOKEN.finditer(_without_names(value))]


def numbers_absent_from_context(text: str, context: Any) -> list[str]:
    """The numbers in `text` that no reading of any number in `context` offers, shortest first;
    empty when every text number is covered. Shared with the ProposalAI eval script."""
    allowed: set[str] = set()
    for chunk in _context_strings(context):
        for readings in _number_tokens(chunk):
            allowed.update(*readings)
    invented: set[str] = set()
    for readings in _number_tokens(text):
        if not any(reading <= allowed for reading in readings):
            invented |= min((reading - allowed for reading in readings), key=len)
    return sorted(invented, key=len)


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
