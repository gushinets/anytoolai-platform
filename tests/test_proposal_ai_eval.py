"""The automatic ProposalAI checks catch the QA report's defects and pass a clean proposal."""

from __future__ import annotations

import importlib.util
import json
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


def test_an_explicit_language_replaces_the_orders_expected_one() -> None:
    russian = "Я делаю автоматизации на Make.com. Могу начать на этой неделе."
    checks = proposal_ai_eval.check_proposal(russian, [], EN_ORDER, PROFILE, expect_language="ru")
    assert checks["wrong_language"] is False
    checks = proposal_ai_eval.check_proposal(CLEAN, [], EN_ORDER, PROFILE, expect_language="de")
    assert checks["wrong_language"] is False  # not detectable, skipped
    checks = proposal_ai_eval.check_proposal(CLEAN, [], EN_ORDER, PROFILE, expect_language="ru")
    assert checks["wrong_language"] is True


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
