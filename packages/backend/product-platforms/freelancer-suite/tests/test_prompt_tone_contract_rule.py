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
    assert "Use the current assignment when it supersedes an earlier one" in text
    assert "Ask the client once for each action still needed from them" in text
    assert "that they have not already arranged" in text
    assert "still missing because the client has not sent it is a pending client action" in text
    assert "request naming the item in a sentence separate from the status and deadline" in text
    assert "what the client owes or did not send does not satisfy the request" in text
    assert "address the client and name only the item" in text
    assert '"to me", "мне" or "envíame" and no response deadline unless supplied' in text
    assert "Ownership of an item alone does not assign the handoff" in text
    assert "If someone else is responsible, state their next step" in text
    assert "report the dependency without assigning the action to the client" in text
    assert "Naming the person waiting for an item does not identify its sender" in text
    assert "Report an already arranged handoff as a plan" in text
    assert "Omit requests for completed or cancelled actions" in text


def test_update_preserves_date_and_resolution_relationships() -> None:
    text = " ".join(UPDATE_PROMPT.read_text(encoding="utf-8").split())
    assert "Keep an explicit first-person commitment as a first-person action with its date" in text
    assert "connect the cause to that change explicitly" in text
    assert "name the stated actor in that cause" in text
    assert "Keep a later arrival separate, with only its own named roles" in text
    assert "explicitly make that link, and retain their certainty" in text


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
    assert "one short acknowledgement drawn from the client's message" in text
    assert "keep the author's answer for the next sentence" in text
    assert "very next sentence with the author's actual decision, answer or next step" in text
    assert "Use that sentence for the decision and its scope and certainty alone" in text
    assert "Use a new sentence for any context after the decision" in text
    assert "Disputed history follows the decision" in text


def test_reply_distinguishes_reported_claims_from_authorized_admissions() -> None:
    text = " ".join(REPLY_PROMPT.read_text(encoding="utf-8").split())
    assert "remains the client's account unless `intent` confirms it" in text
    assert "claims about prior requests, actions or agreements out of the acknowledgement" in text
    assert "the original participants, status and scope within the reported claim" in text
    assert "name the client or the client's side for an action they took" in text
    assert "use wording that includes the freelancer only if they were a participant" in text
    assert "Keep third parties in their stated roles" in text
    assert "name known participants when a pronoun would leave their role unclear" in text
    assert "short attributed direct quote with quotation marks and the original wording" in text
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


def test_reply_preserves_source_meaning_before_applying_tone() -> None:
    text = " ".join(REPLY_PROMPT.read_text(encoding="utf-8").split())
    source_rule = "Select the client's stated concern and the author's authorized answer"
    assert text.index(source_rule) < text.index("Build the reply in this order")
    assert "Keep the participants and their number local to each statement" in text
    assert "Use the singular address in the reply to that individual" in text
    assert "Preserve a group's expectation when the source states it" in text
    assert "An expression of empathy also needs to attribute the evaluation itself" in text
    assert "Use a cause or condition only where the source states it" in text
    assert "with the same direction and degree of certainty" in text


def test_reply_tone_changes_the_opening() -> None:
    text = " ".join(REPLY_PROMPT.read_text(encoding="utf-8").split())
    assert "free of first-person empathy, thanks and appreciation" in text
    assert "Start the first clause with what the client expected, felt or asked" in text
    assert "the client as that clause's grammatical subject" in text
    assert "Present an authorized offer as the option the author can offer" in text
    assert "`warm`: open with a short first-person expression of empathy" in text
    assert "put the central issue first in a compact statement" in text
    assert "keep the client's perception explicit" in text
    assert (
        "Make the point at issue the subject of the opening, including for a factual question"
        in text
    )
    assert "make the proposal directly" in text
    assert "A possibility or an action pending a check stays conditional" in text
    assert "Changing a modal verb or the word order alone is insufficient" in text


def test_reply_firm_keeps_both_actors_in_russian_and_spanish_conditions() -> None:
    text = " ".join(REPLY_PROMPT.read_text(encoding="utf-8").split())
    firm_rule = text.split("- `firm`:", 1)[1].split("The change in tone", 1)[0]
    assert "In Russian and Spanish, lead with the topic of a stated condition" in firm_rule
    assert "express each action with a known actor as a finite clause" in firm_rule
    assert "Give each clause its own stated actor and number" in firm_rule
    assert "Keep different actors separate" in firm_rule


@pytest.mark.parametrize("mode", ["update", "reply_draft"])
def test_tone_enum_matches_the_prompts(mode: str) -> None:
    schema = PRODUCT / "schemas" / f"{mode}_input.schema.json"
    assert json.loads(schema.read_text(encoding="utf-8"))["properties"]["tone"]["enum"] == TONES
