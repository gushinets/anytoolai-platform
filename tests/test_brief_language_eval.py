"""Canonical language review cannot pass from a successful generation alone."""

import importlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

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
    ) + 3  # Recipe regressions supplement, rather than replace, the original matrix.
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


def test_recipe_regression_preserves_the_report_and_reviews_every_prose_field():
    cases = [case for case in CASES if case["id"].endswith("-borscht")]
    assert {case["source_language"] for case in cases} == {"ru", "en", "es"}
    russian = next(case for case in cases if case["source_language"] == "ru")
    assert russian["input"]["brief_text"] == (
        "Рецепт борща: свёкла, капуста, говядина. Варить два часа."
    )
    for case in cases:
        assert "2026-11-11" in case["historical_failure_report"]

    output = CANONICAL[russian["id"]]
    fields = evaluation.authored_fields(output)
    for name, value in output["brief"]["values"].items():
        if isinstance(value, str):
            assert fields[f"/brief/values/{name}"] == value
        else:
            for index, item in enumerate(value):
                assert fields[f"/brief/values/{name}/{index}"] == item
    for index, issue in enumerate(output["issues"]):
        assert fields[f"/issues/{index}/description"] == issue["description"]
        if "evidence" in issue:
            assert fields[f"/issues/{index}/evidence"] == issue["evidence"]
    for index, question in enumerate(output["questions"]):
        for field in ("question", "rationale"):
            assert fields[f"/questions/{index}/{field}"] == question[field]
    assert fields["/document/summary"] == output["document"]["summary"]
    for index, section in enumerate(output["document"]["sections"]):
        assert fields[f"/document/sections/{index}/content"] == section["content"]


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


UNSAFE_KEYS = (
    "../escaped",
    "../../escaped",
    "/absolute",
    "sub/file",
    r"..\escaped",
    r"sub\file",
    r"C:\absolute",
    r"\\server\share\file",
    "",
    ".",
    "..",
    "bad.name",
    "bad\x00name",
)


def cli_args(command, out):
    arguments = ["brief_language_eval.py", command, "--out", str(out)]
    if command == "run":
        arguments += [
            "--api-url",
            "http://127.0.0.1:18000",
            "--project",
            "anytoolai-test",
            "--scenario",
            "acceptance_builder.check_v1",
            "--repeats",
            "1",
        ]
    return arguments


def ab_record(case_id):
    run = record()
    run["case"] = next(case for case in CASES if case["id"] == case_id)
    run["output"] = deepcopy(CANONICAL[case_id])
    if run["case"]["scenario_id"] == "acceptance_builder.draft_v1":
        run["ledger"]["actions"] = run["ledger"]["actions"][:1]
        run["ledger"]["calls"] = run["ledger"]["calls"][:1]
    run["ledger"]["artifacts"][0]["content_json"] = run["output"]
    return run


@pytest.mark.parametrize("mode", ["D", "C"])
@pytest.mark.parametrize("language", ["RU", "EN", "ES"])
@pytest.mark.parametrize("family", ["basic", "weak"])
def test_ab_metadata_must_match_expected_analysis_language(mode, language, family):
    run = ab_record(f"ANY761-AB-{mode}-{language}-{family}")
    expected = run["case"]["expected_language"]
    values = run["output"]["extracted"]["values"]
    for tag in (expected, expected.upper(), expected.title() + "-mX"):
        values["analysis_language"] = tag
        assert evaluation.review_status(run, completed_review(run)) == "PASS"
    values["analysis_language"] = "en" if expected != "en" else "ru"
    assert evaluation.review_status(run, completed_review(run)) == "FAIL"


def test_explicit_analysis_language_override_takes_precedence_over_source_language():
    run = ab_record("ANY761-AB-D-RU-weak")
    run["case"] = next(case for case in CASES if case["id"] == "ANY761-AB-D-RU-override")
    assert run["case"]["source_language"] != run["case"]["expected_language"]
    values = run["output"]["extracted"]["values"]
    values["analysis_language"] = run["case"]["source_language"]
    assert evaluation.review_status(run, completed_review(run)) == "FAIL"
    values["analysis_language"] = run["case"]["expected_language"]
    assert evaluation.review_status(run, completed_review(run)) == "PASS"


@pytest.mark.parametrize("tag", [None, "", "ru_XX", "ru-", "ru-!", "ru\n", 1, [], {}])
def test_ab_invalid_language_tag_cannot_pass(tag):
    run = ab_record("ANY761-AB-D-RU-weak")
    run["output"]["extracted"]["values"]["analysis_language"] = tag
    assert evaluation.review_status(run, completed_review(run)) == "FAIL"


def test_ab_missing_language_tag_cannot_pass():
    run = ab_record("ANY761-AB-D-RU-weak")
    del run["output"]["extracted"]["values"]["analysis_language"]
    assert evaluation.review_status(run, completed_review(run)) == "FAIL"


@pytest.mark.parametrize("expected", [None, "", "ru_XX"])
def test_ab_missing_or_invalid_expected_language_cannot_pass(expected):
    run = ab_record("ANY761-AB-D-RU-weak")
    run["case"] = {**run["case"], "expected_language": expected}
    assert evaluation.review_status(run, completed_review(run)) == "FAIL"


@pytest.mark.parametrize("expected", ["es-MX", "ES-mx", "eS-MX"])
def test_ab_regional_expected_language_matches_primary_tag(expected):
    run = ab_record("ANY761-AB-D-ES-weak")
    run["case"] = {**run["case"], "expected_language": expected}
    assert evaluation.review_status(run, completed_review(run)) == "PASS"


def test_legacy_document_requires_its_historical_ledger_step():
    run = ab_record("ANY761-AB-D-RU-weak")
    del run["output"]["extracted"]["values"]["analysis_language"]
    run["output"]["document"] = {"summary": "Уточните требования.", "sections": []}
    assert evaluation.review_status(run, completed_review(run)) == "PENDING"
    run["ledger"]["actions"].append({
        **run["ledger"]["actions"][0], "id": "document", "step_id": "generate_document",
    })
    run["ledger"]["calls"].append({
        **run["ledger"]["calls"][0], "id": "document-call", "action_run_id": "document",
    })
    assert evaluation.review_status(run, completed_review(run)) == "PASS"
    run["output"]["extracted"]["values"]["analysis_language"] = "en"
    assert evaluation.review_status(run, completed_review(run)) == "FAIL"


@pytest.mark.parametrize(
    ("tag", "status", "exit_code"),
    [("en", "FAIL", 1), ("ru", "PASS", 0), ("ru-RU", "PASS", 0), ("RU-ru", "PASS", 0)],
)
def test_weak_draft_report_checks_metadata_without_modifying_evidence(
    monkeypatch, tmp_path, capsys, tag, status, exit_code,
):
    run = ab_record("ANY761-AB-D-RU-weak")
    run["output"]["extracted"]["values"]["analysis_language"] = tag
    run.update(attempt=1, snapshot={})
    assert evaluation.authored_fields(run["output"]) == {}
    key = run["case"]["id"] + "--1"
    files = {
        "manifest.json": {"runs": [key], "cases": [run["case"]], "snapshot": {}},
        f"{key}.json": run,
        f"{key}.review.json": completed_review(run),
    }
    for name, content in files.items():
        evaluation.write_json(tmp_path / name, content)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    monkeypatch.setattr(sys, "argv", cli_args("report", tmp_path))
    assert evaluation.main() == exit_code
    assert capsys.readouterr().out == f"{key}: {status}\n"
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


@pytest.mark.parametrize("case_id", UNSAFE_KEYS)
def test_run_rejects_all_unsafe_case_ids_before_any_collection(monkeypatch, tmp_path, case_id):
    valid = deepcopy(record()["case"])
    unsafe = {**valid, "id": case_id}
    suite = tmp_path / "cases.json"
    suite.write_text(json.dumps({"cases": [valid, unsafe]}), encoding="utf-8")
    out = tmp_path / "results"
    docker = Mock(side_effect=AssertionError("must reject before Docker access"))
    collect = Mock(side_effect=AssertionError("must reject before provider access"))
    monkeypatch.setattr(evaluation, "SUITE", suite)
    monkeypatch.setattr(evaluation, "_docker", docker)
    monkeypatch.setattr(evaluation, "collect", collect)
    monkeypatch.setattr(sys, "argv", cli_args("run", out))

    with pytest.raises(ValueError, match="invalid evidence filename"):
        evaluation.main()

    docker.assert_not_called()
    collect.assert_not_called()
    assert not out.exists()
    assert set(tmp_path.iterdir()) == {suite}


@pytest.mark.parametrize("key", UNSAFE_KEYS)
def test_report_rejects_unsafe_manifest_keys(monkeypatch, tmp_path, key):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"runs": [key]}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", cli_args("report", tmp_path))

    with pytest.raises(ValueError, match="invalid evidence filename"):
        evaluation.main()

    assert set(tmp_path.iterdir()) == {manifest}


def test_cli_run_and_review_report_round_trip_preserves_json_data(monkeypatch, tmp_path):
    case = deepcopy(record()["case"])
    case["input"]["brief_text"] = 'Русский текст: ../../outside, C:\\file, "цитата"'
    suite = tmp_path / "cases.json"
    suite.write_text(json.dumps({"cases": [case]}), encoding="utf-8")
    snapshot = {"source_sha256": {}}
    out = tmp_path / "results"
    run = {**record(), "case": case, "attempt": 1, "snapshot": snapshot, "evidence_error": None}
    collector = Mock(return_value=run)
    monkeypatch.setattr(evaluation, "SUITE", suite)
    monkeypatch.setattr(evaluation, "_docker", Mock(return_value=json.dumps(snapshot)))
    monkeypatch.setattr(evaluation, "_git_state", lambda: {})
    monkeypatch.setattr(evaluation, "collect", collector)
    monkeypatch.setattr(sys, "argv", cli_args("run", out))

    assert evaluation.main() == 0
    collector.assert_called_once()
    key = case["id"] + "--1"
    saved = json.loads((out / f"{key}.json").read_text(encoding="utf-8"))
    assert saved == run
    assert {path.name for path in out.iterdir()} == {
        "manifest.json",
        f"{key}.json",
        f"{key}.review.json",
    }

    monkeypatch.setattr(sys, "argv", cli_args("report", out))
    assert evaluation.main() == 1  # Generation alone still awaits review.
    (out / f"{key}.review.json").write_text(json.dumps(completed_review(saved)), encoding="utf-8")
    assert evaluation.main() == 0


def test_write_json_never_overwrites_existing_evidence(tmp_path):
    path = evaluation.evidence_path(tmp_path, "case--1.json")
    original = {"result": "original"}
    evaluation.write_json(path, original)

    with pytest.raises(FileExistsError):
        evaluation.write_json(path, {"result": "replacement"})

    assert json.loads(path.read_text(encoding="utf-8")) == original


@pytest.mark.parametrize("filename", ["manifest.json", "case--1.json", "case--1.review.json"])
def test_evidence_path_rejects_a_filename_resolving_outside_root(monkeypatch, tmp_path, filename):
    directory = tmp_path / "results"
    link = directory / filename
    outside = tmp_path / "outside.json"
    resolve = Path.resolve

    def resolve_path(path, *args, **kwargs):
        if path == link:
            return outside
        return resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve_path)
    with pytest.raises(ValueError, match="outside the output directory"):
        evaluation.evidence_path(directory, filename)


def test_evaluator_uses_the_shared_language_tag_contract():
    tags = json.loads(
        (ROOT / "tests/fixtures/brief_language_eval/language_tags.json").read_text(encoding="utf-8")
    )
    for tag in tags["accepted"]:
        assert evaluation.primary_language(tag) == tag.split("-")[0].lower()
    for tag in tags["rejected"]:
        assert evaluation.primary_language(tag) is None
