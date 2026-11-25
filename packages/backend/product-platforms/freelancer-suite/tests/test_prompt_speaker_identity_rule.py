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
    'not yours): the input is the only source of such facts, so open with the point. Before '
    'rephrasing a statement, identify who said it, who took part and in what roles, what '
    'happened or is proposed, and which relationships the source states, such as cause or '
    'condition. Keep those details in every language and tone. Resolve pronouns and verb '
    "endings from the original speaker's perspective before choosing the wording from the "
    "freelancer's perspective. Preserve the source of the claim and the people in it "
    'independently. Keep known actors explicit and roles local to their own events. A '
    'person named for one event does not fill an unstated role in another. Leave unspecified '
    "roles open, using an impersonal or work-centred statement if needed. Keep the author's stated "
    'singular or plural for their own actions, even alongside impersonal statements. Use a shared '
    'voice for a joint action only when the source includes the freelancer in that action. It '
    'does not establish a group voice for their other work. In '
    "languages that mark the speaker's gender (for example Russian, Spanish, "
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
