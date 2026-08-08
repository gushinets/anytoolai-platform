from __future__ import annotations

import json
from typing import Any


def _reject_non_finite_constant(token: str) -> Any:
    raise json.JSONDecodeError(
        f"JSON does not allow non-finite constant: {token}",
        token,
        0,
    )


def parse_strict_json(payload: str) -> Any:
    """Parses JSON, rejecting the non-standard `NaN`/`Infinity`/`-Infinity` tokens.

    Python's `json.loads` non-standardly accepts those bare tokens by default, decoding them to
    `float("nan")`/`float("inf")`/`float("-inf")`. Every caller of this helper treats its input as
    portable, standard JSON (a config-owned `literal:` source, or a provider's structured output
    text), so this raises `json.JSONDecodeError` for them the same way as any other malformed
    input instead of silently producing a non-finite value.
    """
    return json.loads(payload, parse_constant=_reject_non_finite_constant)
