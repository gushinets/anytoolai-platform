import json
from typing import Any


class StructuredOutputError(ValueError):
    pass


def parse_json_object(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StructuredOutputError(str(exc)) from exc
    if not isinstance(data, dict):
        raise StructuredOutputError("Expected JSON object")
    return data
