"""Update evidence cannot become accepted from successful backend output alone."""

import hashlib
import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/agent"))
spec = importlib.util.spec_from_file_location(
    "client_update_writer_eval", ROOT / "scripts/agent/client_update_writer_eval.py"
)
eval_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eval_module)


@pytest.fixture(autouse=True)
def windows_default_text_encoding(monkeypatch):
    # Exercise Windows' legacy default on every host; UTF-8 files must be explicit.
    original_open = Path.open

    def legacy_open(path, mode="r", buffering=-1, encoding=None, errors=None, newline=None):
        if "b" not in mode and encoding in (None, "locale"):
            encoding = "cp1252"
        return original_open(path, mode, buffering, encoding, errors, newline)

    monkeypatch.setattr(Path, "open", legacy_open)


def record():
    return {
        "origin": {"ui_outcome": "result", "ui_latency_ms": 1000},
        "model": "openai/gpt-6-luna",
        "output": {"text": "Done.", "call_to_action": "Send photos."},
        "visible_text": "Done.\n\nSend photos.",
        "reasoning_effort": "medium",
        "provider_calls": [{"model": "gpt-6-luna", "status": "succeeded",
                            "metadata": {"reasoning_effort": "medium"}}],
    }


def test_ui_error_fails_even_after_backend_success(tmp_path):
    run = record()
    run["origin"]["ui_outcome"] = "error"
    assert eval_module.evidence_status(run, tmp_path)[0] == "FAIL"


def test_success_stays_pending_for_human(tmp_path):
    with patch.object(eval_module, "evidence_problems", return_value=[]):
        assert eval_module.evidence_status(record(), tmp_path) == (
            "PENDING",
            ["human semantic review required"],
        )


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"provider_calls": []}, "provider ledger missing"),
        (
            {"provider_calls": [{"model": "gpt-6.1-terra", "status": "succeeded"}]},
            "provider model mismatch",
        ),
        ({"output": None}, "canonical output missing"),
        ({"visible_text": "Done."}, "visible text differs"),
    ],
)
def test_incomplete_or_mismatched_evidence_stays_pending(tmp_path, change, reason):
    with patch.object(eval_module, "evidence_problems", return_value=[]):
        status, problems = eval_module.evidence_status({**record(), **change}, tmp_path)
    assert status == "PENDING"
    assert any(reason in problem for problem in problems)


def test_missing_trace_is_not_accepted(tmp_path):
    assert "browser artifact missing" in eval_module.evidence_status(record(), tmp_path)[1]


def test_frozen_matrix_preserves_originals():
    suite = json.loads(eval_module.FIXTURE.read_text(encoding="utf-8"))
    expected_cases = 12
    expected_attempts = 360
    assert len(suite["cases"]) == expected_cases
    assert (
        len(suite["models"]) * len(suite["reasoning"]) * len(suite["cases"]) * suite["repeats"]
        == expected_attempts
    )
    original_hashes = {
        "U01-ru": "a72d8c15b28398898483d20a2acb7b7614026835e3ec1a2e8d014312ecfcb9f2",
        "U03-ru": "e5b1a6039601b239bc4b9f6ebcdeebca02b30a44b92a5e06996963dcdd140728",
        "U04-en": "f4c7aebeb6bf6fc4ac2f8dfecab65231801e017060c3025302d22ebb1fb03796",
        "U05-ru": "4ec2424b5e464cd30c522ff9c57755f52301442acb83813af1b54503b192f71d",
    }
    for case in suite["cases"]:
        if case["id"] in {"U01-ru", "U03-ru", "U04-en", "U05-ru"}:
            assert (
                hashlib.sha256(case["progress_notes"].encode()).hexdigest()
                == original_hashes[case["id"]]
            )


def test_ledger_rejects_invalid_session_before_docker():
    with patch.object(eval_module, "_docker") as docker:
        with pytest.raises(ValueError, match="invalid scenario"):
            eval_module.provider_calls("local", "session'; drop table calls; --")
        docker.assert_not_called()


def test_ledger_accepts_platform_identifier():
    with patch.object(eval_module, "_docker", return_value="[]") as docker:
        assert eval_module.provider_calls("local", "scenario_session_123_abc") == []
        assert "scenario_session_123_abc" in docker.call_args.args[-1]


@pytest.mark.parametrize(
    "project",
    ["", "--help", "--privileged", "-local", "Local", "local name", "local\n", "local;id"],
)
def test_write_router_rejects_invalid_project_before_any_docker_call(project):
    with (
        patch.object(eval_module.subprocess, "run") as run,
        patch.object(eval_module, "_docker") as readback,
    ):
        with pytest.raises(ValueError, match="invalid Compose project name"):
            eval_module.write_router(project, "model_list: []")
        run.assert_not_called()
        readback.assert_not_called()


def test_write_router_separates_options_and_preserves_stdin_restart_and_readback():
    project = "anytoolai-e986bbcb"
    container = f"{project}-platform-worker-1"
    content = "model_list: []\n# Привет; $(not-a-command)\n"
    with (
        patch.object(eval_module.subprocess, "run") as run,
        patch.object(eval_module, "_docker", return_value=content) as readback,
    ):
        eval_module.write_router(project, content)
    write, restart = run.call_args_list
    assert write.args[0][:9] == [
        "docker", "exec", "--user", "root", "-i", "--", container, "python", "-c"
    ]
    assert write.args[0][-1] == eval_module.ROUTER
    assert content not in write.args[0]
    assert write.kwargs == {
        "input": content, "text": True, "encoding": "utf-8", "check": True, "capture_output": True
    }
    assert restart.args[0] == ["docker", "restart", "--", container]
    assert restart.kwargs == {
        "check": True,
        "capture_output": True,
        "timeout": eval_module.WORKER_RESTART_TIMEOUT_SECONDS,
    }
    readback.assert_called_once_with(project, "platform-worker", "cat", eval_module.ROUTER)


def test_write_router_still_rejects_readback_mismatch():
    with (
        patch.object(eval_module.subprocess, "run"),
        patch.object(eval_module, "_docker", return_value="different content"),
        pytest.raises(RuntimeError, match="worker router readback mismatch"),
    ):
        eval_module.write_router("local", "model_list: []")


def test_write_router_uses_the_parsed_project_for_write_restart_and_readback():
    with (
        patch.object(eval_module, "_parse_compose_project", return_value="parsed-project") as parse,
        patch.object(eval_module.subprocess, "run") as run,
        patch.object(eval_module, "_docker", return_value="content") as readback,
    ):
        eval_module.write_router("original-project", "content")
    parse.assert_called_once_with("original-project")
    write, restart = run.call_args_list
    assert write.args[0][6] == "parsed-project-platform-worker-1"
    assert restart.args[0] == ["docker", "restart", "--", "parsed-project-platform-worker-1"]
    readback.assert_called_once_with("parsed-project", "platform-worker", "cat", eval_module.ROUTER)


report_spec = importlib.util.spec_from_file_location(
    "client_update_writer_eval_report", ROOT / "scripts/agent/client_update_writer_eval_report.py"
)
report_module = importlib.util.module_from_spec(report_spec)
report_spec.loader.exec_module(report_module)
review_module = importlib.import_module("client_update_writer_review")


def reviewed_run():
    run = {
        "input": {"criteria": ["Preserves readiness."]},
        "output": {"text": "Still in progress."},
    }
    run.update(
        {
            "input_sha256": eval_module.digest(run["input"]),
            "output_sha256": eval_module.digest(run["output"]),
        }
    )
    verdict = {
        **run,
        "criteria_sha256": eval_module.digest(run["input"]["criteria"]),
        "reviewer": "human-reviewer",
        "critical_error": False,
        "answers": [
            {
                "question": "Preserves readiness.",
                "decision": "yes",
                "quote": "Still in progress.",
                "reason": "No completion claim.",
            }
        ],
    }
    return run, verdict


def test_human_decision_is_bound_to_input_output_and_criteria():
    run, verdict = reviewed_run()
    assert report_module.human_status(run, verdict) == ("PASS", False)
    for field in ("input_sha256", "output_sha256", "criteria_sha256"):
        assert report_module.human_status(run, {**verdict, field: "stale"}) == ("PENDING", False)
    verdict["answers"][0]["question"] = "Different question."
    assert report_module.human_status(run, verdict) == ("PENDING", False)


def test_unconfirmed_unknown_and_critical_decisions():
    run, verdict = reviewed_run()
    for reviewer in (None, "", "agent"):
        assert report_module.human_status(run, {**verdict, "reviewer": reviewer})[0] == "PENDING"
    verdict["answers"][0]["decision"] = "unknown"
    assert report_module.human_status(run, verdict)[0] == "PENDING"
    verdict["critical_error"] = True
    assert report_module.human_status(run, verdict) == ("FAIL", True)


def test_report_validates_saved_output_against_hash():
    run, _ = reviewed_run()
    run.update(
        {
            "case": "U01-en",
            "attempt": 1,
            "model": "openai/gpt-6-luna",
            "reasoning_effort": "medium",
            "prompt_sha256": "fixed",
        }
    )
    case = {"id": "U01-en", **run["input"]}
    run["input"] = case
    run["input_sha256"] = eval_module.digest(case)
    suite = {"cases": [case]}
    manifest = {
        "suite": suite,
        "suite_sha256": eval_module.digest(suite),
        "model": run["model"],
        "reasoning_effort": "medium",
        "prompt_sha256": "fixed",
    }
    report_module.validate_runs(manifest, [run])
    run["output"]["text"] = "Changed after review."
    with pytest.raises(ValueError, match="output digest"):
        report_module.validate_runs(manifest, [run])


def test_empty_report_cannot_pass(tmp_path):
    with pytest.raises(ValueError, match="no experiment manifests"):
        report_module.summarize(tmp_path)


def test_missing_configuration_keeps_overall_pending():
    suite = {"models": ["openai/gpt-6-luna"], "reasoning": ["medium", "high"]}
    result = report_module.overall_summary(
        {"luna-medium": {"status": "PASS"}}, suite, {("openai/gpt-6-luna", "medium")}
    )
    assert result["status"] == "PENDING"
    assert result["missing_configurations"] == [
        {"model": "openai/gpt-6-luna", "reasoning_effort": "high"}
    ]


def test_termination_triggers_normal_unwinding():
    with pytest.raises(KeyboardInterrupt, match="restoring worker router"):
        eval_module.interrupt_collection(None, None)


@pytest.mark.parametrize("repeats", [5, None])
def test_orphaned_journal_blocks_retry_and_restores_router(tmp_path, repeats):
    baseline = "model_list:\n  - litellm_params:\n      model: openai/gpt-6-luna\n"
    (tmp_path / "U01-ru-1.zip.journal.json").write_text('{"phase":"started"}', encoding="utf-8")
    args = SimpleNamespace(
        suite=eval_module.FIXTURE,
        model="openai/gpt-6-luna",
        reasoning="medium",
        repeats=repeats,
        out=tmp_path,
        resume=True,
        project="local",
        max_attempts=1,
    )
    with (
        patch.object(
            eval_module,
            "_docker",
            side_effect=lambda *a: "prompt" if a[-1].endswith(".md") else baseline,
        ),
        patch.object(
            eval_module, "_git_state",
            return_value={"git_sha": "revision-A", "git_dirty": False},
        ),
        patch.object(eval_module, "write_router") as write,
        patch.object(eval_module.subprocess, "run") as browser,
    ):
        with pytest.raises(RuntimeError, match="orphaned browser evidence"):
            eval_module.collect(args)
        browser.assert_not_called()
        assert write.call_args.args == ("local", baseline)


def test_diagnostic_costs_count_but_unknown_cost_prevents_cost_per_usable():
    call = {"input_tokens": 10, "output_tokens": 2, "estimated_cost": 0.01}
    run = {"origin": {"ui_latency_ms": 1000}, "provider_calls": [call]}
    diagnostic = {"provider_calls": [{**call, "estimated_cost": "NaN"}]}
    groups = {"U01-en": {"usable": 1}}
    metrics = report_module.measured_metrics([run], [diagnostic], groups)
    assert metrics["calls_without_cost"] == 1
    assert metrics["cost_per_usable"] is None
    assert metrics["ledger_estimated_cost"] == call["estimated_cost"]
    diagnostic["provider_calls"][0]["estimated_cost"] = 0.02
    metrics = report_module.measured_metrics([run], [diagnostic], groups)
    assert metrics["cost_per_usable"] == pytest.approx(0.03)


def test_configuration_outside_frozen_matrix_is_rejected_before_collecting():
    with pytest.raises(ValueError, match="outside frozen matrix"):
        eval_module.collect(
            SimpleNamespace(suite=eval_module.FIXTURE, model="openai/unknown", reasoning="medium")
        )


def review_directory(tmp_path, *, questions=None):
    directory = tmp_path / "screening"
    series = directory / "sol-medium"
    series.mkdir(parents=True)
    run, _ = reviewed_run()
    run.update(
        {
            "id": "U04-en-1",
            "case": "U04-en",
            "attempt": 1,
            "model": "openai/gpt-6.1-sol",
            "reasoning_effort": "medium",
            "prompt_sha256": "frozen-prompt",
        }
    )
    run["input"].update({"id": "U04-en", "progress_notes": "Internal complete; tests fail."})
    if questions is not None:
        run["input"]["criteria"] = questions
    run["input_sha256"] = eval_module.digest(run["input"])
    suite = {"cases": [run["input"]]}
    manifest = {
        "suite": suite,
        "suite_sha256": eval_module.digest(suite),
        **{key: run[key] for key in ("model", "reasoning_effort", "prompt_sha256")},
    }
    (series / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (series / "runs.jsonl").write_text(json.dumps(run) + "\n", encoding="utf-8")
    return directory, run


def saved_verdict(directory):
    return json.loads((directory / "verdicts.jsonl").read_text(encoding="utf-8").splitlines()[-1])


def test_interactive_review_requires_explicit_decisions_and_records_identity(tmp_path, capsys):
    directory, run = review_directory(tmp_path)
    observation = {
        "series": "screening/sol-medium",
        "run_id": run["id"],
        **review_module.verdict_hashes(run),
        "suggestion": "agent suggests yes",
        "reason": "Agent explanation",
    }
    (tmp_path / "agent-observations.json").write_text(
        json.dumps({"observations": [observation]}), encoding="utf-8"
    )
    with patch(
        "builtins.input", side_effect=["", "invalid", "n", "Readiness is misstated", "Still", "y"]
    ):
        review_module.review(directory, " Putilin ", "sol-medium")
    verdict = saved_verdict(directory)
    assert verdict["reviewer"] == "Putilin"
    assert verdict["reviewed_at"]
    assert verdict["answers"][0]["decision"] == "no"
    assert verdict["answers"][0]["reason"] == "Readiness is misstated"
    assert verdict["critical_error"] is True
    assert report_module.human_status(run, verdict) == ("FAIL", True)
    display = capsys.readouterr().out
    assert "Internal complete; tests fail." in display
    assert "Still in progress." in display
    assert "agent suggests yes" in display
    # A confirmed verdict is not requested again, even for another reviewer.
    with patch("builtins.input", side_effect=AssertionError("already reviewed")):
        review_module.review(directory, "Another reviewer")


def test_review_resumes_partial_decisions_and_does_not_auto_accept(tmp_path):
    directory, run = review_directory(tmp_path, questions=["Ready?", "Dates?"])
    with (
        patch("builtins.input", side_effect=["y", "q"]),
        pytest.raises(review_module.ReviewStopped),
    ):
        review_module.review(directory, "Putilin")
    verdict = saved_verdict(directory)
    assert verdict["answers"][0]["decision"] == "yes"
    assert verdict["answers"][1]["decision"] is None
    assert report_module.human_status(run, verdict)[0] == "PENDING"
    with patch("builtins.input", side_effect=["y", "n"]):
        review_module.review(directory, "Putilin")
    assert report_module.human_status(run, saved_verdict(directory)) == ("PASS", False)
    expected_saves = 3
    saved = (directory / "verdicts.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(saved) == expected_saves


@pytest.mark.parametrize("stale", [True, False])
def test_review_discards_stale_or_differently_attributed_partial_decisions(tmp_path, capsys, stale):
    directory, run = review_directory(tmp_path)
    old = {
        "series": "sol-medium",
        "id": run["id"],
        **review_module.verdict_hashes(run),
        "reviewer": "Putilin" if stale else "Other",
        "critical_error": None,
        "answers": [
            {"question": "Preserves readiness.", "decision": "yes", "reason": "Old", "quote": ""}
        ],
    }
    observation = {
        "series": "screening/sol-medium",
        "run_id": run["id"],
        **review_module.verdict_hashes(run),
        "output_sha256": "old-output",
        "suggestion": "STALE SUGGESTION",
        "reason": "Do not display",
    }
    if stale:
        old["input_sha256"] = "old-input"
    (directory / "verdicts.jsonl").write_text(json.dumps(old) + "\n", encoding="utf-8")
    (tmp_path / "agent-observations.json").write_text(
        json.dumps({"observations": [observation]}), encoding="utf-8"
    )
    with patch("builtins.input", side_effect=["n", "New assessment", "", "n"]):
        review_module.review(directory, "Putilin")
    assert saved_verdict(directory)["answers"][0]["reason"] == "New assessment"
    assert "STALE SUGGESTION" not in capsys.readouterr().out


def test_unknown_or_skipped_review_is_pending_and_eof_preserves_progress(tmp_path):
    directory, run = review_directory(tmp_path)
    with patch("builtins.input", side_effect=["u", "Cannot tell", "", "s"]):
        review_module.review(directory, "Putilin")
    assert report_module.human_status(run, saved_verdict(directory))[0] == "PENDING"
    with patch("builtins.input", side_effect=EOFError):
        review_module.main(["--directory", str(directory), "--reviewer", "Putilin"])
    assert saved_verdict(directory)["answers"][0]["decision"] == "unknown"


@pytest.mark.parametrize("reviewer,series", [("agent", None), (" ", None), ("Putilin", "missing")])
def test_review_rejects_invalid_identity_and_series_without_writes(tmp_path, reviewer, series):
    directory, _ = review_directory(tmp_path)
    with pytest.raises(ValueError):
        review_module.review(directory, reviewer, series)
    assert not (directory / "verdicts.jsonl").exists()


def test_review_validates_hashes_before_accepting_any_decision(tmp_path):
    directory, run = review_directory(tmp_path)
    run["output"]["text"] = "Modified after collection"
    (directory / "sol-medium/runs.jsonl").write_text(json.dumps(run) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="output digest"):
        review_module.review(directory, "Putilin")
    assert not (directory / "verdicts.jsonl").exists()


def test_collector_dispatches_offline_review_without_docker():
    with (
        patch.object(review_module, "main") as offline,
        patch.object(eval_module, "collect") as collect,
    ):
        eval_module.main(["review", "--reviewer", "Putilin", "--directory", "results"])
    offline.assert_called_once_with(["--reviewer", "Putilin", "--directory", "results"])
    collect.assert_not_called()


def experiment_manifests():
    suite = {
        "cases": [
            {
                "id": "case",
                "progress_notes": "Still in progress.",
                "criteria": ["Preserves readiness."],
            }
        ],
        "models": ["openai/gpt-6.1-sol"],
        "reasoning": ["medium", "high"],
        "repeats": 1,
        "minimum_usable": 1,
        "max_median_ui_ms": 60000,
    }
    return {
        effort: {
            "suite": deepcopy(suite),
            "model": "openai/gpt-6.1-sol",
            "reasoning_effort": effort,
            "prompt_sha256": "fixed-prompt",
        }
        for effort in suite["reasoning"]
    }


def write_report_experiment(directory, manifests):
    verdicts = []
    for series, manifest in manifests.items():
        manifest["suite_sha256"] = eval_module.digest(manifest["suite"])
        run, verdict = reviewed_run()
        run.update(
            {field: manifest[field] for field in ("model", "reasoning_effort", "prompt_sha256")}
        )
        run["input"] = manifest["suite"]["cases"][0]
        run.update(
            {
                "id": "case-1",
                "case": "case",
                "attempt": 1,
                "origin": {"ui_latency_ms": 1000},
                "provider_calls": [],
            }
        )
        run["input_sha256"] = eval_module.digest(run["input"])
        verdict.update({"series": series, "id": run["id"], **review_module.verdict_hashes(run)})
        report_module.validate_runs(manifest, [run])
        assert report_module.human_status(run, verdict) == ("PASS", False)
        path = directory / series
        path.mkdir()
        (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (path / "runs.jsonl").write_text(json.dumps(run) + "\n", encoding="utf-8")
        verdicts.append(verdict)
    (directory / "verdicts.jsonl").write_text(
        "".join(json.dumps(verdict) + "\n" for verdict in verdicts), encoding="utf-8"
    )


@pytest.fixture
def valid_report_runtime():
    # These tests exercise experiment identity; browser-proof checks have their own tests.
    with patch.object(
        report_module,
        "evidence_status",
        return_value=("PENDING", ["human semantic review required"]),
    ):
        yield


@pytest.mark.usefixtures("valid_report_runtime")
def test_report_preserves_utf8_with_legacy_default_encoding(tmp_path):
    text = "Проверка готовности: mañana."
    probe = tmp_path / "utf8.txt"
    probe.write_bytes(text.encode("utf-8"))
    with pytest.raises(UnicodeDecodeError):
        probe.read_text()
    manifests = experiment_manifests()
    for manifest in manifests.values():
        manifest["suite"]["cases"][0]["progress_notes"] = text
    write_report_experiment(tmp_path, manifests)
    # Real collector manifests contain literal Unicode rather than JSON ASCII escapes.
    for path in tmp_path.glob("*/manifest.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        path.write_bytes(json.dumps(document, ensure_ascii=False).encode("utf-8"))

    assert report_module.summarize(tmp_path)["status"] == "PASS"
    assert text in (tmp_path / "report.html").read_text(encoding="utf-8")


@pytest.mark.usefixtures("valid_report_runtime")
@pytest.mark.parametrize(
    "change",
    [
        "suite",
        "prompt",
        "duplicate",
        "unplanned_model",
        "unplanned_effort",
        "duplicate_models",
        "duplicate_efforts",
        "empty_models",
        "empty_efforts",
    ],
)
def test_report_rejects_inconsistent_experiments_without_overwriting_reports(tmp_path, change):
    manifests = experiment_manifests()
    if change == "suite":
        manifests["medium"]["suite"]["cases"][0]["progress_notes"] = "Different input."
    elif change == "prompt":
        manifests["medium"]["prompt_sha256"] = "different-prompt"
    elif change == "duplicate":
        for manifest in manifests.values():
            manifest["suite"]["reasoning"] = ["medium"]
            manifest["reasoning_effort"] = "medium"
    elif change == "unplanned_model":
        manifests["medium"]["model"] = "openai/unplanned"
    elif change == "unplanned_effort":
        manifests["medium"]["reasoning_effort"] = "unplanned"
    else:
        key = "models" if change.endswith("models") else "reasoning"
        for manifest in manifests.values():
            values = manifest["suite"][key]
            manifest["suite"][key] = values + values if change.startswith("duplicate") else []
    write_report_experiment(tmp_path, manifests)
    reports = [tmp_path / name for name in ("summary.json", "report.html", "review-template.jsonl")]
    for path in reports:
        path.write_text("previous report", encoding="utf-8")
    verdicts = (tmp_path / "verdicts.jsonl").read_bytes()
    with pytest.raises(ValueError):
        report_module.summarize(tmp_path)
    assert all(path.read_text(encoding="utf-8") == "previous report" for path in reports)
    assert (tmp_path / "verdicts.jsonl").read_bytes() == verdicts


@pytest.mark.usefixtures("valid_report_runtime")
@pytest.mark.parametrize("missing_high", [False, True])
def test_report_accepts_one_consistent_experiment_and_keeps_missing_pairs_pending(
    tmp_path, missing_high
):
    manifests = experiment_manifests()
    if missing_high:
        del manifests["high"]
    write_report_experiment(tmp_path, manifests)
    result = report_module.summarize(tmp_path)
    assert result["status"] == ("PENDING" if missing_high else "PASS")
    assert result["missing_configurations"] == (
        [{"model": "openai/gpt-6.1-sol", "reasoning_effort": "high"}] if missing_high else []
    )


def test_report_rejects_a_suite_with_a_forged_matching_digest(tmp_path):
    manifests = experiment_manifests()
    write_report_experiment(tmp_path, manifests)
    manifest = manifests["medium"]
    manifest["suite"]["cases"][0]["progress_notes"] = "Changed after hashing."
    (tmp_path / "medium/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="suite manifest digest mismatch"):
        report_module.summarize(tmp_path)


def resume_collection(tmp_path):
    suite = json.loads(eval_module.FIXTURE.read_text(encoding="utf-8"))
    baseline = {
        "model_list": [
            {
                "litellm_params": {
                    "model": "openai/gpt-6-luna",
                    "reasoning_effort": "medium",
                    "timeout": 60,
                }
            }
        ]
    }
    prompt = "fixed prompt"
    manifest = {
        "suite_sha256": eval_module.digest(suite),
        "model": "openai/gpt-6.1-sol",
        "reasoning_effort": "medium",
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "original_router": baseline,
        "git_sha": "revision-A",
        "git_dirty": False,
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    args = SimpleNamespace(
        suite=eval_module.FIXTURE,
        model=manifest["model"],
        reasoning="medium",
        repeats=None,
        out=tmp_path,
        resume=True,
        project="local",
        max_attempts=0,
    )
    return args, baseline, prompt


def test_collector_preserves_utf8_and_resumes_with_legacy_encoding(tmp_path):
    args, baseline, prompt = resume_collection(tmp_path)
    state = {"router": json.dumps(baseline)}
    (tmp_path / "manifest.json").unlink()
    args.max_attempts = 1
    args.web_url = "http://localhost:3200"
    observed = {
        "output": {"text": "Проверка готовности: mañana."},
        "session_id": "scenario_session_test",
        "ui_outcome": "result",
        "ui_latency_ms": 1000,
    }

    def browser(_command, **kwargs):
        assert kwargs["encoding"] == "utf-8"
        spec = json.loads(kwargs["input"])
        Path(spec["trace"]).write_bytes(b"trace")
        return SimpleNamespace(stdout=json.dumps(observed, ensure_ascii=False))

    with (
        patch.object(
            eval_module, "_docker",
            side_effect=lambda *a: prompt if a[-1].endswith(".md") else state["router"],
        ),
        patch.object(
            eval_module, "_git_state",
            return_value={"git_sha": "revision-A", "git_dirty": False},
        ),
        patch.object(
            eval_module, "write_router",
            side_effect=lambda _project, content: state.update(router=content),
        ),
        patch.object(eval_module, "provider_calls", return_value=[]),
        patch.object(eval_module, "evidence_status", return_value=("PENDING", [])),
        patch.object(eval_module.subprocess, "run", side_effect=browser) as submit,
    ):
        eval_module.collect(args)
        args.max_attempts = 0
        eval_module.collect(args)
        submit.assert_called_once()
    [run] = eval_module.read_jsonl(tmp_path / "runs.jsonl")
    assert run["output"] == observed["output"]
    raw = json.loads((tmp_path / f"{run['id']}.browser.json").read_text(encoding="utf-8"))
    assert raw == observed


@pytest.mark.parametrize(
    "changed_field,value", [("model", "openai/gpt-6.1-terra"), ("timeout", 120)]
)
def test_resume_rejects_live_router_drift_before_writes_or_submissions(
    tmp_path, changed_field, value
):
    args, baseline, prompt = resume_collection(tmp_path)
    current = deepcopy(baseline)
    current["model_list"][0]["litellm_params"][changed_field] = value
    manifest_before = (tmp_path / "manifest.json").read_bytes()
    with (
        patch.object(
            eval_module,
            "_docker",
            side_effect=lambda *a: prompt if a[-1].endswith(".md") else json.dumps(current),
        ),
        patch.object(
            eval_module, "_git_state",
            return_value={"git_sha": "revision-A", "git_dirty": False},
        ),
        patch.object(eval_module, "write_router") as write,
        patch.object(eval_module.subprocess, "run") as browser,
    ):
        with pytest.raises(ValueError, match="resume manifest mismatch: original_router"):
            eval_module.collect(args)
        write.assert_not_called()
        browser.assert_not_called()
    assert (tmp_path / "manifest.json").read_bytes() == manifest_before
    assert not (tmp_path / "router-restored.txt").exists()


@pytest.mark.parametrize("reformat", [False, True])
def test_resume_accepts_equivalent_baseline_and_restores_actual_entry_text(tmp_path, reformat):
    args, baseline, prompt = resume_collection(tmp_path)
    original = (
        "# Current operator comment\n" + json.dumps(baseline, indent=2) + "\n"
        if reformat
        else eval_module.yaml.safe_dump(baseline)
    )
    with (
        patch.object(
            eval_module,
            "_docker",
            side_effect=lambda *a: prompt if a[-1].endswith(".md") else original,
        ),
        patch.object(
            eval_module, "_git_state",
            return_value={"git_sha": "revision-A", "git_dirty": False},
        ),
        patch.object(eval_module, "write_router") as write,
        patch.object(eval_module.subprocess, "run") as browser,
    ):
        eval_module.collect(args)
        browser.assert_not_called()
    selected, restored = write.call_args_list
    selected_params = eval_module.yaml.safe_load(selected.args[1])["model_list"][0][
        "litellm_params"
    ]
    assert selected_params["timeout"] == baseline["model_list"][0]["litellm_params"]["timeout"]
    assert "openai/gpt-6.1-sol" in selected.args[1]
    assert restored.args == ("local", original)


def test_resume_still_restores_entry_baseline_after_orphaned_attempt(tmp_path):
    args, baseline, prompt = resume_collection(tmp_path)
    args.max_attempts = 1
    first_case = json.loads(args.suite.read_text(encoding="utf-8"))["cases"][0]["id"]
    (tmp_path / f"{first_case}-1.zip.journal.json").write_text(
        '{"phase":"started"}', encoding="utf-8"
    )
    original = "# Current baseline\n" + json.dumps(baseline)
    with (
        patch.object(
            eval_module,
            "_docker",
            side_effect=lambda *a: prompt if a[-1].endswith(".md") else original,
        ),
        patch.object(
            eval_module, "_git_state",
            return_value={"git_sha": "revision-A", "git_dirty": False},
        ),
        patch.object(eval_module, "write_router") as write,
        patch.object(eval_module.subprocess, "run") as browser,
        pytest.raises(RuntimeError, match="orphaned browser evidence"),
    ):
        eval_module.collect(args)
    browser.assert_not_called()
    assert write.call_args.args == ("local", original)


def test_review_reasks_critical_error_after_resolving_unknown(tmp_path):
    directory, run = review_directory(tmp_path)
    with patch("builtins.input", side_effect=["u", "Need another look", "", "n"]):
        review_module.review(directory, "Putilin")
    with patch("builtins.input", side_effect=["n", "Found an omission", "", "y"]):
        review_module.review(directory, "Putilin")
    assert report_module.human_status(run, saved_verdict(directory)) == ("FAIL", True)


def test_corrupt_partial_review_is_rejected_without_overwriting(tmp_path):
    directory, _ = review_directory(tmp_path)
    with (
        patch("builtins.input", side_effect=["y", "q"]),
        pytest.raises(review_module.ReviewStopped),
    ):
        review_module.review(directory, "Putilin")
    verdict = saved_verdict(directory)
    verdict["answers"] = []
    path = directory / "verdicts.jsonl"
    path.write_text(json.dumps(verdict) + "\n", encoding="utf-8")
    original = path.read_bytes()
    with pytest.raises(ValueError, match="Повреждены"):
        review_module.review(directory, "Putilin")
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "recorded,expected", [("medium", "FAIL"), (None, "PENDING"), ("high", "PENDING")]
)
def test_effort_is_verified_on_every_physical_attempt(tmp_path, recorded, expected):
    run = record()
    run["reasoning_effort"] = "high"
    call = run["provider_calls"][0]
    call["metadata"] = {"reasoning_effort": "high"}
    run["provider_calls"].append({**call, "metadata": {"reasoning_effort": recorded}})
    with patch.object(eval_module, "evidence_problems", return_value=[]):
        status, problems = eval_module.evidence_status(run, tmp_path)
    assert status == expected
    assert (problems == ["human semantic review required"]) == (recorded == "high")


def test_provider_query_preserves_effort_metadata():
    call = {"metadata": {"reasoning_effort": "high"}}
    with patch.object(eval_module, "_docker", return_value=json.dumps([call])) as docker:
        assert eval_module.provider_calls("local", "scenario_session_test") == [call]
    assert "metadata" in docker.call_args.args[-1]


@pytest.mark.parametrize(
    "recorded,expected", [("medium", "FAIL"), (None, "PENDING"), ("high", "PASS")]
)
def test_human_pass_cannot_override_effort_evidence(tmp_path, recorded, expected):
    manifest = experiment_manifests()["high"]
    manifest["suite"]["reasoning"] = ["high"]
    write_report_experiment(tmp_path, {"high": manifest})
    path = tmp_path / "high/runs.jsonl"
    run = json.loads(path.read_text(encoding="utf-8"))
    run["origin"]["ui_outcome"] = "result"
    run["visible_text"] = run["output"]["text"]
    run["provider_calls"] = [{
        "model": run["model"], "status": "succeeded", "metadata": {"reasoning_effort": recorded},
        "input_tokens": 1, "output_tokens": 1, "estimated_cost": 0,
    }]
    path.write_text(json.dumps(run) + "\n", encoding="utf-8")
    with (
        patch.object(eval_module, "evidence_problems", return_value=[]),
        patch.object(report_module, "evidence_status", side_effect=eval_module.evidence_status),
    ):
        assert report_module.summarize(tmp_path)["status"] == expected


@pytest.mark.parametrize("revision", [
    {"git_sha": "revision-B", "git_dirty": False},
    {"git_sha": "revision-A", "git_dirty": True},
    {"git_sha": None, "git_dirty": False},
])
def test_resume_rejects_unverifiable_or_changed_revision_before_mutation(tmp_path, revision):
    args, baseline, prompt = resume_collection(tmp_path)
    before = (tmp_path / "manifest.json").read_bytes()
    with (
        patch.object(eval_module, "_git_state", return_value=revision),
        patch.object(
            eval_module, "_docker",
            side_effect=lambda *a: prompt if a[-1].endswith(".md") else json.dumps(baseline),
        ),
        patch.object(eval_module, "write_router") as write,
        patch.object(eval_module.subprocess, "run") as submit,
        pytest.raises(ValueError, match="revision|git_sha"),
    ):
        eval_module.collect(args)
    write.assert_not_called()
    submit.assert_not_called()
    assert (tmp_path / "manifest.json").read_bytes() == before


@pytest.mark.parametrize("change", [
    {"cases": []}, {"cases": [{"id": "case", "criteria": []}]},
    {"cases": [{"id": "", "criteria": ["Ready?"]}]},
    {"cases": [{"id": "case", "criteria": [" "]}]},
    {"cases": [{"id": "same", "criteria": ["Ready?"]}] * 2},
    {"repeats": 0}, {"repeats": 0, "minimum_usable": 0},
    {"repeats": -1}, {"repeats": True}, {"repeats": 1.5},
    {"minimum_usable": 0}, {"minimum_usable": 2}, {"minimum_usable": True},
])
def test_invalid_suite_is_rejected_before_collection_or_report_writes(tmp_path, change):
    manifest = experiment_manifests()["medium"]
    manifest["suite"].update(change)
    manifest["suite_sha256"] = eval_module.digest(manifest["suite"])
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps(manifest["suite"]), encoding="utf-8")
    with (
        patch.object(eval_module, "_docker") as docker,
        pytest.raises(ValueError, match="suite"),
    ):
        eval_module.collect(SimpleNamespace(suite=suite_path))
    docker.assert_not_called()
    series = tmp_path / "medium"
    series.mkdir()
    (series / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    report = tmp_path / "report.html"
    report.write_text("previous report", encoding="utf-8")
    with pytest.raises(ValueError, match="suite"):
        report_module.summarize(tmp_path)
    assert report.read_text(encoding="utf-8") == "previous report"


@pytest.mark.parametrize("missing", ["git_sha", "git_dirty"])
def test_resume_rejects_legacy_manifest_without_revision(tmp_path, missing):
    args, baseline, prompt = resume_collection(tmp_path)
    path = tmp_path / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    del manifest[missing]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with (
        patch.object(eval_module, "_git_state", return_value={
            "git_sha": "revision-A", "git_dirty": False,
        }),
        patch.object(eval_module, "_docker", side_effect=lambda *a:
                     prompt if a[-1].endswith(".md") else json.dumps(baseline)),
        patch.object(eval_module, "write_router") as write,
        pytest.raises(ValueError, match=missing),
    ):
        eval_module.collect(args)
    write.assert_not_called()
