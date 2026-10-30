"""The automatic ProposalAI checks catch the QA report's defects and pass a clean proposal."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("proposal_ai_eval", REPO_ROOT / "scripts" / "agent" / "proposal_ai_eval.py")
assert spec is not None and spec.loader is not None
proposal_ai_eval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proposal_ai_eval)

FIXTURE = json.loads(proposal_ai_eval.ORDERS_PATH.read_text(encoding="utf-8"))
PROFILE = FIXTURE["freelancer_positioning"]
EN_ORDER = {"task_text": "Need Make.com scenarios for Telegram. Budget $150.", "expect_language": "en", "expect_gap": False}
CLEAN = "I build Make.com and n8n automations with Telegram bots.\n\nI can start this week and will confirm the plan after a short call."


def violations(text: str, gaps: list | None = None, order: dict = EN_ORDER, profile: str = PROFILE) -> set[str]:
    checks = proposal_ai_eval.check_proposal(text, gaps or [], order, profile)
    return {name for name, value in checks.items() if value is True}


def test_clean_proposal_has_no_violations() -> None:
    assert violations(CLEAN) == set()


def test_each_reported_defect_is_caught() -> None:
    assert "placeholder" in violations(CLEAN + "\n\nBest, [Your Name]")
    assert "meta_phrase" in violations(CLEAN + " Based on the information I have, I fit.")
    assert "invented_number" in violations(CLEAN + " I charge $350 for it.")
    assert "list_or_heading" in violations("Why I'm a good fit\n\n" + CLEAN)
    assert "list_or_heading" in violations(CLEAN + "\n- Make.com\n- n8n")
    assert "long_dash" in violations(CLEAN + " It is fast — and clean.")
    assert "wrong_language" in violations("Я делаю автоматизации на Make.com. Могу начать на этой неделе.")
    assert "too_long" in violations("word " * 300)


def test_numbers_from_the_order_are_allowed_and_gap_is_required_when_expected() -> None:
    assert "invented_number" not in violations(CLEAN + " The $150 budget is clear.")
    gap_order = {**EN_ORDER, "expect_gap": True}
    assert "missing_gap" in violations(CLEAN, [], gap_order)
    assert "missing_gap" not in violations(CLEAN, [{"description": "No HubSpot."}], gap_order)


def test_numbers_are_read_both_ways_and_ordinary_ai_phrases_pass() -> None:
    order = {**EN_ORDER, "task_text": "Need 3 500-word blog posts"}
    assert "invented_number" not in violations("I can write 3 posts of 500 words.", order=order)
    assert "invented_number" in violations("I can write 4 posts of 500 words.", order=order)
    assert "invented_number" in violations("I have completed 3500 projects.", order=order)
    for hyphen in ("\u2010", "\u2011"):
        typographic = {**EN_ORDER, "task_text": f"Need 3 500{hyphen}word blog posts"}
        assert "invented_number" not in violations("I can write 3 posts of 500 words.", order=typographic)
        assert "invented_number" in violations("I have completed 3,500 posts.", order=typographic)
    for separator in (",", "\u00a0", "\u202f"):
        grouped = {**EN_ORDER, "task_text": f"Write a 3{separator}500-word article"}
        assert "invented_number" not in violations("I can write a 3500-word article.", order=grouped)
    assert "placeholder" in violations(CLEAN + " Hello {client_name}.")
    assert "meta_phrase" not in violations(CLEAN + " As an AI automation engineer I build bots.")
    assert "meta_phrase" in violations(CLEAN + " As an AI language model I cannot promise.")


def test_numbers_are_compared_by_value_and_your_namespace_is_not_a_placeholder() -> None:
    order = {**EN_ORDER, "task_text": "Deadline 2024-05-01"}
    assert "invented_number" not in violations("I can deliver by May 1.", order=order)
    assert "placeholder" not in violations(CLEAN + " I follow your namespace conventions.")
    assert "placeholder" in violations(CLEAN + " Best, Your Name")


# Whole proposals in the languages ANY-631 saw (shortened from real outputs; long enough to detect).
EN_TEXT = (
    "I build Webflow marketing sites, and my past work includes small business sites. I do not accept the "
    "48-hour deadline for the fully custom 12-page site: copy and images arrive next week, and every page "
    "must be approved before build. Your EUR 300 budget is your proposal, not an agreed price."
)
ES_TEXT = (
    "Mi experiencia creando sitios de marketing en Webflow, incluidos sitios para pequeñas empresas, puede "
    "aportar una base concreta para una primera fase. No acepto el plazo de 48 horas para el sitio de 12 "
    "páginas: los textos y las imágenes llegarán la semana que viene. Tampoco acepto el presupuesto de EUR 300."
)
NL_TEXT = (
    "Ik bouw Webflow-marketingwebsites en heb ervaring met websites voor kleine bedrijven, wat aansluit bij "
    "deze opdracht. Ik accepteer de deadline van 48 uur niet: de teksten en afbeeldingen komen pas volgende "
    "week, en elke pagina moet vóór de bouw worden goedgekeurd. Uw budget van EUR 300 accepteer ik niet."
)
DE_TEXT = (
    "In zwei E-Commerce-Projekten habe ich manuelle Tastatur- und Screenreader-Prüfungen durchgeführt; diese "
    "Erfahrung passt zu einem fokussierten Review. Der Review umfasst die sechs Templates und eine priorisierte "
    "Tabelle mit Reproduktionsschritten. Ihr Budgetdeckel beträgt USD 1,200 und ist nicht vereinbart."
)
RU_TEXT = "Я делаю автоматизации на Make.com. Могу начать на этой неделе."


def test_the_proposal_language_is_detected_not_assumed() -> None:
    """ANY-631 code review #3: whole English orders answered in Spanish, Dutch or German passed as
    English, and a Spanish order answered in English was not checked at all."""
    for text in (ES_TEXT, NL_TEXT, DE_TEXT):
        assert proposal_ai_eval.check_proposal(text, [], EN_ORDER, PROFILE)["wrong_language"] is True
    assert proposal_ai_eval.check_proposal(EN_TEXT, [], EN_ORDER, PROFILE)["wrong_language"] is False
    es_order = {**EN_ORDER, "expect_language": "es"}
    assert proposal_ai_eval.check_proposal(EN_TEXT, [], es_order, PROFILE)["wrong_language"] is True
    assert proposal_ai_eval.check_proposal(ES_TEXT, [], es_order, PROFILE)["wrong_language"] is False
    assert proposal_ai_eval.check_proposal(RU_TEXT, [], EN_ORDER, PROFILE, expect_language="ru")["wrong_language"] is False
    assert proposal_ai_eval.check_proposal(EN_TEXT, [], EN_ORDER, PROFILE, expect_language="ru")["wrong_language"] is True
    # a text too short or too mixed to tell is reported for a manual read, never as correct
    checks = proposal_ai_eval.check_proposal("Make.com and n8n bots for Telegram.", [], EN_ORDER, PROFILE, expect_language="de")
    assert checks["wrong_language"] is False and checks["language_unverified"] is True


def test_order_set_covers_the_protocol_classes() -> None:
    orders = FIXTURE["orders"]
    assert {order["expect_language"] for order in orders} == {"en", "ru"}
    assert any(order["expect_gap"] for order in orders)
    assert any(order.get("asks_similar_project") for order in orders)


def test_numbers_are_not_joined_across_the_task_and_the_profile() -> None:
    order = {**EN_ORDER, "task_text": "Budget is $2"}
    assert "invented_number" in violations(CLEAN + " I charge 2500.", order=order, profile="n8n, 500 happy clients")
    assert "invented_number" not in violations(CLEAN + " I have 500 clients.", order=order, profile="n8n, 500 happy clients")


def test_decimals_and_names_with_digits_are_not_evidence_for_standalone_numbers() -> None:
    order = {**EN_ORDER, "task_text": "About 1.5 hours a day"}
    assert "invented_number" not in violations("I can give 1.5 hours a day on n8n.", order=order, profile="n8n")
    assert "invented_number" in violations("I can give 5 hours a day on n8n.", order=order, profile="n8n")
    assert "invented_number" in violations("I have delivered 8 projects on n8n.", order=order, profile="n8n")


def test_angle_placeholders_are_caught_but_numeric_comparisons_pass() -> None:
    assert "placeholder" in violations(CLEAN + " Hello <client_name>.")
    for placeholder in ("<client.name>", "<client/email>", "<client:name>", "<Client Name>"):
        assert "placeholder" in violations(CLEAN + f" Hello {placeholder}.")
        assert "placeholder" in violations(CLEAN + f" Hello{placeholder}, hi.")
        assert "placeholder" in violations(CLEAN + f" Hello{placeholder}there.")
    for placeholder in ("<Имя или фамилия>", "<client and/or company>"):
        assert "placeholder" in violations(CLEAN + f" Hello {placeholder}.")
    # fail closed: brackets around words are a placeholder even in a comparison
    assert "placeholder" in violations(CLEAN + " I can implement the condition x<y && a>b.")
    for marker in ("<%=client_name%>", "<@client_name>", "<$name>", "%FIRST_NAME%", "%client.name%", "%\u0418\u041c\u042f%"):
        assert "placeholder" in violations(CLEAN + f" Hello {marker}.")
    assert "placeholder" not in violations(CLEAN + " I keep latency <50ms and uptime >99%.")
    assert "placeholder" not in violations(CLEAN + " I keep latency <=50ms and uptime >99%.")
    assert "placeholder" not in violations(CLEAN + " Uptime stays at 99% while latency drops by 50%.")
    assert "placeholder" not in violations(CLEAN + " Budget < 500 and timeline > 2 weeks works.")


def test_explicit_groupings_are_one_number_and_dotted_dates_are_three() -> None:
    order = {**EN_ORDER, "task_text": "Budget is $1,500, due 10.5.2024"}
    assert "invented_number" not in violations("I can do it for $1500 by May 5, 2024.", order=order)
    assert "invented_number" in violations("My price is $500.", order=order)


def test_european_amounts_are_one_number() -> None:
    order = {**EN_ORDER, "task_text": "Budget €1.234,50"}
    assert "invented_number" not in violations("My price is €1234.50.", order=order)
    assert "invented_number" in violations("My price is €50.", order=order)


def test_a_space_grouped_amount_is_one_number_never_its_parts() -> None:
    order = {**EN_ORDER, "task_text": "Automate my CRM"}
    for profile, fee in (
        ("My fixed fee is 3 200,50 EUR", "50"),
        ("My fixed fee is 3 200,50 EUR", "200,50"),
        ("My fixed fee is 3 200,50 EUR", "3"),
        ("My fixed fee is 12 500.75 EUR", "75"),
        ("My fixed fee is 12 500.75 EUR", "500.75"),
        ("3 projects, 200 clients", "3 200"),
    ):
        assert "invented_number" in violations(f"My fee is {fee} EUR.", order=order, profile=profile)
    profile = "My fixed fee is 3 200,50 EUR"
    assert "invented_number" not in violations("My fee is 3200.50 EUR.", order=order, profile=profile)


def test_a_number_is_read_by_its_shape() -> None:
    order = {**EN_ORDER, "task_text": "Automate my CRM"}
    for profile, faithful, invented in (
        ("My fixed fee is CHF 1'500.", "My fee is CHF 1500.", "My fee is CHF 500."),
        ("My fixed fee is CHF 1’500.", "My fee is CHF 1,500.", "My fee is CHF 1."),
        ("My fixed fee is CHF 1'500.50.", "My fee is CHF 1500.50.", "My fee is CHF 500.50."),
        ("I delivered +20% revenue growth.", "I delivered 20% growth.", "I delivered -20% growth."),
        ("My fixed fee is +200 EUR.", "My fee is 200 EUR.", "My fee is -200 EUR."),
        ("My rate is $1.234k.", "My rate is $1,234.", "My rate is $1,234,000."),
        ("I processed .5M rows.", "I processed 500,000 rows.", "I processed 5,000,000 rows."),
    ):
        assert "invented_number" not in violations(faithful, order=order, profile=profile), faithful
        assert "invented_number" in violations(invented, order=order, profile=profile), invented


def test_a_scaled_amount_keeps_its_exact_fraction() -> None:
    order = {**EN_ORDER, "task_text": "Automate my CRM"}
    profile = "My fixed fee is $1.2345k"
    assert "invented_number" not in violations("My fee is $1,234.50.", order=order, profile=profile)
    assert "invented_number" in violations("My fee is $1,234.", order=order, profile=profile)


def test_a_digit_leading_hyphenated_range_keeps_its_upper_bound() -> None:
    order = {**EN_ORDER, "task_text": "Automate my CRM"}
    profile = "I can complete a 2-to-3-week project"
    assert "invented_number" not in violations("Done in 2 to 3 weeks.", order=order, profile=profile)
    assert "invented_number" in violations("Done in 2 to 4 weeks.", order=order, profile=profile)


def test_identifiers_do_not_offer_their_digits_as_numbers() -> None:
    for task_text in ("Integrate GPT-4o", "Need 4K footage"):
        order = {**EN_ORDER, "task_text": task_text}
        assert "invented_number" in violations("I have delivered 4 projects.", order=order)
    order = {**EN_ORDER, "task_text": "Integrate GPT-4.1-mini"}
    assert "invented_number" in violations("I have completed 1 project.", order=order)
    order = {**EN_ORDER, "task_text": "Integrate gpt_4o, use task_id_42"}
    assert "invented_number" in violations("I have delivered 4 projects.", order=order)
    assert "invented_number" in violations("I completed 42 projects.", order=order)
    order = {**EN_ORDER, "task_text": "Keep latency under 50ms with 16GB RAM"}
    assert "invented_number" not in violations("I keep it under 50 ms with 16 GB.", order=order)
    order = {**EN_ORDER, "task_text": "Need 12V at 60Hz, budget $20k"}
    assert "invented_number" not in violations("12 volts at 60 Hz for $20,000.", order=order)
    assert "invented_number" in violations("My fee is $20.", order=order)


def test_terms_set_checks_the_status_of_client_terms() -> None:
    """terms.json (ANY-631): every order names its rule and the decision each term needs. The status
    check finds definite errors and never passes a term: a term without an error needs a human
    verdict. Every counterexample below got through an earlier version (code reviews #3 to #5)."""
    terms = json.loads((proposal_ai_eval.ORDERS_PATH.parent / "terms.json").read_text(encoding="utf-8"))
    orders = {order["id"]: order for order in terms["orders"]}
    for order in orders.values():
        assert order["rule"] and order["terms"], order["id"]
        for pattern in order.get("must", []) + order.get("must_not", []) + [term["value"] for term in order["terms"]]:
            re.compile(pattern)

    def outcome(order_id: str, text: str) -> str:
        result = proposal_ai_eval.check_terms(text, orders[order_id]["terms"])
        assert result["errors"] or result["needs_verdict"], "every term is an error or needs a verdict"
        return "error" if result["errors"] else "needs_verdict"

    # an unagreed price or deadline stated as accepted (review #3)
    assert outcome("conflict-decline-en", "I accept your USD 150 budget and the 3-day deadline for this project. I do not accept unlimited logo concepts.") == "error"
    assert outcome("counteroffer-en", "I accept the EUR 300 budget and offer EUR 800 for a smaller first phase. I do not accept the 48-hour deadline.") == "error"
    assert outcome("ceiling-stays-client-ru", "Бюджет до 80 000 ₽ согласован и принят. Срок в 2 рабочих дня подтверждаю.") == "error"
    assert outcome("limit-change-accepted-en", "I do not accept a second revision round; EUR 1,500 stays as agreed.") == "error"
    assert outcome("conflict-decline-es", "Acepto el presupuesto de 200 EUR y garantizo 10 000 seguidores.") == "error"
    # a negation in another clause, a declined term only left open, an omitted or unstatused term (review #4)
    assert outcome("conflict-decline-en", "I do not code, but I accept your USD 150 budget. I do not accept the 3-day deadline or unlimited logo concepts.") == "error"
    assert outcome("counteroffer-en", "Your EUR 300 budget will be agreed later. I do not accept the 48-hour deadline. I offer EUR 800 for a smaller phase.") == "error"
    assert outcome("conflict-decline-en", "Your request is for a logo and templates on a USD 150 budget. I do not accept the 3-day deadline or unlimited concepts.") == "error"
    assert outcome("left-open-en", "I can rewrite the welcome email and the four-email trial sequence. Analytics setup is outside this work.") == "error"
    # a decline the freelancer ordered, written only as "a proposal, not agreed" (review #5)
    assert outcome("conflict-decline-es", "El presupuesto de 200 EUR es una propuesta del cliente, no un acuerdo. La garantía de 10 000 seguidores también es una propuesta del cliente, no un acuerdo. No propongo otra suma.") == "error"
    assert outcome("conflict-decline-en", "Your USD 150 budget is your proposal, not an agreed price. I do not accept the 3-day deadline. Unlimited logo concepts are your proposal, not agreed.") == "error"
    # the fee is open only after the theme is inspected; dropping that condition is an error (review #5)
    assert outcome("ceiling-and-scope-en", "Your USD 1,200 budget is proposed, not agreed. The final fee is proposed, not agreed.") == "error"
    # an agreed term called not agreed (the shipping-prompt regression on luna/medium)
    assert outcome("agreed-confirm-ru", "Стоимость 36 000 ₽, сдача до 20 ноября и 3 000 ₽ за карточку указаны как условия клиента, но пока не согласованы.") == "error"

    # correct proposals (from the live runs) are never errors, and never pass without a human verdict
    for order_id, text in (
        ("conflict-decline-en", "Your USD 150 budget is your proposal, not an agreed price. I do not accept the 3-day deadline or unlimited logo concepts."),
        ("counteroffer-en", "I do not accept the EUR 300 budget or the 48-hour deadline. I offer EUR 800 for a smaller 5-page first phase."),
        ("ceiling-stays-client-ru", "Срок в 2 рабочих дня нереален и не принимается. Ваш бюджет до 80 000 ₽ является предложенным пределом, а не согласованной ценой."),
        ("limit-change-accepted-en", "I accept the second revision round instead of the one-round limit; EUR 1,500 and the 5 pages stay as agreed."),
        ("conflict-decline-es", "No acepto el presupuesto de 200 EUR. Tampoco acepto garantizar 10 000 seguidores nuevos."),
        ("left-open-en", "The number of additional emails and the fee will be agreed after the discovery call. Early January 2027 is your requested target, but the date is not fixed yet."),
        ("agreed-confirm-ru", "Подтверждаю согласованные условия: 12 карточек, итого 36 000 ₽. Сдача до 18:00 20 ноября 2026. Сверх 12 карточек по 3 000 ₽."),
        ("ceiling-and-scope-en", "Your USD 1,200 budget ceiling is a proposal, not an agreed fee; the final fee remains to be agreed after inspecting the theme."),
    ):
        assert outcome(order_id, text) == "needs_verdict", (order_id, text)
