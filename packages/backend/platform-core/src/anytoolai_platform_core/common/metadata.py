from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def metadata_str(metadata: Mapping[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) and value else None
