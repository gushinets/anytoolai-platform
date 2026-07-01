from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PromptRef:
    prompt_ref: str
    version: int
    output_schema_ref: str
    template_path: str | None = None
    input_variables: list[str] = field(default_factory=list)
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
