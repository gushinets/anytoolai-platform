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
    'Speak as the freelancer without a name or a gender. Do not introduce yourself by name and '
    'do not sign off with a name, a role or contact details unless the input explicitly gives '
    "them as the freelancer's own (a name or signature in the client's message is the client's, "
    'not yours): the input is the only source of such facts, so open with the point. For each '
    'action you report, preserve its actor in every language and tone, including who makes a '
    'commitment. '
    "Keep the author's stated first-person singular or plural for that action, even when other "
    'sentences are impersonal. Keep a known actor explicit instead of using a passive that '
    "omits them. Use first-person plural only when the freelancer's own words speak for a group, "
    'including conjugated verbs with an implied pronoun. A joint action with the client licenses '
    'that shared voice only for that action. Client quotes and third-person descriptions do not '
    "establish the freelancer's speaker number. When the source gives no actor for a status, "
    'let the work, deliverable, or missing material be the subject, or use an impersonal '
    "construction. In languages that mark the speaker's gender (for example Russian, Spanish, "
    "French), write about yourself only in gender-neutral forms unless the input states the "
    "speaker's gender. In Russian the first-person singular past tense (with or without "
    '"я"), "чтобы я" with a verb and "сам"/"сама" mark gender just like "готов"/"готова"; plural '
    '"мы" forms ("мы завершили") do not. When rephrasing to avoid gender, keep the actor, '
    'tense and status. The past stays in the past ("новую дату пока не обещали" stays '
    '"пока не обещали", never "не обещаем" or "не обещаю"). If a known actor needs an impersonal '
    'or nominal phrase, name the actor in that phrase ("обещаний по новой дате с моей стороны '
    'пока не было"). Keep present or future actions in those tenses ("я могу", '
    '"у меня есть опыт", "я сделаю", "чтобы начать работу", "требования задаю я"). Avoid '
    '"готов(а)", "мог(ла)", "чтобы я мог", "чтобы я начал", "не обещал", "я сама" and "Готова". '
    'Change the wording, not the facts, amounts, dates or '
    'actions.'
)


@pytest.mark.parametrize("prompt", PROMPTS)
def test_prompt_carries_speaker_identity_rule_verbatim(prompt: str) -> None:
    text = " ".join((PRODUCTS / prompt).read_text(encoding="utf-8").split())
    assert RULE in text
