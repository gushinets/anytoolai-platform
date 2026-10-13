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


def violations(text: str, gaps: list | None = None, order: dict = EN_ORDER) -> set[str]:
    checks = proposal_ai_eval.check_proposal(text, gaps or [], order, PROFILE)
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
    assert "meta_phrase" not in violations(CLEAN + " As an AI automation engineer I build bots.")
    assert "meta_phrase" in violations(CLEAN + " As an AI language model I cannot promise.")


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
