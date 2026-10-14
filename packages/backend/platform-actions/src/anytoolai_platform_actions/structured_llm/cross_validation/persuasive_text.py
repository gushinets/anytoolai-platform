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

# The number formats a brief or a proposal is read in. Each token is one of these, longest form
# first, and yields one or more readings: a set of numbers it may mean. A text token is covered when
# any of its readings is in the context; the context offers every reading of every token. A number is
# compared by value ("05" is 5, "1,500" is 1500) and never by its digit groups, so a "$1,500" budget
# never offers "$500" as a price. A grouped figure has one magnitude: "1.500" is 1500, never 1.5,
# so a brief's "1.5 years" cannot cover a claimed "1,500 projects" (ambiguity fails closed). Digits
# inside an identifier are not a number: after a letter ("n8n", "v2"), after letters and a hyphen or
# dot ("GPT-4o", "ANY-656", "H.265"), or before an upper-case letter ("4K", "2FA"); a lower-case unit
# keeps its number ("50ms", "2h", "3500-word").
# ponytail: a fixed list of formats; add a format here (with its test) rather than a special case.
_NUMBER_TOKEN = re.compile(
    r"""(?<![^\W_])(?<![^\W\d_][-.])(?:  # not after a letter or digit, not after "GPT-"/"H."
    (?P<date>\d{1,2}[./]\d{1,2}[./]\d{2,4})                              # 10.5.2024, 05/01/24: three numbers
  | (?P<us>\d{1,3}(?:,\d{3})+)(?P<us_fraction>\.\d+)?                     # 1,500 and 1,234.50
  | (?P<eu>\d{1,3}(?:\.\d{3})+)(?P<eu_fraction>,\d+)?                     # 1.500 and 1.234,50
  | (?P<nbsp>\d{1,3}(?:[\u00a0\u202f]\d{3})+)(?P<nbsp_fraction>[.,]\d+)?  # 3\u202f500: an explicit group
  | (?P<space>\d{1,3}(?:\x20\d{3})+)(?P<space_fraction>[.,]\d+)?(?!-[^\W\d_])  # 3 200: 3200, or 3 and 200
  | (?P<decimal>\d+)(?P<decimal_fraction>[.,]\d+)                         # 1.5 and 1,5
  | (?P<integer>\d+)
)(?!\d)(?![A-Z\u0410-\u042f])""",
    re.VERBOSE,
)
_GROUP_SEPARATORS = str.maketrans("", "", ",.\u00a0\u202f\x20")


def _number(whole_digits: str, fraction: str = "") -> str:
    """A number by value: "05" is 5, "1234" with fraction "50" is 1234.5."""
    fraction = fraction.rstrip("0")
    return str(int(whole_digits)) + (f".{fraction}" if fraction else "")


def _readings(match: re.Match[str]) -> list[set[str]]:
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
        # an ASCII space may just separate two numbers ("3 posts of 200 words" written "3 200")
        readings.append({_number(part) for part in grouped.split("\x20")} | ({_number(fraction[1:])} if fraction else set()))
    return readings


def _number_tokens(value: str) -> list[list[set[str]]]:
    return [_readings(match) for match in _NUMBER_TOKEN.finditer(value)]


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
            invented = numbers_absent_from_context(text, input_payload.get("context"))
            if invented:
                raise _cross_validation_error(
                    f"text_has_numbers_absent_from_context:{_truncated_repr(','.join(invented))}"
                )
