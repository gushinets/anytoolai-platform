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


def test_terms_set_checks_the_status_of_client_terms() -> None:
    """terms.json (ANY-631): every order names its rule and the expected status of its terms; the
    status oracle passes correct proposals and rejects the critical errors code review #3 showed
    passing the earlier presence-only patterns."""
    terms = json.loads((proposal_ai_eval.ORDERS_PATH.parent / "terms.json").read_text(encoding="utf-8"))
    orders = {order["id"]: order for order in terms["orders"]}
    for order in orders.values():
        assert order["rule"] and order["terms"], order["id"]
        for pattern in order.get("must", []) + order.get("must_not", []) + [term["value"] for term in order["terms"]]:
            re.compile(pattern)

    def errors(order_id: str, text: str) -> list[str]:
        return proposal_ai_eval.term_status_errors(text, orders[order_id]["terms"])

    # the critical errors: an unagreed price or deadline stated as accepted
    assert errors("conflict-decline-en", "I accept your USD 150 budget and the 3-day deadline for this project. I do not accept unlimited logo concepts.")
    assert errors("counteroffer-en", "I accept the EUR 300 budget and offer EUR 800 for a smaller first phase. I do not accept the 48-hour deadline.")
    assert errors("ceiling-stays-client-ru", "Бюджет до 80 000 ₽ согласован и принят. Срок в 2 рабочих дня подтверждаю.")
    assert errors("limit-change-accepted-en", "I do not accept a second revision round; EUR 1,500 stays as agreed.")
    assert errors("conflict-decline-es", "Acepto el presupuesto de 200 EUR, garantizo 10 000 seguidores y 5 publicaciones diarias.")
    # a term restated with no status at all is not "explicit"
    assert errors("conflict-decline-en", "Your request is for a logo and templates on a USD 150 budget. I do not accept the 3-day deadline or unlimited concepts.")

    # correct proposals (from the live runs): refusal, proposal, a governing verb over a list, an open fee
    assert not errors("conflict-decline-en", "I do not accept your USD 150 budget or the 3-day deadline for this scope. I also do not accept unlimited logo concepts.")
    assert not errors("counteroffer-en", "I do not accept the EUR 300 budget or the 48-hour deadline. I offer EUR 800 for a smaller 5-page first phase.")
    assert not errors("ceiling-stays-client-ru", "Срок в 2 рабочих дня нереален и не принимается. Ваш бюджет до 80 000 ₽ является предложенным пределом, а не согласованной ценой.")
    assert not errors("limit-change-accepted-en", "I accept the second revision round instead of the one-round limit; EUR 1,500 and the 5 pages stay as agreed.")
    assert not errors("conflict-decline-es", "No acepto el presupuesto de 200 EUR ni el ritmo de 5 publicaciones diarias. Tampoco acepto garantizar 10 000 seguidores nuevos.")
    assert not errors("left-open-en", "The number of additional emails and the fee will be agreed after the discovery call. Early January 2027 is your requested target, but the date is not fixed yet.")
    assert errors("left-open-en", "The fee is accepted and I will deliver in early January, as agreed.")
