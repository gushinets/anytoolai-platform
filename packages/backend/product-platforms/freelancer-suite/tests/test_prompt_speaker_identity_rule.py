"""All four freelancer-voice prompts carry the same speaker-identity rule (ANY-629)."""

from pathlib import Path

import pytest

PRODUCTS = Path(__file__).parents[1] / "src" / "anytoolai_freelancer_suite" / "products"

PROMPTS = [
    "proposal_ai/prompts/compose_persuasive_text.v1.md",
    "client_update_writer/prompts/update_compose_reply.v1.md",
    "client_update_writer/prompts/reply_draft_compose_reply.v1.md",
    "client_update_writer/prompts/prepaid_request_compose_persuasive_text.v1.md",
]

RULE = (
    "Speak as the freelancer without a name or a gender. Do not introduce yourself by name and do "
    "not sign off with a name, a role or contact details unless the input states them: the input is "
    "the only source of such facts, so open with the point and close with the next step. In "
    "languages that mark the speaker's gender (for example Russian, Spanish, French), use "
    'constructions that do not: "я могу", "у меня есть опыт", "я сделаю"; never "готов(а)", '
    '"мог(ла)", "Готова" or "Готов" unless the input states the speaker\'s gender.'
)


@pytest.mark.parametrize("prompt", PROMPTS)
def test_prompt_carries_speaker_identity_rule_verbatim(prompt: str) -> None:
    text = " ".join((PRODUCTS / prompt).read_text(encoding="utf-8").split())
    assert RULE in text
