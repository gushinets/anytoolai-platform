from __future__ import annotations

from typing import Any, Mapping

from ._markup import _has_disallowed_plain_text_markup, _has_html_tag, _has_visible_text
from ._shared import _coerce_integer_valued, _cross_validation_error, _require_output


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
        # Code review finding (P2): `minLength: 1` on the output schema accepts a
        # whitespace-only string, and an HTML-formatted `<p></p>` has a real tag but no
        # actual content -- neither is usable persuasive text.
        if not _has_visible_text(text):
            raise _cross_validation_error("text_has_no_visible_content")
        constraints = input_payload.get("constraints")
        constraints = constraints if isinstance(constraints, Mapping) else {}

        length = _coerce_integer_valued(constraints.get("length"))
        if length is not None and len(text) > length:
            raise _cross_validation_error(
                f"text_exceeds_constraints_length:{len(text)}>{length}"
            )

        # Prompt contract: "if it is plain_text or omitted, text must be copy-ready
        # (paragraphs and ordered/unordered lists are allowed; other Markdown/HTML markup
        # is not)".
        text_format = constraints.get("format")
        if text_format in (None, "plain_text") and _has_disallowed_plain_text_markup(text):
            raise _cross_validation_error("text_contains_markup_for_plain_text_format")
        # Markdown syntax alone doesn't satisfy "html" — it must contain an actual tag. Same
        # as the sibling A07 validator: "markdown" is not required to prove itself with a
        # decorative token (a plain paragraph is valid Markdown too).
        if text_format == "html" and not _has_html_tag(text):
            raise _cross_validation_error("text_missing_markup_for_html_format")
