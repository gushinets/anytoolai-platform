"""Client Update Writer tone and reply-order rules (ANY-851)."""

import json
from pathlib import Path

import pytest

PRODUCT = (
    Path(__file__).parents[1] / "src" / "anytoolai_freelancer_suite"
    / "products" / "client_update_writer"
)
UPDATE_PROMPT = PRODUCT / "prompts/update_compose_reply.v1.md"
REPLY_PROMPT = PRODUCT / "prompts/reply_draft_compose_reply.v1.md"
TONES = ["neutral", "warm", "firm"]


@pytest.mark.parametrize("prompt", [UPDATE_PROMPT, REPLY_PROMPT])
def test_tone_contract_is_present_verbatim(prompt: Path) -> None:
    text = " ".join(prompt.read_text(encoding="utf-8").split())
    assert "changes wording only, never content" in text
    assert (
        "Applied correctly, the three tones differ in phrasing and length while stating identical"
        in text
    )
    for tone in TONES:
        assert f"- `{tone}`:" in text


def test_update_prompt_keeps_client_actions_across_tones() -> None:
    text = " ".join(UPDATE_PROMPT.read_text(encoding="utf-8").split())
    assert "`warm` never drops a client action that `firm` states" in text
    assert "ask for the specific materials once in `call_to_action` in every tone" in text


def test_update_tone_preserves_language_and_uses_a_friendly_milestone_when_supported() -> None:
    text = " ".join(UPDATE_PROMPT.read_text(encoding="utf-8").split())
    assert "Apply every tone in that same language" in text
    assert "When the notes report good progress, use that friendly clause" in text


def test_reply_prompt_orders_acknowledgement_before_explanation() -> None:
    text = " ".join(REPLY_PROMPT.read_text(encoding="utf-8").split())
    assert "Build the reply in this order" in text
    assert "Never place the explanation between the acknowledgement and the decision" in text
    assert "An acknowledgement is not a concession" in text


@pytest.mark.parametrize("mode", ["update", "reply_draft"])
def test_tone_enum_matches_the_prompts(mode: str) -> None:
    schema = PRODUCT / "schemas" / f"{mode}_input.schema.json"
    assert json.loads(schema.read_text(encoding="utf-8"))["properties"]["tone"]["enum"] == TONES
