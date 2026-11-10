"""Canonical language review cannot pass from a successful generation alone."""

import importlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.support.brief_language import CANONICAL, CASES

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/agent"))
evaluation = importlib.import_module("brief_language_eval")


def record():
    case = next(case for case in CASES if case["id"] == "ANY761-AB-C-RU-basic")
    return {
        "case": case,
        "output": CANONICAL[case["id"]],
        "error": None,
        "session_id": "session-1",
        "result_id": "result-1",
        "ledger": {
            "calls": [
                {
                    "id": "call-1",
                    "model": "test",
                    "action_run_id": step,
                    "status": "succeeded",
                    "scenario_session_id": "session-1",
                }
                for step in ("extract", "compare")
            ],
            "actions": [
                {
                    "id": step,
                    "step_id": step,
                    "status": "succeeded",
                    "output_artifact_id": "result-1",
                    "scenario_session_id": "session-1",
                }
                for step in ("extract", "compare")
            ],
            "artifacts": [
                {
                    "id": "result-1",
                    "scenario_session_id": "session-1",
                    "content_json": CANONICAL[case["id"]],
                }
            ],
        },
    }


def completed_review(run):
    review = evaluation.review_template(run)
    review["reviewer"] = "test-reviewer"
    for group in ("fields", "criteria"):
        review[group] = dict.fromkeys(review[group], True)
    return review


def test_every_authored_field_including_hidden_summary_is_reviewed():
    fields = evaluation.authored_fields(record()["output"])
    assert "/document/summary" not in fields
    assert fields["/comparison/deltas/0/evidence"].startswith("Предоставлен")
    assert "/comparison/rationale" in fields
    assert "/extracted/values/acceptance_criteria/0" in fields
    assert not any("/title" in path or "/verdict" in path or "/status" in path for path in fields)
    bd = evaluation.authored_fields(CANONICAL["ANY761-BD-RU-basic"])
    assert "/issues/0/description" in bd
    assert "/questions/0/rationale" in bd
    assert "/brief_text" not in bd


def test_generated_output_is_pending_until_every_field_and_fact_is_reviewed():
    run = record()
    assert evaluation.review_status(run, evaluation.review_template(run)) == "PENDING"
    review = completed_review(run)
    assert evaluation.review_status(run, review) == "PASS"
    review["fields"]["/comparison/rationale"] = None
    assert evaluation.review_status(run, review) == "PENDING"
    review["fields"]["/comparison/rationale"] = False
    assert evaluation.review_status(run, review) == "FAIL"


def test_incomplete_stale_and_invalid_reviews_cannot_pass():
    run = record()
    review = completed_review(run)
    del review["fields"]["/comparison/rationale"]
    with pytest.raises(ValueError, match="incomplete"):
        evaluation.review_status(run, review)
    review = completed_review(run)
    changed = deepcopy(run)
    changed["output"]["comparison"]["rationale"] = "An English leak."
    with pytest.raises(ValueError, match="evidence"):
        evaluation.review_status(changed, review)
    review["criteria"][next(iter(review["criteria"]))] = "yes"
    with pytest.raises(ValueError, match="decisions"):
        evaluation.review_status(run, review)


@pytest.mark.parametrize("field", ["error", "evidence_error"])
def test_runtime_and_evidence_errors_are_failures(field):
    run = record()
    run[field] = "failed"
    assert evaluation.review_status(run, completed_review(run)) == "FAIL"


def test_missing_or_wrong_session_ledger_is_not_accepted():
    run = record()
    run["ledger"]["artifacts"] = []
    assert evaluation.review_status(run, completed_review(run)) == "PENDING"
    run = record()
    run["ledger"]["calls"][0]["scenario_session_id"] = "another-session"
    with pytest.raises(ValueError, match="another session"):
        evaluation.review_status(run, completed_review(run))


def test_partial_workflow_ledger_cannot_pass_even_with_all_review_decisions():
    run = record()
    run["ledger"]["actions"].pop()
    run["ledger"]["calls"].pop()
    assert evaluation.review_status(run, completed_review(run)) == "PENDING"


def test_failed_attempt_keeps_input_and_error_without_retry(monkeypatch):
    calls = []

    def fail(url, **kwargs):
        calls.append(url)
        raise OSError("offline")

    monkeypatch.setattr(evaluation, "_request", fail)
    args = SimpleNamespace(api_url="http://localhost:8000", timeout=1, project="test")
    run = evaluation.collect(args, CASES[0], 1, {})
    assert len(calls) == 1
    assert run["case"]["input"] == CASES[0]["input"]
    assert run["error"] == "OSError: offline"
    assert run["confirmed_reasoning_effort"] is None


def test_suite_has_twelve_families_in_three_languages_and_honest_provenance():
    assert len(CASES) == len(evaluation.SCENARIOS) * len(("ru", "en", "es")) * len(
        ("basic", "weak", "mixed", "override")
    )
    assert len({case["id"] for case in CASES}) == len(CASES)
    for scenario in evaluation.SCENARIOS:
        for language in ("ru", "en", "es"):
            cases = [
                case
                for case in CASES
                if case["scenario_id"] == scenario and case["source_language"] == language
            ]
            assert {case["family"] for case in cases} == {"basic", "weak", "mixed", "override"}
    for case in CASES:
        assert case["provenance"] and case["criteria"]
        assert case["input"]["brief_text"]
    assert not {"BD-RU-10", "AB-D-RU-03", "AB-C-RU-01"} & {case["id"] for case in CASES}
    json.dumps(CASES, ensure_ascii=False)


def test_machine_only_weak_draft_has_no_prose_to_review():
    run = record()
    run["case"] = next(case for case in CASES if case["id"] == "ANY761-AB-D-RU-weak")
    run["output"] = CANONICAL[run["case"]["id"]]
    run["ledger"]["actions"] = run["ledger"]["actions"][:1]
    run["ledger"]["calls"] = run["ledger"]["calls"][:1]
    run["ledger"]["artifacts"][0]["content_json"] = run["output"]
    assert evaluation.authored_fields(run["output"]) == {}
    assert evaluation.review_status(run, evaluation.review_template(run)) == "PENDING"
    assert evaluation.review_status(run, completed_review(run)) == "PASS"
