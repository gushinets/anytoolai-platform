"""Canonical language review cannot pass from a successful generation alone."""

import importlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.support.brief_language import CANONICAL, CASES, assert_summary_matches_sources

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/agent"))
evaluation = importlib.import_module("brief_language_eval")


def record(steps=("extract", "compare")):
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
                for step in steps
            ],
            "actions": [
                {
                    "id": step,
                    "step_id": step,
                    "status": "succeeded",
                    "output_artifact_id": "result-1",
                    "scenario_session_id": "session-1",
                }
                for step in steps
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


def completed_review(run, *, historical=False):
    review = evaluation.review_template(run, historical=historical)
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


@pytest.mark.parametrize(
    ("section_id", "replacement"),
    [("gaps", ""), ("next-steps", "- How much will the article cost?\n")],
    ids=["dropped-issue", "rephrased-question"],
)
def test_canonical_brief_rejects_changed_section(section_id, replacement):
    case = CANONICAL["ANY761-BD-EN-basic"]
    document = deepcopy(case["document"])
    sources = (case["brief"], case["issues"], case["questions"], "en")
    assert_summary_matches_sources(document, *sources)
    section = next(s for s in document["sections"] if s["id"] == section_id)
    _, remaining = section["content"].split("\n", 1)
    section["content"] = replacement + remaining
    with pytest.raises(AssertionError, match=section_id):
        assert_summary_matches_sources(document, *sources)


@pytest.mark.parametrize("language", ["en", "ru", "es"])
@pytest.mark.parametrize(
    ("collection", "key"), [("issues", "description"), ("questions", "question")]
)
def test_weak_summary_rejects_repeated_clarification_lists(language, collection, key):
    case = CANONICAL[f"ANY761-BD-{language.upper()}-weak"]
    repeated = " ".join(record[key] for record in case[collection])
    document = {**case["document"], "summary": f"{case['document']['summary']} {repeated}"}
    with pytest.raises(AssertionError, match="summary repeats"):
        assert_summary_matches_sources(
            document, case["brief"], case["issues"], case["questions"], language
        )


@pytest.mark.parametrize("condition", [
    "If the budget is approved",
    "If the budget is approved, and if the client signs",
])
def test_canonical_brief_rejects_current_readiness_claim_after_budget_condition(condition):
    case = CANONICAL["ANY761-BD-EN-basic"]
    conditional = f"The brief is not ready to start. {condition}, the brief is ready to start work"
    document = {**case["document"], "summary": conditional + "."}
    sources = (case["brief"], case["issues"], case["questions"], "en")
    assert_summary_matches_sources(document, *sources)
    document["summary"] = conditional + ", however the brief is ready to start right now."
    with pytest.raises(AssertionError, match="Conflicting readiness"):
        assert_summary_matches_sources(document, *sources)


def test_canonical_brief_rejects_independent_verdict_after_scope_change():
    case = CANONICAL["ANY761-BD-EN-basic"]
    summary = (
        "The brief is not ready to start. If anything changes, when necessary we will "
        "revisit the scope, and in any case the brief is ready to start right now."
    )
    with pytest.raises(AssertionError, match="Conflicting readiness"):
        assert_summary_matches_sources(
            {**case["document"], "summary": summary},
            case["brief"], case["issues"], case["questions"], "en",
        )


@pytest.mark.parametrize("subject_and_verb", ["the brief is", "it’s"])
def test_canonical_brief_rejects_contradictory_continuing_readiness(subject_and_verb):
    case = CANONICAL["ANY761-BD-EN-basic"]
    summary = (
        "The brief is not ready to start work. "
        f"However, {subject_and_verb} still ready to start work."
    )
    with pytest.raises(AssertionError, match="Conflicting readiness"):
        assert_summary_matches_sources(
            {**case["document"], "summary": summary},
            case["brief"], case["issues"], case["questions"], "en",
        )


@pytest.mark.parametrize(
    ("language", "verdict", "timing", "instruction"),
    [
        ("en", "The brief is not ready to start work", "only after the client approves the budget",
         "contact the client"),
        ("ru", "Бриф не готов к работе", "только после согласования", "свяжитесь с клиентом"),
        ("es", "El encargo no está listo para empezar", "solo después de la aprobación",
         "contacte con el cliente"),
    ],
    ids=["en", "ru", "es"],
)
def test_canonical_brief_distinguishes_timed_verdict_from_timed_action(
    language, verdict, timing, instruction
):
    case = CANONICAL[f"ANY761-BD-{language.upper()}-basic"]
    sources = case["brief"], case["issues"], case["questions"], language
    summary = f"{verdict} — {timing}"
    with pytest.raises(AssertionError, match="opening readiness"):
        assert_summary_matches_sources({**case["document"], "summary": summary + "."}, *sources)
    document = {**case["document"], "summary": f"{verdict}. {timing.capitalize()}, {instruction}."}
    assert_summary_matches_sources(document, *sources)


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


def test_legacy_machine_only_weak_draft_has_no_prose_to_review():
    run = record(["extract"])
    run["case"] = next(case for case in CASES if case["id"] == "ANY761-AB-D-RU-weak")
    run["output"] = {"extracted": CANONICAL[run["case"]["id"]]["extracted"]}
    run["ledger"]["artifacts"][0]["content_json"] = run["output"]
    assert evaluation.authored_fields(run["output"]) == {}
    assert evaluation.review_status(run, completed_review(run)) == "FAIL"
    template = evaluation.review_template(run, historical=True)
    assert evaluation.review_status(run, template, historical=True) == "PENDING"
    review = completed_review(run, historical=True)
    assert evaluation.review_status(run, review, historical=True) == "PASS"


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
    case = next(case for case in CASES if case["id"] == case_id)
    output = deepcopy(CANONICAL[case_id])
    steps = ["extract", "compare"]
    if case["scenario_id"] == "acceptance_builder.draft_v1":
        steps = ["extract", "detect_issues"]
        if output["issues"]:
            steps.append("generate_questions")
    run = record(steps)
    run["case"] = case
    run["output"] = output
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
    assert evaluation.review_status(run, completed_review(run)) == "FAIL"
    review = completed_review(run, historical=True)
    assert evaluation.review_status(run, review, historical=True) == "PENDING"
    run["ledger"]["actions"].append({
        **run["ledger"]["actions"][0], "id": "document", "step_id": "generate_document",
    })
    run["ledger"]["calls"].append({
        **run["ledger"]["calls"][0], "id": "document-call", "action_run_id": "document",
    })
    review = completed_review(run, historical=True)
    assert evaluation.review_status(run, review, historical=True) == "PASS"
    run["output"]["extracted"]["values"]["analysis_language"] = "en"
    review = completed_review(run, historical=True)
    assert evaluation.review_status(run, review, historical=True) == "FAIL"


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
    assert set(evaluation.authored_fields(run["output"])) == {
        "/issues/0/description", "/questions/0/question", "/questions/0/rationale",
    }
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
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["evidence_contract"] == "current"
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


def test_draft_risk_suite_covers_all_four_briefs_in_each_language():
    cases = evaluation.draft_risk_cases()
    assert len({c["id"] for c in cases}) == len(cases) == 12
    assert len({c["input"]["brief_text"] for c in cases}) == 12
    assert {(c["family"], c["expected_language"]) for c in cases} == {
        (family, lang)
        for family in ("vague", "complete", "contradiction", "feasibility")
        for lang in ("ru", "en", "es")
    }
    assert all(c["scenario_id"] == "acceptance_builder.draft_v1" and c["criteria"] for c in cases)


@pytest.mark.parametrize(
    ("suite", "family", "count"),
    [
        ("draft-risks", None, 36),
        ("draft-risks", "feasibility", 9),
        ("draft-risks", "basic", 0),
        ("language", "feasibility", 0),
    ],
)
def test_draft_cli_selects_cases_before_collection(monkeypatch, tmp_path, suite, family, count):
    out = tmp_path / "results"
    args = cli_args("run", out)
    args[args.index("--scenario") + 1] = "acceptance_builder.draft_v1"
    args[args.index("--repeats") + 1] = "3"
    args.extend(["--suite", suite])
    if family:
        args.extend(["--family", family])
    snapshot = Mock(return_value="{}")
    collector = Mock(
        side_effect=lambda args, case, attempt, snapshot: {
            "case": case,
            "error": None,
            "evidence_error": None,
        }
    )
    monkeypatch.setattr(evaluation, "_docker", snapshot)
    monkeypatch.setattr(evaluation, "_git_state", lambda: {})
    monkeypatch.setattr(evaluation, "collect", collector)
    monkeypatch.setattr(sys, "argv", args)
    if not count:
        with pytest.raises(SystemExit) as error:
            evaluation.main()
        assert error.value.code == 2
        snapshot.assert_not_called()
        collector.assert_not_called()
        assert not out.exists()
        return
    assert evaluation.main() == 0
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    expected = [c for c in evaluation.draft_risk_cases() if family is None or c["family"] == family]
    assert manifest["cases"] == expected
    assert set(manifest["runs"]) == {f"{c['id']}--{n}" for c in expected for n in range(1, 4)}
    assert collector.call_count == count


def risk_record(family, sections, steps, attempt=1):
    case = next(
        case for case in evaluation.draft_risk_cases()
        if case["family"] == family and case["expected_language"] == "ru"
    )
    output = {"extracted": CANONICAL["ANY761-AB-D-RU-weak"]["extracted"], **sections}
    run = record(steps)
    run.update(case=case, output=deepcopy(output), attempt=attempt, snapshot={})
    run["ledger"]["artifacts"][0]["content_json"] = run["output"]
    return run


def write_report_inputs(out, *runs, historical=False):
    keys = [f"{run['case']['id']}--{run['attempt']}" for run in runs]
    cases = {run["case"]["id"]: run["case"] for run in runs}
    evaluation.write_json(
        out / "manifest.json", {"runs": keys, "cases": list(cases.values()), "snapshot": {}}
    )
    for key, run in zip(keys, runs, strict=True):
        evaluation.write_json(out / f"{key}.json", run)
        evaluation.write_json(
            out / f"{key}.review.json", completed_review(run, historical=historical)
        )
    return keys


def any761_archive_record(mode, *, document=False, document_step=True):
    case = next(case for case in CASES if case["id"] == f"ANY761-AB-{mode}-RU-weak")
    canonical = CANONICAL[case["id"]]
    output = {"extracted": deepcopy(canonical["extracted"])}
    steps = ["extract"]
    if mode == "C":
        output["comparison"] = deepcopy(canonical["comparison"])
        steps.append("compare")
    if document:
        del output["extracted"]["values"]["analysis_language"]
        output["document"] = {"summary": "Уточните требования.", "sections": []}
        if document_step:
            steps.append("generate_document")
    run = record(steps)
    run.update(case=case, output=output, attempt=1, snapshot={})
    run["ledger"]["artifacts"][0]["content_json"] = output
    return run


@pytest.mark.parametrize(("mode", "document"), [("D", False), ("D", True), ("C", True)])
def test_cli_replays_any761_archive_only_with_explicit_opt_in(
    mode, document, monkeypatch, tmp_path, capsys
):
    run = any761_archive_record(mode, document=document)
    (key,) = write_report_inputs(tmp_path, run, historical=True)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    args = cli_args("report", tmp_path)
    monkeypatch.setattr(sys, "argv", args)
    assert evaluation.main() == 1
    assert capsys.readouterr().out.startswith(f"{key}: FAIL")

    monkeypatch.setattr(sys, "argv", [*args, "--historical-any-761"])
    assert evaluation.main() == 0
    assert capsys.readouterr().out == f"{key}: PASS\n"
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


@pytest.mark.parametrize("missing", ["document_step", "review_decision"])
def test_cli_archive_mode_still_requires_ledger_and_review(missing, monkeypatch, tmp_path, capsys):
    run = any761_archive_record("D", document=True, document_step=missing != "document_step")
    (key,) = write_report_inputs(tmp_path, run, historical=True)
    if missing == "review_decision":
        path = tmp_path / f"{key}.review.json"
        review = completed_review(run, historical=True)
        review["fields"]["/document/summary"] = None
        path.write_text(json.dumps(review), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [*cli_args("report", tmp_path), "--historical-any-761"])
    assert evaluation.main() == 1
    assert capsys.readouterr().out == f"{key}: PENDING\n"


def test_archive_report_checks_the_original_review_digest(monkeypatch, tmp_path):
    run = any761_archive_record("D")
    (key,) = write_report_inputs(tmp_path, run, historical=True)
    review = completed_review(run, historical=True)
    review["evidence_sha256"] = "different-record"
    (tmp_path / f"{key}.review.json").write_text(json.dumps(review), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [*cli_args("report", tmp_path), "--historical-any-761"])
    with pytest.raises(ValueError, match="does not belong to this evidence"):
        evaluation.main()


@pytest.mark.parametrize("kind", ["draft-risks", "current-manifest", "wrong-scenario"])
def test_archive_cli_rejects_other_manifests(kind, monkeypatch, tmp_path, capsys):
    if kind == "draft-risks":
        run = risk_record("complete", {}, ("extract",))
    else:
        run = any761_archive_record("D")
        if kind == "wrong-scenario":
            run["case"] = {**run["case"], "scenario_id": "acceptance_builder.check_v1"}
    write_report_inputs(tmp_path, run, historical=True)
    if kind == "current-manifest":
        path = tmp_path / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["evidence_contract"] = "current"
        path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [*cli_args("report", tmp_path), "--historical-any-761"])
    with pytest.raises(SystemExit) as error:
        evaluation.main()
    assert error.value.code == 2
    assert "requires an unversioned ANY-761 AB archive" in capsys.readouterr().err


@pytest.mark.parametrize("family", ["vague", "feasibility", "contradiction", "complete"])
def test_risk_report_cannot_certify_an_extract_only_stack(
    family, monkeypatch, tmp_path, capsys
):
    stale = risk_record(family, {}, ("extract",))
    clean = risk_record(
        "complete", {"issues": [], "questions": []}, ("extract", "detect_issues"), attempt=2
    )
    stale_key, clean_key = write_report_inputs(tmp_path, stale, clean)
    monkeypatch.setattr(sys, "argv", cli_args("report", tmp_path))

    assert evaluation.main() == 1
    stale_line, clean_line = capsys.readouterr().out.splitlines()
    assert stale_line.startswith(f"{stale_key}: FAIL")
    assert "requires both issues and questions" in stale_line
    assert clean_line == f"{clean_key}: PASS"


@pytest.mark.parametrize(
    ("sections", "steps", "status"),
    [
        ({"issues": []}, ("extract", "detect_issues"), "FAIL"),
        ({"questions": []}, ("extract",), "FAIL"),
        ({"issues": [], "questions": None}, ("extract", "detect_issues"), "FAIL"),
        ({"issues": {}, "questions": []}, ("extract", "detect_issues"), "FAIL"),
        ({"issues": [None], "questions": []}, ("extract", "detect_issues"), "FAIL"),
        ({"issues": [], "questions": []}, ("extract",), "PENDING"),
        ({"issues": [], "questions": []}, ("extract", "detect_issues"), "PASS"),
    ],
)
def test_report_requires_both_arrays_and_a04_for_clean_drafts(
    sections, steps, status, monkeypatch, tmp_path, capsys
):
    run = risk_record("complete", sections, steps)
    (key,) = write_report_inputs(tmp_path, run)
    monkeypatch.setattr(sys, "argv", cli_args("report", tmp_path))
    assert evaluation.main() == (0 if status == "PASS" else 1)
    assert capsys.readouterr().out.startswith(f"{key}: {status}")


@pytest.mark.parametrize("with_a05", [False, True])
def test_risk_report_demands_a05_for_nonempty_issues(with_a05, monkeypatch, tmp_path, capsys):
    sections = {k: CANONICAL["ANY761-AB-D-RU-weak"][k] for k in ("issues", "questions")}
    steps = ("extract", "detect_issues", "generate_questions") if with_a05 else (
        "extract", "detect_issues",
    )
    run = risk_record("vague", sections, steps)
    (key,) = write_report_inputs(tmp_path, run)
    monkeypatch.setattr(sys, "argv", cli_args("report", tmp_path))
    assert evaluation.main() == (0 if with_a05 else 1)
    assert capsys.readouterr().out == f"{key}: {'PASS' if with_a05 else 'PENDING'}\n"


@pytest.mark.parametrize("problem", ["failed_call", "missing_artifact", "skipped_action"])
def test_a04_needs_successful_same_session_evidence(problem):
    run = risk_record("complete", {"issues": [], "questions": []}, ("extract", "detect_issues"))
    if problem == "failed_call":
        run["ledger"]["calls"][1]["status"] = "failed"
    elif problem == "missing_artifact":
        run["ledger"]["actions"][1]["output_artifact_id"] = "absent"
    else:
        run["ledger"]["actions"][1]["status"] = "skipped"
    assert evaluation.review_status(run, completed_review(run)) == "PENDING"


def test_clean_draft_cannot_claim_questions_without_issues():
    sections = {"issues": [], "questions": CANONICAL["ANY761-AB-D-RU-weak"]["questions"]}
    run = risk_record("complete", sections, ("extract", "detect_issues"))
    assert evaluation.review_status(run, completed_review(run)) == "FAIL"


@pytest.mark.parametrize("field", ["issues", "questions"])
def test_brief_decoder_rejects_missing_or_nonarray_sections(field):
    run = record(["extract", "detect_issues", "generate_questions", "generate_document"])
    run["case"] = next(case for case in CASES if case["id"] == "ANY761-BD-RU-basic")
    run["output"] = deepcopy(CANONICAL[run["case"]["id"]])
    run["ledger"]["artifacts"][0]["content_json"] = run["output"]
    assert evaluation.review_status(run, completed_review(run)) == "PASS"
    run["output"].pop(field)
    assert evaluation.review_status(run, completed_review(run)) == "FAIL"
    run["output"][field] = None
    assert evaluation.review_status(run, completed_review(run)) == "FAIL"


def test_run_preserves_incompatible_output_and_reports_why(monkeypatch, tmp_path, capsys):
    out = tmp_path / "results"
    run = risk_record("complete", {"issues": [], "questions": None}, ("extract",))
    args = cli_args("run", out)
    args[args.index("--scenario") + 1] = "acceptance_builder.draft_v1"
    args.extend(["--suite", "draft-risks", "--family", "complete"])
    responses = [
        {"guest_id": "guest-1"},
        {"scenario_session_id": run["session_id"], "job_id": "job-1"},
        {"status": "completed", "result_artifact_id": run["result_id"]},
        {"output": run["output"]},
    ]
    request = Mock(side_effect=responses)
    monkeypatch.setattr(evaluation, "_request", request)
    monkeypatch.setattr(evaluation, "_docker", Mock(side_effect=[
        "{}", json.dumps(run["ledger"]), "{}",
    ]))
    monkeypatch.setattr(evaluation, "_git_state", lambda: {})
    monkeypatch.setattr(sys, "argv", args)

    assert evaluation.main() == 1
    assert request.call_count == len(responses)
    assert "ERROR" in capsys.readouterr().out
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    first, *remaining = manifest["runs"]
    saved = json.loads((out / f"{first}.json").read_text(encoding="utf-8"))
    assert saved["output"] == run["output"]
    assert "type at $.questions" in saved["evidence_error"]
    monkeypatch.setattr(sys, "argv", cli_args("report", out))
    assert evaluation.main() == 1
    assert capsys.readouterr().out.splitlines() == [
        f"{first}: FAIL ({saved['evidence_error']})",
        *(f"{key}: PENDING" for key in remaining),
    ]


def test_report_can_read_partial_collection_without_a_review_sheet(monkeypatch, tmp_path, capsys):
    corrupt = risk_record("complete", {"issues": [], "questions": None}, ("extract",))
    valid = risk_record(
        "complete", {"issues": [], "questions": []}, ("extract", "detect_issues"), attempt=2
    )
    corrupt_key, valid_key = write_report_inputs(tmp_path, corrupt, valid)
    for key in (corrupt_key, valid_key):
        (tmp_path / f"{key}.review.json").unlink()
    monkeypatch.setattr(sys, "argv", cli_args("report", tmp_path))
    assert evaluation.main() == 1
    assert capsys.readouterr().out.splitlines() == [
        f"{corrupt_key}: FAIL (acceptance_builder.draft_v1 output violates type at $.questions)",
        f"{valid_key}: PENDING",
    ]


@pytest.fixture(scope="module", params=[4, 5])
def reviewed_drafts(request):
    path = (
        ROOT
        / f"tests/fixtures/acceptance_builder_eval/any-894-review-{request.param}-live.evidence.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))["runs"]


def test_reviewed_draft_matrix_matches_the_current_cases_and_rubric(reviewed_drafts):
    cases = {case["id"]: case for case in evaluation.draft_risk_cases()}
    records = [run["record"] for run in reviewed_drafts]
    expected = {(key, n) for key in cases for n in (1, 2, 3)}
    assert {(r["case"]["id"], r["attempt"]) for r in records} == expected
    assert len({r["session_id"] for r in records}) == len(records) == len(expected)
    for run in reviewed_drafts:
        record = run["record"]
        assert record["case"] == cases[record["case"]["id"]]
        review = run["review"]
        assert evaluation.review_status(record, review) == "PASS"
        if record["case"]["family"] == "contradiction":
            for quote in (None, "Which language is mentioned here?"):
                assert (
                    evaluation.review_status(record, {**review, "language_question": quote})
                    == "PENDING"
                )
            old_sheet = {k: v for k, v in review.items() if k != "language_question"}
            assert evaluation.review_status(record, {**old_sheet, "notes": ""}) == "PENDING"


def test_feasibility_report_requires_the_reviewed_linked_question(reviewed_drafts):
    run = next(row for row in reviewed_drafts if row["record"]["case"]["family"] == "feasibility")
    record, review = run["record"], run["review"]
    for quote in (
        None,
        "Is delivery tomorrow the priority?",
        record["output"]["questions"][1]["question"],
    ):
        assert evaluation.review_status(record, {**review, "scope_question": quote}) == "PENDING"
    for changed in ("question", "criteria"):
        altered = deepcopy(record)
        if changed == "question":
            altered["output"]["questions"][0]["question"] = "Is delivery tomorrow the priority?"
        else:
            altered["case"]["criteria"][0] += " Changed."
        with pytest.raises(ValueError, match="does not belong"):
            evaluation.review_status(altered, review)
