from __future__ import annotations

import json
from typing import Any

from anytoolai_platform_actions.structured_llm.executor import StructuredLlmActionExecutor


def _render(payload: dict[str, Any]) -> str:
    # _render_prompt uses no instance state
    return StructuredLlmActionExecutor._render_prompt(None, "T", payload)  # type: ignore[arg-type]


def test_render_prompt_keeps_non_ascii_input_as_text() -> None:
    payload = {"brief": "Привет, мир ä é 😀"}
    prompt = _render(payload)
    assert "Привет, мир ä é 😀" in prompt
    assert "\\u" not in prompt
    assert json.loads(prompt.split("\n\nInput payload:\n", 1)[1]) == payload


def test_render_prompt_ascii_input_is_unchanged() -> None:
    payload = {"b": 'q"uote\nnl\x01', "a": [1, None]}
    assert _render(payload) == "T\n\nInput payload:\n" + json.dumps(payload, sort_keys=True)
