from __future__ import annotations

from typing import Any


def extract_fields() -> list[dict[str, Any]]:
    """Fresh A01 field definitions shared by runtime, API and worker tests."""
    return [
        {
            "name": "deadline",
            "type": "string",
            "description": "Project deadline mentioned in the text.",
            "required": True,
        },
        {
            "name": "budget",
            "type": "string",
            "description": "Budget mentioned in the text.",
            "required": False,
        },
        {
            "name": "deliverables",
            "type": "array_of_strings",
            "description": "Deliverables mentioned in the text.",
            "required": False,
        },
    ]
