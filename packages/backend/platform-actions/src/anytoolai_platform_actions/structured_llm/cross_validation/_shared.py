from __future__ import annotations

import math
import re
from datetime import date
from typing import Any, Mapping

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
