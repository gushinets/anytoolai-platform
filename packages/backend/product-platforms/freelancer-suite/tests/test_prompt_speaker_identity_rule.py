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
    "not sign off with a name, a role or contact details unless the input explicitly gives them as "
    "the freelancer's own (a name or signature in the client's message is the client's, not "
    "yours): the input is the only source of such facts, so open with the point. In "
    "languages that mark the speaker's gender (for example Russian, Spanish, French), write about "
    "yourself only in forms that do not, unless the input states the speaker's gender. In Russian "
    'the first-person past tense (with or without "я"), "чтобы я" with a verb and "сам"/"сама" '
    'mark gender just like "готов"/"готова": use the present or future tense or an impersonal '
    'phrase ("я могу", "у меня есть опыт", "я сделаю", "после этого начну", "чтобы начать работу", '
    '"новую дату пока не обещаю", "требования задаю я"), never "готов(а)", "мог(ла)", "чтобы я '
    'мог", "чтобы я начал", "не обещал", "я сама" or "Готова". Change the wording, not the facts, '
    "amounts, dates or actions."
)


@pytest.mark.parametrize("prompt", PROMPTS)
def test_prompt_carries_speaker_identity_rule_verbatim(prompt: str) -> None:
    text = " ".join((PRODUCTS / prompt).read_text(encoding="utf-8").split())
    assert RULE in text
