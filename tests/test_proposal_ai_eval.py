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


FIXTURES = proposal_ai_eval.ORDERS_PATH.parent
KINDS = {"declined", "not_agreed", "agreed", "accepted", "offered", "open", "requirement"}


def test_criteria_are_questions_and_fixture_checks_are_literal() -> None:
    """Meaning is a human question; `must_not` may only forbid amounts (code reviews #3 to #6 found
    a new wording that every semantic regular expression misread)."""
    for name in ("terms.json", "qa_cases.json"):
        for order in json.loads((FIXTURES / name).read_text(encoding="utf-8"))["orders"]:
            ids = [criterion["id"] for criterion in order["criteria"]]
            assert len(ids) == len(set(ids)) and "no-critical-error" not in ids, order["id"]
            for criterion in order["criteria"]:
                assert criterion["kind"] in KINDS and criterion["question"].endswith("?"), criterion
                assert isinstance(criterion["critical"], bool), criterion
            for pattern in order.get("must", []) + order.get("must_not", []):
                re.compile(pattern)
            for pattern in order.get("must_not", []):
                assert "\\d" in pattern, f"{order['id']}: must_not forbids amounts only: {pattern}"


ORDER = {
    "id": "counteroffer-en",
    "task_text": "A client wants a 12-page site within 48 hours for EUR 300. Decline both and offer EUR 800 for 5 pages.",
    "expect_language": "en",
    "must": ["EUR 800"],
    "must_not": ["EUR (?!300\\b|800\\b)\\d"],
    "criteria": [{"id": "budget-declined", "kind": "declined", "critical": False, "question": "Is EUR 300 refused?"}],
}
PROFILE_EN = "I build Webflow marketing sites for small businesses and agree timelines after the content arrives."
TEXT = (
    "I build Webflow marketing sites for small businesses, and this project is close to the work I do for my clients. "
    "I do not accept the EUR 300 budget or the 48-hour deadline for the full site with all of its pages. "
    "I offer EUR 800 for a smaller first phase of 5 pages, and I will start it once the copy and the images arrive."
)


def make_run(run_id: str, text: str = TEXT, **fields) -> dict:
    return {
        "run_id": run_id, "series": "luna-medium", "case_id": ORDER["id"], "attempt": 1, "channel": "web_form",
        "session_id": f"s-{run_id}", "prompt_sha256": {"compose_persuasive_text.v1.md": "abc"}, "model": "openai/gpt-6-luna",
        "reasoning_effort": "medium", "input": {"task_text": ORDER["task_text"], "freelancer_positioning": PROFILE_EN, "tone": "firm"},
        "output": {"text": text, "gaps": []}, "runtime_status": "ok", "error": None, "latency_ms": 20000, **fields,
    }


def decide(run: dict, answers: dict[str, str]) -> list[dict]:
    digest = proposal_ai_eval.answer_hash(run["output"])
    return [
        {"run_id": run["run_id"], "criterion_id": criterion, "answer_hash": digest, "suggestion": None,
         "decision": {"answer": answer, "reason": None if answer == "yes" else "read", "reviewer": "qa", "reviewed_at": "2026-10-30T00:00:00+00:00"}}
        for criterion, answer in answers.items()
    ]


def run_accept(tmp_path: Path, runs: list[dict], verdicts: list[dict], thresholds: list[dict] | None = None, capsys=None) -> tuple[int, str]:
    (tmp_path / "orders.json").write_text(json.dumps({"orders": [ORDER]}), encoding="utf-8")
    (tmp_path / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in runs), encoding="utf-8")
    (tmp_path / "verdicts.jsonl").write_text("".join(json.dumps(v) + "\n" for v in verdicts), encoding="utf-8")
    suite = {
        "id": "t", "orders": ["orders.json"], "runs": "runs.jsonl", "verdicts": "verdicts.jsonl", "max_median_latency_ms": 60000,
        "thresholds": [{"series": "luna-medium", "cases": [ORDER["id"]], "min_usable": 2, "of": 3}] if thresholds is None else thresholds,
    }
    (tmp_path / "suite.json").write_text(json.dumps(suite), encoding="utf-8")
    code = proposal_ai_eval.main(["accept", "--suite", str(tmp_path / "suite.json")])
    return code, capsys.readouterr().out


YES = {"no-critical-error": "yes", "budget-declined": "yes"}


def test_accept_is_pending_until_a_human_confirms_every_criterion(tmp_path: Path, capsys) -> None:
    runs = [make_run(f"r{i}") for i in range(3)]
    # an agent suggestion is not a decision, and a decision for another answer does not count
    suggested = [{**row, "decision": None, "suggestion": {"answer": "yes", "reviewer": "agent"}} for row in decide(runs[0], YES)]
    stale = [{**row, "answer_hash": "sha256:other"} for row in decide(runs[1], YES)]
    code, out = run_accept(tmp_path, runs, suggested + stale + decide(runs[2], {**YES, "budget-declined": "unknown"}), capsys=capsys)
    assert code == 1 and out.startswith("# Suite t: PENDING")
    assert "budget-declined: not confirmed" in out and "budget-declined: unknown" in out


def test_accept_passes_with_confirmed_verdicts_and_a_non_critical_failure_within_the_threshold(tmp_path: Path, capsys) -> None:
    runs = [make_run("r0"), make_run("r1", text=TEXT + " Long dashes — are a warning only."), make_run("r2")]
    verdicts = decide(runs[0], YES) + decide(runs[1], YES) + decide(runs[2], {**YES, "budget-declined": "no"})
    code, out = run_accept(tmp_path, runs, verdicts, capsys=capsys)
    assert code == 0 and out.startswith("# Suite t: PASS"), out
    assert "| luna-medium | counteroffer-en | 3 | 2 | 1 | 0 | 2/3 | PASS |" in out
    assert "warning: long_dash" in out


def test_accept_fails_on_a_critical_error_a_missed_threshold_or_slow_runs(tmp_path: Path, capsys) -> None:
    runs = [make_run(f"r{i}") for i in range(3)]
    verdicts = [row for run in runs for row in decide(run, YES)]
    critical = decide(runs[0], {**YES, "no-critical-error": "no"})
    code, out = run_accept(tmp_path, runs, verdicts + critical, capsys=capsys)
    assert code == 1 and "FAIL: critical errors: r0" in out
    # a forbidden amount is a critical error without any verdict
    code, out = run_accept(tmp_path, [make_run("r0", text=TEXT + " Or EUR 500 for less.")] + runs[1:], verdicts, capsys=capsys)
    assert code == 1 and "FAIL critical `r0`: forbidden_present" in out
    # two runs a person rejected and one runtime error leave 0 of 3 usable
    failed = [make_run("r0", runtime_status="ui_error", error="form gave up after 60 s")] + runs[1:]
    rejected = [row for run in runs[1:] for row in decide(run, {**YES, "budget-declined": "no"})]
    code, out = run_accept(tmp_path, failed, rejected, capsys=capsys)
    assert code == 1 and "FAIL: luna-medium counteroffer-en: 0 usable, needs 2/3" in out
    slow = [make_run(f"r{i}", latency_ms=61000) for i in range(3)]
    code, out = run_accept(tmp_path, slow, [row for run in slow for row in decide(run, YES)], capsys=capsys)
    assert code == 1 and "median latency 61.0 s above 60 s" in out


def test_accept_never_invents_a_threshold(tmp_path: Path, capsys) -> None:
    runs = [make_run(f"r{i}") for i in range(3)]
    code, out = run_accept(tmp_path, runs, [row for run in runs for row in decide(run, YES)], thresholds=[], capsys=capsys)
    assert code == 1 and "PENDING: luna-medium counteroffer-en: no approved threshold" in out


def test_formal_checks_leave_every_wording_of_a_term_to_the_reviewer() -> None:
    """The review #6 wordings: whatever the text says about a term, the formal checks neither pass nor
    fail it; only the forbidden amount and the required value are literal."""
    for text in (
        TEXT.replace("I offer EUR 800", "I propose EUR 800"),
        TEXT.replace("I do not accept the EUR 300 budget or", "The EUR 300 budget is not agreed. I do not accept"),
    ):
        judged = proposal_ai_eval.judge_run(make_run("r", text=text), ORDER, {})
        assert judged["status"] == "PENDING" and judged["critical"] is None, judged
        assert not any(reason.startswith(("budget", "forbidden", "missing")) and "confirmed" not in reason for reason in judged["reasons"])


def test_the_any_631_suite_is_consistent() -> None:
    """The committed live acceptance: every verdict belongs to a stored run, a criterion of its order and
    the exact answer it judged, and the offline verdict is the same on every call."""
    path = FIXTURES / "acceptance" / "any-631" / "suite.json"
    suite, orders, runs, verdicts = proposal_ai_eval.load_suite(path)
    by_id = {run["run_id"]: run for run in runs}
    assert len(by_id) == len(runs) == 150
    for (run_id, criterion_id), row in verdicts.items():
        run = by_id[run_id]
        assert criterion_id in {c["id"] for c in proposal_ai_eval.criteria_for(orders[run["case_id"]])}
        assert row["answer_hash"] == proposal_ai_eval.answer_hash(run["output"])
        assert row["decision"] is None or row["decision"]["reviewer"] != "agent"
    assert proposal_ai_eval.accept(*proposal_ai_eval.load_suite(path)) == proposal_ai_eval.accept(suite, orders, runs, verdicts)


def test_review_copies_the_agents_reason_only_for_the_same_answer(tmp_path: Path, monkeypatch) -> None:
    run = make_run("r0")
    digest = proposal_ai_eval.answer_hash(run["output"])
    suggestion = {"answer": "unknown", "reviewer": "agent", "reason": "agent doubt", "quote": None}
    row = {"run_id": "r0", "criterion_id": "budget-declined", "answer_hash": digest, "suggestion": suggestion, "decision": None}
    (tmp_path / "orders.json").write_text(json.dumps({"orders": [ORDER]}), encoding="utf-8")
    (tmp_path / "runs.jsonl").write_text(json.dumps(run) + "\n", encoding="utf-8")
    (tmp_path / "verdicts.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    suite = {"id": "t", "orders": ["orders.json"], "runs": "runs.jsonl", "verdicts": "verdicts.jsonl",
             "max_median_latency_ms": 60000, "thresholds": []}
    (tmp_path / "suite.json").write_text(json.dumps(suite), encoding="utf-8")
    # no-critical-error: y with no suggestion; budget-declined: y against the agent's unknown, own reason
    answers = iter(["y", "y", "refused in the second sentence"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    args = ["review", "--suite", str(tmp_path / "suite.json"), "--reviewer", "qa"]
    assert proposal_ai_eval.main(args) == 0
    decisions = {r["criterion_id"]: r["decision"] for r in proposal_ai_eval.read_jsonl(tmp_path / "verdicts.jsonl") if r["decision"]}
    assert decisions["budget-declined"]["reason"] == "refused in the second sentence"
    # --redo shows only the named decision; a matching answer keeps the agent's reason
    row["suggestion"] = {**suggestion, "answer": "yes", "reason": "agent reason"}
    (tmp_path / "verdicts.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _prompt="": "y")
    assert proposal_ai_eval.main([*args, "--redo", "r0/budget-declined"]) == 0
    last = proposal_ai_eval.read_jsonl(tmp_path / "verdicts.jsonl")[-1]
    assert last["criterion_id"] == "budget-declined" and last["decision"]["reason"] == "agent reason"
