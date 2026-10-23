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


# A fill-in-the-blank slot: square brackets that name a field the sender should fill in
# ("[Your Name]", "[Contact Information]", "[Client Name]", "[Ваше имя]"). Any bracket would also
# catch ordinary prose ("[sic]", "[FYI]", "[Project brief]") and no shape (case, word count) tells
# "[Ваше имя]" from "[Project brief]", so a slot is a bracket whose words name a field. Bracket
# content is bounded (1-60 characters, no nesting, no newline), so matching stays linear. Markdown
# links ("[a](u)", "[a][id]") and shortcut references whose "[label]: url" definition is in the
# text are not slots. Curly and angle brackets are legitimate in code and HTML, so they are not
# covered here; a product opts in through A06 forbidden_patterns.
# ponytail: EN/RU field words only; extend _FIELD_WORD when a product ships another language.
_BRACKETED = re.compile(r"(?<!\])\[([^\[\]\n]{1,60})\](?![(\[:])")
_REFERENCE_DEFINITION = re.compile(r"^ {0,3}\[([^\[\]\n]{1,60})\]:", re.MULTILINE)
_FIELD_WORD = re.compile(
    r"\b(?:your|name|names|contact|contacts|e-?mail|phone|date|address|company|title|signature"
    r"|client|recipient|insert|link|url|website"
    r"|ваш\w*|имя|имени|фамили\w*|контакт\w*|телефон\w*|почт\w*|дат[аеуы]|подпис\w*|компани\w*"
    r"|должност\w*|адрес\w*|клиент\w*|укажите|вставьте)\b",
    re.IGNORECASE,
)


def _reference_label(label: str) -> str:
    """CommonMark matches reference labels case-insensitively with whitespace collapsed."""
    return " ".join(label.split()).casefold()


def _find_unfilled_placeholder(text: str) -> str | None:
    """The first bracketed field slot in `text`, or None."""
    defined = {_reference_label(m.group(1)) for m in _REFERENCE_DEFINITION.finditer(text)}
    for match in _BRACKETED.finditer(text):
        if _reference_label(match.group(1)) not in defined and _FIELD_WORD.search(match.group(1)):
            return match.group(0)
    return None
