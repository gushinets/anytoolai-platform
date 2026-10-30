"""The automatic ProposalAI checks catch the QA report's defects and pass a clean proposal."""

from __future__ import annotations

import hashlib
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
CRITICAL = proposal_ai_eval.CRITICAL_VIOLATIONS
SUITE_PATH = FIXTURES / "acceptance" / "any-631" / "suite.json"


def test_criteria_are_questions_and_fixture_checks_are_literal() -> None:
    """Meaning is a human question; `must_not` may only forbid amounts (code reviews #3 to #6 found
    a new wording that every semantic regular expression misread). A critical criterion names its
    violation, so no criterion mixes a critical violation with a minor one."""
    for name in ("terms.json", "qa_cases.json"):
        for order in json.loads((FIXTURES / name).read_text(encoding="utf-8"))["orders"]:
            ids = [criterion["id"] for criterion in order["criteria"]]
            assert len(ids) == len(set(ids)) and "no-critical-error" not in ids, order["id"]
            assert order["expect_gaps_language"] in {"en", "ru", "es"}, order["id"]
            for criterion in order["criteria"]:
                assert criterion["kind"] in KINDS and criterion["question"].endswith("?"), criterion
                assert isinstance(criterion["critical"], bool), criterion
                assert criterion["critical"] == (criterion.get("violation_type") in CRITICAL), criterion
            for pattern in order.get("must", []) + order.get("must_not", []):
                re.compile(pattern)
            for pattern in order.get("must_not", []):
                assert "\\d" in pattern, f"{order['id']}: must_not forbids amounts only: {pattern}"


ORDER = {
    "id": "counteroffer-en",
    "task_text": "A client wants a 12-page site within 48 hours for EUR 300. Decline both and offer EUR 800 for 5 pages.",
    "expect_language": "en",
    "expect_gaps_language": "en",
    "must": ["EUR 800"],
    "must_not": ["EUR (?!300\\b|800\\b)\\d"],
    "criteria": [
        {"id": "budget-declined", "kind": "declined", "critical": False, "question": "Is EUR 300 refused?"},
        {"id": "terms-not-accepted", "kind": "requirement", "critical": True, "violation_type": "unagreed_term_accepted",
         "question": "Is none of the client's terms stated as accepted?"},
    ],
}
PROFILE_EN = "I build Webflow marketing sites for small businesses and agree timelines after the content arrives."
TEXT = (
    "I build Webflow marketing sites for small businesses, and this project is close to the work I do for my clients. "
    "I do not accept the EUR 300 budget or the 48-hour deadline for the full site with all of its pages. "
    "I offer EUR 800 for a smaller first phase of 5 pages, and I will start it once the copy and the images arrive."
)
HASHES = {"compose_persuasive_text.v1.md": "abc"}
SPANISH_GAPS = [{"description": "No se menciona experiencia con Shopify en tu perfil."}]
YES = {"no-critical-error": "yes", "budget-declined": "yes", "terms-not-accepted": "yes"}


def trace_hash(run_id: str) -> str:
    return hashlib.sha256(f"trace-{run_id}".encode()).hexdigest()


def make_run(run_id: str, text: str = TEXT, attempt: int = 1, case: str = ORDER["id"], **fields) -> dict:
    return {
        "run_id": run_id, "series": "luna-medium", "case_id": case, "attempt": attempt, "channel": "web_form",
        "origin": {"ui_outcome": "result", "ui_latency_ms": 20000, "trace": f"trace/{run_id}.zip", "trace_sha256": trace_hash(run_id)},
        "session_id": f"s-{run_id}", "prompt_sha256": HASHES, "model": "openai/gpt-6-luna",
        "reasoning_effort": "medium", "input": {"task_text": ORDER["task_text"], "freelancer_positioning": PROFILE_EN, "tone": "firm"},
        "output": {"text": text, "gaps": []}, "runtime_status": "ok", "error": None, "latency_ms": 20000, **fields,
    }


def decide(run: dict, answers: dict[str, str], order: dict = ORDER) -> list[dict]:
    criteria = {c["id"]: c for c in proposal_ai_eval.criteria_for(order, run)}
    return [
        {"run_id": run["run_id"], "criterion_id": criterion, "answer_hash": proposal_ai_eval.answer_hash(run["output"]),
         "input_hash": proposal_ai_eval.input_hash(run), "criterion_hash": proposal_ai_eval.criterion_hash(criteria[criterion]),
         "suggestion": None,
         "decision": {"answer": answer, "reason": None if answer == "yes" else "read", "violation_type": None,
                      "reviewer": "qa", "reviewed_at": "2026-10-30T00:00:00+00:00"}}
        for criterion, answer in answers.items()
    ]


def write_suite(tmp_path: Path, runs: list[dict], verdicts: list[dict], program: list[dict] | None = None, orders: list[dict] | None = None) -> Path:
    (tmp_path / "orders.json").write_text(json.dumps({"orders": orders or [ORDER, {**ORDER, "id": "other"}]}), encoding="utf-8")
    (tmp_path / "trace").mkdir(exist_ok=True)
    for run in runs:  # the browser artifact of a run, where its record names the conventional one
        (tmp_path / "trace" / f"{run['run_id']}.zip").write_bytes(f"trace-{run['run_id']}".encode())
    (tmp_path / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in runs), encoding="utf-8")
    (tmp_path / "verdicts.jsonl").write_text("".join(json.dumps(v) + "\n" for v in verdicts), encoding="utf-8")
    suite = {
        "id": "t", "orders": ["orders.json"], "runs": "runs.jsonl", "verdicts": "verdicts.jsonl", "max_median_latency_ms": 60000,
        "defaults": {"channel": "web_form", "model": "openai/gpt-6-luna", "prompt_sha256": HASHES},
        "program": program if program is not None else [
            {"series": "luna-medium", "cases": [ORDER["id"]], "attempts": 3, "min_usable": 2, "reasoning_effort": "medium"}
        ],
    }
    (tmp_path / "suite.json").write_text(json.dumps(suite), encoding="utf-8")
    return tmp_path / "suite.json"


def run_accept(tmp_path: Path, runs: list[dict], verdicts: list[dict], capsys, **kwargs) -> tuple[int, str]:
    code = proposal_ai_eval.main(["accept", "--suite", str(write_suite(tmp_path, runs, verdicts, **kwargs))])
    captured = capsys.readouterr()
    return code, captured.out + captured.err


def confirmed(runs: list[dict], answers: dict[str, str] = YES) -> list[dict]:
    return [row for run in runs for row in decide(run, answers)]


def attempts(count: int, **fields) -> list[dict]:
    return [make_run(f"r{i}", attempt=i + 1, **fields) for i in range(count)]


GRID = [{"series": "luna-medium", "cases": [ORDER["id"]], "attempts": 5, "min_usable": 4, "reasoning_effort": "medium"}]


def grid_suite(tmp_path: Path, capsys, *kinds: str) -> tuple[int, str]:
    """Five runs at 4/5: pass, fail (a minor criterion is no), pending (nothing confirmed), critical."""
    runs, verdicts = attempts(5), []
    for run, kind in zip(runs, kinds, strict=True):
        answers = {"pass": YES, "fail": {**YES, "budget-declined": "no"}, "critical": {**YES, "terms-not-accepted": "no"}}
        if kind != "pending":
            verdicts += decide(run, answers[kind])
    return run_accept(tmp_path, runs, verdicts, capsys, program=GRID)


def test_a_group_is_decided_by_the_runs_it_can_still_reach(tmp_path: Path, capsys) -> None:
    for kinds, status in (
        (["pass"] * 5, "PASS"),
        (["pass"] * 4 + ["fail"], "PASS"),
        (["pass"] * 4 + ["pending"], "PENDING"),
        (["pass"] * 3 + ["fail"] * 2, "FAIL"),
        (["pass"] * 4 + ["critical"], "FAIL"),
        (["pass"] * 3 + ["fail", "pending"], "PENDING"),
    ):
        code, out = grid_suite(tmp_path, capsys, *kinds)
        assert out.startswith(f"# Suite t: {status}") and code == (0 if status == "PASS" else 1), (kinds, out)


def test_a_missing_run_group_or_case_is_never_a_pass(tmp_path: Path, capsys) -> None:
    code, out = run_accept(tmp_path, [], [], capsys)
    assert code == 1 and out.startswith("# Suite t: PENDING") and "3 of 3 runs missing" in out
    two_cases = [
        {"series": "luna-medium", "cases": [ORDER["id"], "other"], "attempts": 3, "min_usable": 2, "reasoning_effort": "medium"}
    ]
    runs = attempts(3)
    code, out = run_accept(tmp_path, runs, confirmed(runs), capsys, program=two_cases)
    assert code == 1 and out.startswith("# Suite t: PENDING") and "luna-medium other: 3 of 3 runs missing" in out


def test_a_corrupt_suite_is_an_error_not_a_verdict(tmp_path: Path, capsys) -> None:
    runs = attempts(3)
    # a case removed from the program leaves its runs unplanned
    only_other = [{"series": "luna-medium", "cases": ["other"], "attempts": 3, "min_usable": 2, "reasoning_effort": "medium"}]
    code, out = run_accept(tmp_path, runs, confirmed(runs), capsys, program=only_other)
    assert code == 2 and out.startswith("invalid suite:") and "not in the program" in out
    # three copies of one run, and three runs for one attempt
    for copies in ([runs[0]] * 3, [make_run(f"c{i}") for i in range(3)]):
        code, out = run_accept(tmp_path, copies, confirmed(copies), capsys)
        assert code == 2 and "duplicate run" in out
    # an attempt beyond the plan, and a case planned twice
    code, out = run_accept(tmp_path, [make_run("x", attempt=4)], [], capsys)
    assert code == 2 and "not in the program" in out
    twice = [{"series": "luna-medium", "cases": [ORDER["id"]], "attempts": 3, "min_usable": 2, "reasoning_effort": "medium"}] * 2
    code, out = run_accept(tmp_path, [], [], capsys, program=twice)
    assert code == 2 and "planned twice" in out


def test_every_part_of_the_answer_is_checked_for_its_language(tmp_path: Path, capsys) -> None:
    """The ANY-631 gaps: an English order answered in English with Spanish (or German) gap descriptions."""
    gaps = {"text": TEXT, "gaps": SPANISH_GAPS}
    runs = attempts(3)
    runs[0]["output"] = gaps
    strict = [{"series": "luna-medium", "cases": [ORDER["id"]], "attempts": 3, "min_usable": 3, "reasoning_effort": "medium"}]
    judged = proposal_ai_eval.judge_run(runs[0], ORDER, dict(proposal_ai_eval.latest_verdicts(decide(runs[0], YES))))
    assert judged["status"] == "FAIL" and judged["reasons"][0] == "wrong_gaps_language"
    code, out = run_accept(tmp_path, runs, confirmed(runs), capsys, program=strict)
    assert code == 1 and "FAIL `r0`: wrong_gaps_language" in out
    # a gap too short to tell is for the reviewer: pending until they confirm the language
    runs = attempts(3)
    runs[0]["output"] = {"text": TEXT, "gaps": [{"description": "No HubSpot."}]}
    code, out = run_accept(tmp_path, runs, confirmed(runs), capsys)
    assert code == 1 and "PENDING `r0`: language-confirmed: not confirmed" in out
    code, out = run_accept(tmp_path, runs, confirmed(runs) + decide(runs[0], {"language-confirmed": "yes"}), capsys)
    assert code == 0, out


def test_an_api_result_or_a_web_form_error_never_satisfies_a_web_form_group(tmp_path: Path, capsys) -> None:
    # the server answered after the form gave up (74 s against a 60 s limit): a failure, not a success
    late = [make_run(f"r{i}", attempt=i + 1, origin={**make_run(f"r{i}")["origin"], "ui_outcome": "error", "ui_latency_ms": 60000}) for i in range(3)]
    code, out = run_accept(tmp_path, late, confirmed(late), capsys)
    assert code == 1 and "FAIL: luna-medium counteroffer-en" in out and "web form showed error after 60000 ms" in out
    # an API run, or a record that only claims the channel, is not the evidence the group asks for
    for fields in ({"channel": "api", "origin": None}, {"origin": None}):
        runs = attempts(3, **fields)
        code, out = run_accept(tmp_path, runs, confirmed(runs), capsys)
        assert code == 1 and out.startswith("# Suite t: PENDING"), out
        assert "evidence:" in out
    assert "no web form observation" in out


def test_a_verdict_counts_only_for_the_answer_input_and_criterion_it_judged(tmp_path: Path, capsys) -> None:
    runs = attempts(3)
    rows = confirmed(runs)
    code, out = run_accept(tmp_path, runs, rows, capsys)
    assert code == 0, out
    # the question changed, the answer did not
    reworded = {**ORDER, "criteria": [{**ORDER["criteria"][0], "question": "Is EUR 300 clearly refused?"}, ORDER["criteria"][1]]}
    code, out = run_accept(tmp_path, runs, rows, capsys, orders=[reworded, {**ORDER, "id": "other"}])
    assert code == 1 and out.startswith("# Suite t: PENDING") and "budget-declined: not confirmed" in out
    # the input changed
    changed = [{**run, "input": {**run["input"], "tone": "warm"}} for run in runs]
    code, out = run_accept(tmp_path, changed, rows, capsys)
    assert code == 1 and out.startswith("# Suite t: PENDING")
    # only a threshold changed: the same verdicts still count
    stricter = [{"series": "luna-medium", "cases": [ORDER["id"]], "attempts": 3, "min_usable": 3, "reasoning_effort": "medium"}]
    code, out = run_accept(tmp_path, runs, rows, capsys, program=stricter)
    assert code == 0, out


def test_a_critical_detail_cannot_hide_behind_the_general_answer(tmp_path: Path, capsys) -> None:
    runs = attempts(3)
    rows = confirmed(runs[1:]) + decide(runs[0], {**YES, "terms-not-accepted": "no"})
    code, out = run_accept(tmp_path, runs, rows, capsys)
    assert code == 1 and "FAIL: critical errors: r0" in out and "contradiction: no-critical-error is yes but terms-not-accepted is no" in out


def test_confirmed_verdicts_and_thresholds_give_a_pass(tmp_path: Path, capsys) -> None:
    runs = [make_run("r0"), make_run("r1", text=TEXT + " Long dashes — are a warning only.", attempt=2), make_run("r2", attempt=3)]
    verdicts = decide(runs[0], YES) + decide(runs[1], YES) + decide(runs[2], {**YES, "budget-declined": "no"})
    code, out = run_accept(tmp_path, runs, verdicts, capsys)
    assert code == 0 and out.startswith("# Suite t: PASS"), out
    assert "| luna-medium | counteroffer-en | 3 | 3 | 2 | 1 | 0 | 2/3 | PASS |" in out and "warning: long_dash" in out


def test_accept_is_pending_until_a_human_confirms_every_criterion(tmp_path: Path, capsys) -> None:
    runs = attempts(3)
    # an agent suggestion is not a decision, and a decision for another answer does not count
    suggested = [{**row, "decision": None, "suggestion": {"answer": "yes", "reviewer": "agent"}} for row in decide(runs[0], YES)]
    stale = [{**row, "answer_hash": "sha256:other"} for row in decide(runs[1], YES)]
    code, out = run_accept(tmp_path, runs, suggested + stale + decide(runs[2], {**YES, "budget-declined": "unknown"}), capsys)
    assert code == 1 and out.startswith("# Suite t: PENDING")
    assert "budget-declined: not confirmed" in out and "budget-declined: unknown" in out


def test_accept_fails_on_a_critical_error_a_missed_threshold_or_slow_runs(tmp_path: Path, capsys) -> None:
    runs = attempts(3)
    code, out = run_accept(tmp_path, runs, confirmed(runs) + decide(runs[0], {**YES, "no-critical-error": "no"}), capsys)
    assert code == 1 and "FAIL: critical errors: r0" in out
    # a forbidden amount is a critical error without any verdict
    forbidden = [make_run("r0", text=TEXT + " Or EUR 500 for less.")] + runs[1:]
    code, out = run_accept(tmp_path, forbidden, confirmed(forbidden), capsys)
    assert code == 1 and "FAIL critical `r0`: forbidden_present" in out
    # two runs a person rejected and one runtime error leave 0 of 3 usable
    failed = [make_run("r0", runtime_status="ui_error", error="form gave up after 60 s")] + runs[1:]
    code, out = run_accept(tmp_path, failed, confirmed(runs[1:], {**YES, "budget-declined": "no"}), capsys)
    assert code == 1 and "FAIL: luna-medium counteroffer-en: 0 usable, 3 failed, needs 2/3" in out
    slow = attempts(3, latency_ms=61000, origin=None)
    for run in slow:
        run["origin"] = {**make_run(run["run_id"])["origin"], "ui_latency_ms": 61000}
    code, out = run_accept(tmp_path, slow, confirmed(slow), capsys)
    assert code == 1 and "median latency 61.0 s above 60 s" in out


def test_formal_checks_leave_every_wording_of_a_term_to_the_reviewer() -> None:
    """The review #6 wordings: whatever the text says about a term, the formal checks neither pass nor
    fail it; only the forbidden amount and the required value are literal."""
    for text in (
        TEXT.replace("I offer EUR 800", "I propose EUR 800"),
        TEXT.replace("I do not accept the EUR 300 budget or", "The EUR 300 budget is not agreed. I do not accept"),
    ):
        judged = proposal_ai_eval.judge_run(make_run("r", text=text), ORDER, {})
        assert judged["status"] == "PENDING" and judged["critical"] is None, judged
        assert all("not confirmed" in reason for reason in judged["reasons"]), judged


def test_the_approved_any_631_matrix_is_pinned() -> None:
    """Removing a group from suite.json must not go unnoticed: 33 groups, 150 attempts, all web form."""
    suite, orders, runs, _ = proposal_ai_eval.load_suite(SUITE_PATH)
    groups = proposal_ai_eval.program_groups(suite, orders)
    p_cases, terms = ["P01", "P02", "P04", "P05"], [
        "conflict-decline-en", "agreed-confirm-ru", "agreed-change-accepted-en", "agreed-plus-conflict-es",
        "limit-change-accepted-en", "counteroffer-en", "left-open-en", "ceiling-stays-client-ru", "conflict-decline-es",
        "ceiling-and-scope-en",
    ]
    expected = {}
    for series, effort in (("final-luna-medium", "medium"), ("final-luna-high", "high")):
        expected |= {(series, case): (5, 4, effort) for case in p_cases} | {(series, case): (3, 3, effort) for case in terms}
    expected |= {
        ("agreed-luna-medium", case): (10, 10, "medium")
        for case in ("P05", "agreed-confirm-ru", "agreed-plus-conflict-es", "agreed-change-accepted-en", "conflict-decline-es")
    }
    assert {key: (g["attempts"], g["min_usable"], g["reasoning_effort"]) for key, g in groups.items()} == expected
    assert len(groups) == 33 and sum(g["attempts"] for g in groups.values()) == 150 == len(runs)
    assert {g["channel"] for g in groups.values()} == {"web_form"} and {g["model"] for g in groups.values()} == {"openai/gpt-6-luna"}
    assert suite["max_median_latency_ms"] == 60000


def test_the_any_631_suite_is_consistent() -> None:
    """Every stored verdict belongs to a stored run, a criterion of its order and the exact answer,
    input and criterion text it judged, and the runs are the program's runs."""
    suite, orders, runs, verdicts = proposal_ai_eval.load_suite(SUITE_PATH)
    by_id = {run["run_id"]: run for run in runs}
    assert len(by_id) == len(runs) == 150
    for (run_id, criterion_id), row in verdicts.items():
        run = by_id[run_id]
        criteria = {c["id"]: c for c in proposal_ai_eval.criteria_for(orders[run["case_id"]], run)}
        assert row["answer_hash"] == proposal_ai_eval.answer_hash(run["output"])
        assert row["input_hash"] == proposal_ai_eval.input_hash(run)
        if criterion_id in criteria:
            assert row["decision"] is None or row["decision"]["reviewer"] != "agent"
    assert proposal_ai_eval.accept(*proposal_ai_eval.load_suite(SUITE_PATH)) == proposal_ai_eval.accept(suite, orders, runs, verdicts)


def test_the_historical_any_631_series_is_a_fail_for_the_known_reasons() -> None:
    """The approved thresholds and the stored runs, nothing else: FAIL. The language check of the gap
    descriptions finds the Spanish and German ones; the stored runs carry no browser artifact, so every
    run stays PENDING behind its failure and the failures alone fail their groups."""
    status, lines = proposal_ai_eval.accept(*proposal_ai_eval.load_suite(SUITE_PATH))
    report = "\n".join(lines)
    assert status == "FAIL"
    for run_id in (
        "final-luna-medium-ceiling-and-scope-en-1", "final-luna-medium-ceiling-and-scope-en-2",
        "final-luna-high-P02-2", "final-luna-high-P02-3",
    ):
        assert f"PENDING `{run_id}`: wrong_gaps_language" in report, run_id
    assert "FAIL: final-luna-high P02: 0 usable, 2 failed, needs 4/5" in report
    assert "`final-luna-high-conflict-decline-es-1`: runtime: ui_error" in report
    assert "`final-luna-medium-conflict-decline-en-3`: wrong_language; wrong_gaps_language" in report
    assert "evidence: browser artifact missing" in report
    # a human "yes" on the language of German gap descriptions is shown to the reviewer again
    suite, orders, runs, verdicts = proposal_ai_eval.load_suite(SUITE_PATH)
    run = next(r for r in runs if r["run_id"] == "final-luna-high-P02-3")
    judged = proposal_ai_eval.judge_run(run, orders["P02"], verdicts)
    assert judged["reopen"] == ["language-confirmed"]


def test_the_program_cannot_be_empty_and_runs_keep_the_input_of_their_case(tmp_path: Path, capsys) -> None:
    for program in ([], [{"series": "luna-medium", "cases": [], "attempts": 3, "min_usable": 2, "reasoning_effort": "medium"}]):
        code, out = run_accept(tmp_path, [], [], capsys, program=program)
        assert code == 2 and "invalid suite" in out, out
    # the right case_id with a simplified task text is not that case, whatever a person says about it
    runs = attempts(3)
    runs[1]["input"] = {**runs[1]["input"], "task_text": "Build me a website."}
    code, out = run_accept(tmp_path, runs, confirmed(runs), capsys)
    assert code == 2 and "r1: task_text is not the one of case counteroffer-en" in out


def test_missing_ui_evidence_keeps_a_failed_run_pending(tmp_path: Path, capsys) -> None:
    """A non-critical failure does not hide that the run is not verified; a critical one still fails."""
    runs = attempts(3)
    runs[0]["origin"] = None
    rows = confirmed(runs[1:]) + decide(runs[0], {**YES, "budget-declined": "no"})
    code, out = run_accept(tmp_path, runs, rows, capsys)
    assert code == 1 and out.startswith("# Suite t: PENDING") and "PENDING `r0`: budget-declined: read" in out
    rows = confirmed(runs[1:]) + decide(runs[0], {**YES, "terms-not-accepted": "no"})
    code, out = run_accept(tmp_path, runs, rows, capsys)
    assert code == 1 and out.startswith("# Suite t: FAIL") and "FAIL critical `r0`" in out


def test_the_browser_artifact_is_read_and_its_hash_compared(tmp_path: Path, capsys) -> None:
    runs = attempts(3)
    runs[0]["origin"] = {**runs[0]["origin"], "trace": "trace/elsewhere.zip"}
    code, out = run_accept(tmp_path, runs, confirmed(runs), capsys)
    assert code == 1 and "PENDING `r0`: evidence: browser artifact missing" in out
    runs = attempts(3)
    runs[0]["origin"] = {**runs[0]["origin"], "trace_sha256": "0" * 64}
    code, out = run_accept(tmp_path, runs, confirmed(runs), capsys)
    assert code == 1 and "evidence: browser artifact does not match its sha256" in out
    runs = attempts(3)
    runs[0]["origin"] = {**runs[0]["origin"], "ui_latency_ms": True}
    code, out = run_accept(tmp_path, runs, confirmed(runs), capsys)
    assert code == 1 and "evidence: no web form observation" in out


def test_a_changed_violation_type_asks_for_the_decision_again(tmp_path: Path, capsys) -> None:
    runs = attempts(3)
    rows = confirmed(runs)
    retyped = {**ORDER, "criteria": [ORDER["criteria"][0], {**ORDER["criteria"][1], "violation_type": "promised_excluded_work"}]}
    code, out = run_accept(tmp_path, runs, rows, capsys, orders=[retyped, {**ORDER, "id": "other"}])
    assert code == 1 and "terms-not-accepted: not confirmed" in out


def test_losing_the_fee_condition_of_the_p02_orders_is_a_critical_error() -> None:
    for name, case in (("qa_cases.json", "P02"), ("terms.json", "ceiling-and-scope-en")):
        order = next(o for o in json.loads((FIXTURES / name).read_text(encoding="utf-8"))["orders"] if o["id"] == case)
        criteria = {c["id"]: c for c in order["criteria"]}
        assert "fee-open-after-inspection" not in criteria
        for criterion_id in ("fee-left-open", "fee-after-inspection"):
            assert criteria[criterion_id]["critical"] and criteria[criterion_id]["violation_type"] == "lost_mandatory_condition"


def test_review_copies_the_agents_reason_only_for_the_same_answer(tmp_path: Path, monkeypatch) -> None:
    order = {**ORDER, "criteria": ORDER["criteria"][:1]}
    run = make_run("r0")
    suggestion = {"answer": "unknown", "reviewer": "agent", "reason": "agent doubt", "quote": None}
    row = {**decide(run, {"budget-declined": "yes"}, order)[0], "suggestion": suggestion, "decision": None}
    suite = write_suite(tmp_path, [run], [row], orders=[order])
    # no-critical-error: y with no suggestion; budget-declined: y against the agent's unknown, own reason
    answers = iter(["y", "y", "refused in the second sentence"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    args = ["review", "--suite", str(suite), "--reviewer", "qa"]
    assert proposal_ai_eval.main(args) == 0
    decisions = {r["criterion_id"]: r for r in proposal_ai_eval.read_jsonl(tmp_path / "verdicts.jsonl") if r["decision"]}
    assert decisions["budget-declined"]["decision"]["reason"] == "refused in the second sentence"
    assert decisions["budget-declined"]["input_hash"] == proposal_ai_eval.input_hash(run) and decisions["budget-declined"]["criterion_hash"]
    # --redo shows only the named decision; a matching answer keeps the agent's reason
    row["suggestion"] = {**suggestion, "answer": "yes", "reason": "agent reason"}
    (tmp_path / "verdicts.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _prompt="": "y")
    assert proposal_ai_eval.main([*args, "--redo", "r0/budget-declined"]) == 0
    last = proposal_ai_eval.read_jsonl(tmp_path / "verdicts.jsonl")[-1]
    assert last["criterion_id"] == "budget-declined" and last["decision"]["reason"] == "agent reason"


def test_review_asks_again_for_the_general_answer_that_a_critical_detail_contradicts(tmp_path: Path, monkeypatch) -> None:
    run = make_run("r0")
    rows = decide(run, {**YES, "terms-not-accepted": "no"})
    suite = write_suite(tmp_path, [run], rows)
    prompts = {"Violation": "unagreed_term_accepted", "reason": "own reason"}
    monkeypatch.setattr("builtins.input", lambda prompt="": next((v for k, v in prompts.items() if k in prompt), "n"))
    assert proposal_ai_eval.main(["review", "--suite", str(suite), "--reviewer", "qa"]) == 0
    last = proposal_ai_eval.read_jsonl(tmp_path / "verdicts.jsonl")[-1]
    assert last["criterion_id"] == "no-critical-error" and last["decision"]["answer"] == "no"
    assert last["decision"]["violation_type"] == "unagreed_term_accepted"
