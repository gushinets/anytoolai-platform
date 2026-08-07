from __future__ import annotations

import json
from typing import Any

LITERAL_SOURCE_PREFIX = "literal:"


def _reject_non_finite_constant(token: str) -> Any:
    raise json.JSONDecodeError(
        f"literal JSON does not allow non-finite constant: {token}",
        token,
        0,
    )


def parse_strict_literal_json(payload: str) -> Any:
    """Parses a `literal:` source payload as strict JSON.

    Python's `json.loads` non-standardly accepts the bare tokens `NaN`, `Infinity`, and
    `-Infinity` by default. A config-owned literal is meant to be plain, portable JSON, so this
    rejects those tokens the same way as any other malformed literal: by raising
    `json.JSONDecodeError`.
    """
    return json.loads(payload, parse_constant=_reject_non_finite_constant)
