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
    assert "Apply every tone in that same language" in text
    for tone in TONES:
        assert f"- `{tone}`:" in text


def test_update_prompt_keeps_client_actions_across_tones() -> None:
    text = " ".join(UPDATE_PROMPT.read_text(encoding="utf-8").split())
    assert "`warm` never drops a client action that `firm` states" in text
    assert "must explicitly ask the client to send them once in every tone" in text
    assert "Skip the request only if the notes say the items arrived, are no longer needed" in text
    assert "retain the client as the sender in the account of the past delay" in text
    assert "Leave the receiver unspecified when the source does" in text
    assert "keep that wait in first-person plural" in text


def test_warm_update_uses_a_friendly_milestone_when_supported() -> None:
    text = " ".join(UPDATE_PROMPT.read_text(encoding="utf-8").split())
    assert "When the notes report good progress, use that friendly clause" in text


def test_update_rechecks_project_identity_against_source_notes() -> None:
    text = " ".join(UPDATE_PROMPT.read_text(encoding="utf-8").split())
    assert "include its client-facing name or full description" in text
    assert "Name the completed parts directly as ready" in text
    assert "Check the finished update against the notes for omissions" in text


def test_update_preserves_the_actor_of_commitments_in_every_tone() -> None:
    text = " ".join(UPDATE_PROMPT.read_text(encoding="utf-8").split())
    assert "Keep the actor, action, deliverable and date of a commitment together" in text
    assert "keep the freelancer as the explicit speaker of that commitment in every tone" in text


def test_reply_prompt_orders_acknowledgement_before_explanation() -> None:
    text = " ".join(REPLY_PROMPT.read_text(encoding="utf-8").split())
    assert "Build the reply in this order" in text
    assert "Never place the explanation between the acknowledgement and the decision" in text
    assert "give the brief or scope explanation in a later sentence" in text.lower()


def test_reply_distinguishes_reported_claims_from_authorized_admissions() -> None:
    text = " ".join(REPLY_PROMPT.read_text(encoding="utf-8").split())
    assert "remains the client's account unless `intent` confirms it" in text
    assert "Put any evaluative adjective inside the attributed perception" in text
    assert "claims about prior requests, actions or agreements out of the acknowledgement" in text
    assert "preserve the original actor, status, and scope of each claim" in text
    assert (
        "A request and a belief that the result differs from the agreement are separate claims"
        in text
    )
    assert "describe a term as agreed in the freelancer's voice when `intent` confirms it" in text
    assert (
        "An authorized admission belongs with the acknowledgement, including in a firm reply"
        in text
    )
    assert "do not admit fault" not in text
    assert "without adding an admission or apology unless `intent` authorizes it" in text
    assert "carry over its stated identifier" in text


def test_reply_tone_changes_the_opening() -> None:
    text = " ".join(REPLY_PROMPT.read_text(encoding="utf-8").split())
    assert "free of first-person empathy, thanks and appreciation" in text
    assert "`warm`: open with a short first-person expression of empathy" in text
    assert "For an opinion, name the client's expectation or reaction directly" in text
    assert "Changing a modal verb or the word order alone is insufficient" in text


@pytest.mark.parametrize("mode", ["update", "reply_draft"])
def test_tone_enum_matches_the_prompts(mode: str) -> None:
    schema = PRODUCT / "schemas" / f"{mode}_input.schema.json"
    assert json.loads(schema.read_text(encoding="utf-8"))["properties"]["tone"]["enum"] == TONES
