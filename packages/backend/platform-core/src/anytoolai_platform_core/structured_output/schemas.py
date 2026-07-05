from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


def normalize_schema_mapping(schema: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if schema is None:
        return None
    return normalize_mapping(schema)


def normalize_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): normalize_value(item)
        for key, item in value.items()
    }


def normalize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return normalize_mapping(value)
    if isinstance(value, tuple):
        return [normalize_value(item) for item in value]
    if isinstance(value, list):
        return [normalize_value(item) for item in value]
    return value


@dataclass(frozen=True)
class StructuredOutputContract:
    schema: dict[str, Any] | None = None
    requires_object: bool = True
    schema_ref: str | None = None
    schema_version: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
