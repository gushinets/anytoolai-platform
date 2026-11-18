"""Prepaid Request addresses the client named in notes, in the second person (ANY-606)."""

from pathlib import Path

PROMPT = (
    Path(__file__).parents[1]
    / "src"
    / "anytoolai_freelancer_suite"
    / "products"
    / "client_update_writer"
    / "prompts"
    / "prepaid_request_compose_persuasive_text.v1.md"
)

RULE = (
    'Address the message to the client: the person the notes name as the one this payment is '
    'requested from, who will read the message. Write to the client directly in the second '
    'person ("you"; in Russian "вы" and plural verb forms, which do not mark gender) in every '
    'kind of message (rules A–D), and never describe the client in the third person ("for Jordan '
    'at Cedar Studio", "поддержка сайта с Никитой", "Никита уже согласился" become "you", '
    '"поддержка вашего сайта", "вы уже согласились"). When `context.notes` gives the client\'s '
    'name (for example "For Jordan at Cedar Studio", "обсуждаем поддержку сайта с Никитой", '
    '"клиент — Елена"), open with a greeting that uses that name, matching the tone and language '
    '(for example "Hello Jordan,", "Hi Jordan,", "Здравствуйте, Никита.", "Здравствуйте, '
    'Елена!"); do not replace a given name with a nameless greeting. Use only the client\'s name: '
    "never the freelancer's own name, the name of a third party (a colleague, the client's "
    'customer, a manager), or a company, brand or product name ("ООО Север", "Cedar Studio" are '
    'not a person: greet without a name). When it is unclear whose name it is, or several people '
    'are named and none is clearly the client, greet without a name. Keep the spelling and '
    'script the input gives and never invent a patronymic, surname or diminutive. In Russian use '
    'the nominative for direct address, changing an inflected name only when its nominative is '
    'unambiguous ("с Никитой" is "Никита", "для Елены" is "Елена"); otherwise greet without a '
    'name. A company the notes name may still be mentioned as what the work is for. Never use a '
    'time-of-day greeting ("Добрый день", "Good morning"). When `constraints.length` is too '
    'short, drop the greeting before any payment term or open point, but keep the second person.'
)


def _normalized_prompt() -> str:
    return " ".join(PROMPT.read_text(encoding="utf-8").split())


def test_prepaid_prompt_carries_client_addressee_rule_verbatim() -> None:
    assert RULE in _normalized_prompt()


def test_client_addressee_rule_sits_between_placeholder_and_speaker_rules() -> None:
    prompt = _normalized_prompt()
    placeholder = prompt.index("placeholders such as `[Client Name]`")
    addressee = prompt.index(RULE)
    speaker = prompt.index("Speak as the freelancer without a name or a gender.")
    assert placeholder < addressee < speaker
