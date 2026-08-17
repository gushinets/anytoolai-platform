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
