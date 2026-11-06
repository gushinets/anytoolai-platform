"""Update evidence cannot become accepted from successful backend output alone."""

import hashlib
import importlib.util
import json
import sys
import zipfile
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


def test_complete_technical_proof_is_separate_from_human_review(tmp_path):
    with patch.object(eval_module, "evidence_problems", return_value=[]):
        assert eval_module.evidence_status(record(), tmp_path) == (
            "PASS",
            [],
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
        "git_sha": "a" * 40,
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
            "id": "U01-en-1",
            "attempt": 1,
            "model": "openai/gpt-6-luna",
            "reasoning_effort": "medium",
            "prompt_sha256": "fixed",
        }
    )
    case = {"id": "U01-en", **run["input"]}
    run["input"] = case
    run["input_sha256"] = eval_module.digest(case)
    suite = {"cases": [case], "repeats": 1}
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
            return_value={"git_sha": "a" * 40, "git_dirty": False},
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
    run = {"origin": {"ui_outcome": "result", "ui_latency_ms": 1000}, "provider_calls": [call]}
    diagnostic = {"provider_calls": [{**call, "estimated_cost": "NaN"}]}
    groups = {"U01-en": {"usable": 1}}
    metrics = report_module.measured_metrics([run], [diagnostic], groups, [run])
    assert metrics["calls_without_cost"] == 1
    assert metrics["cost_per_usable"] is None
    assert metrics["ledger_estimated_cost"] == call["estimated_cost"]
    diagnostic["provider_calls"][0]["estimated_cost"] = 0.02
    metrics = report_module.measured_metrics([run], [diagnostic], groups, [run])
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
            "prompt_sha256": "e" * 64,
        }
    )
    run["input"].update({"id": "U04-en", "progress_notes": "Internal complete; tests fail."})
    if questions is not None:
        run["input"]["criteria"] = questions
    run["input_sha256"] = eval_module.digest(run["input"])
    suite = {"cases": [run["input"]], "repeats": 1}
    manifest = {
        "suite": suite,
        "suite_sha256": eval_module.digest(suite),
        **{key: run[key] for key in ("model", "reasoning_effort", "prompt_sha256", "git_sha")},
        "git_dirty": False,
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
    manifests = {
        effort: {
            "suite": deepcopy(suite),
            "model": "openai/gpt-6.1-sol",
            "reasoning_effort": effort,
            "prompt_sha256": "f" * 64,
            "git_sha": "a" * 40,
            "git_dirty": False,
        }
        for effort in suite["reasoning"]
    }

    for manifest in manifests.values():
        manifest["original_router"] = {"model_list": [{"litellm_params": {
            "model": "openai/gpt-6-luna", "timeout": 60,
        }}]}
        manifest["router"] = eval_module.selected_router(
            manifest["original_router"], manifest["model"], manifest["reasoning_effort"]
        )
    return manifests


def write_report_experiment(directory, manifests):
    verdicts = []
    for series, manifest in manifests.items():
        manifest["suite_sha256"] = eval_module.digest(manifest["suite"])
        run, verdict = reviewed_run()
        run.update(
            {field: manifest[field]
             for field in ("model", "reasoning_effort", "prompt_sha256", "git_sha")}
        )
        run["input"] = manifest["suite"]["cases"][0]
        run.update(
            {
                "id": "case-1",
                "case": "case",
                "attempt": 1,
                "origin": {"ui_outcome": "result", "ui_latency_ms": 1000},
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
        return_value=("PASS", []),
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
        "git_sha": "a" * 40,
        "git_dirty": False,
    }
    manifest["suite"] = suite
    manifest["router"] = eval_module.selected_router(
        baseline, manifest["model"], manifest["reasoning_effort"]
    )
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
            return_value={"git_sha": "a" * 40, "git_dirty": False},
        ),
        patch.object(
            eval_module, "write_router",
            side_effect=lambda _project, content: state.update(router=content),
        ),
        patch.object(eval_module, "provider_calls", return_value=[]),
        patch.object(eval_module, "evidence_status", return_value=("PASS", [])),
        patch.object(eval_module.subprocess, "run", side_effect=browser) as submit,
    ):
        eval_module.collect(args)
        args.max_attempts = 0
        eval_module.collect(args)
        submit.assert_called_once()
    [run] = eval_module.read_jsonl(tmp_path / "runs.jsonl")
    assert run["output"] == observed["output"]
    assert run["status"] == "PENDING"
    assert run["review_needed"] == ["human semantic review required"]
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
            return_value={"git_sha": "a" * 40, "git_dirty": False},
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
            return_value={"git_sha": "a" * 40, "git_dirty": False},
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
            return_value={"git_sha": "a" * 40, "git_dirty": False},
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
    "recorded,expected", [("medium", "FAIL"), (None, "PENDING"), ("high", "PASS")]
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
    assert (problems == []) == (recorded == "high")


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
    {"git_sha": "b" * 40, "git_dirty": False},
    {"git_sha": "a" * 40, "git_dirty": True},
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
            "git_sha": "a" * 40, "git_dirty": False,
        }),
        patch.object(eval_module, "_docker", side_effect=lambda *a:
                     prompt if a[-1].endswith(".md") else json.dumps(baseline)),
        patch.object(eval_module, "write_router") as write,
        pytest.raises(ValueError, match=missing),
    ):
        eval_module.collect(args)
    write.assert_not_called()


API_FAILURES = [
    "json-error", "html-start", "plain-start", "body-start",
    "html-result", "plain-result", "body-result",
]
DRIVER_FAILURES = [*API_FAILURES, "screenshot", "trace", "close", "journal"]


def driver_result(spec, failure, run_process):
    harness = ROOT / "tests/fixtures/client_update_writer_eval/driver_harness.mjs"
    completed = run_process(
        ["node", str(harness)],
        input=json.dumps({**spec, "failure": failure}),
        encoding="utf-8", capture_output=True, check=True, timeout=20,
    )
    return json.loads(completed.stdout)


@pytest.mark.parametrize("failure", ["success", *DRIVER_FAILURES])
def test_live_driver_finalizes_each_attempt_independently(tmp_path, failure):
    trace = tmp_path / "attempt.zip"
    result = driver_result({
        "trace": str(trace), "language": "en", "tone": "warm",
        "progress_notes": "Done", "web_url": "http://web",
    }, failure, eval_module.subprocess.run)
    record, calls = result["record"], result["calls"]
    assert record["ui_outcome"] == ("error" if failure in API_FAILURES else "result")
    assert calls.count("submit") == 1
    assert calls.count("screenshot") == calls.count("trace") == calls.count("close") == 1
    assert calls[-1] == "complete"
    assert trace.exists() == (failure != "trace")
    if failure != "journal":
        journal = json.loads(Path(str(trace) + ".journal.json").read_text(encoding="utf-8"))
        assert journal == {**record, "phase": "complete"}
    else:
        assert "journal" in record["diagnostic_errors"]
    if failure.startswith(("html-", "plain-", "body-")):
        kind = failure.split("-")[1]
        assert record[kind + "_status"] == (200 if failure.startswith("body-") else 502)
        assert kind + "_response" in record["diagnostic_errors"]


@pytest.mark.parametrize("failure", DRIVER_FAILURES)
def test_driver_failures_are_persisted_and_stop_collection(tmp_path, failure):
    args, baseline, prompt = resume_collection(tmp_path)
    args.max_attempts = 2
    args.web_url = "http://web"
    state = {"router": json.dumps(baseline)}
    run_process = eval_module.subprocess.run

    def browser(_command, **kwargs):
        result = driver_result(json.loads(kwargs["input"]), failure, run_process)
        return SimpleNamespace(stdout=json.dumps(result["record"]))

    with (
        patch.object(eval_module, "_git_state", return_value={
            "git_sha": "a" * 40, "git_dirty": False,
        }),
        patch.object(eval_module, "_docker", side_effect=lambda *a:
                     prompt if a[-1].endswith(".md") else state["router"]),
        patch.object(eval_module, "write_router", side_effect=lambda _p, content:
                     state.update(router=content)) as write,
        patch.object(eval_module, "provider_calls", return_value=[]),
        patch.object(eval_module.subprocess, "run", side_effect=browser) as submit,
        pytest.raises(RuntimeError, match=(
            "UI failed; evidence retained" if failure in API_FAILURES
            else "Evidence collection failed"
        )),
    ):
        eval_module.collect(args)
    submit.assert_called_once()
    assert write.call_args.args == ("local", json.dumps(baseline))
    [run] = eval_module.read_jsonl(tmp_path / "runs.jsonl")
    assert run["status"] == ("FAIL" if failure in API_FAILURES else "PENDING")
    assert run["origin"]["ui_outcome"] == ("error" if failure in API_FAILURES else "result")
    assert (run["origin"]["trace_sha256"] is None) == (failure == "trace")
    if failure == "trace":
        assert run["trace_error"]


@pytest.mark.parametrize("error", [FileNotFoundError, PermissionError])
def test_unreadable_trace_preserves_the_observed_ui_success(tmp_path, error):
    observed = {"ui_outcome": "result", "ui_latency_ms": 1000}
    with patch.object(Path, "read_bytes", side_effect=error("trace unavailable")):
        origin = eval_module.trace_origin(observed, tmp_path / "attempt.zip")
    assert observed["ui_outcome"] == origin["ui_outcome"] == "result"
    assert origin["trace_sha256"] is None
    assert observed["trace_error"] == "trace unavailable"


@pytest.mark.parametrize("failure", [
    eval_module.subprocess.CalledProcessError(1, ["node"]),
    eval_module.subprocess.TimeoutExpired(["node"], 180),
])
def test_unknown_process_outcome_restores_router_and_blocks_blind_retry(tmp_path, failure):
    args, baseline, prompt = resume_collection(tmp_path)
    args.max_attempts = 2
    args.web_url = "http://web"

    def crash(_command, **kwargs):
        trace = json.loads(kwargs["input"])["trace"]
        Path(trace + ".journal.json").write_text('{"phase":"submitting"}', encoding="utf-8")
        raise failure

    with (
        patch.object(eval_module, "_git_state", return_value={
            "git_sha": "a" * 40, "git_dirty": False,
        }),
        patch.object(eval_module, "_docker", side_effect=lambda *a:
                     prompt if a[-1].endswith(".md") else json.dumps(baseline)),
        patch.object(eval_module, "write_router") as write,
        patch.object(eval_module.subprocess, "run", side_effect=crash) as submit,
    ):
        with pytest.raises(type(failure)):
            eval_module.collect(args)
        with pytest.raises(RuntimeError, match="orphaned browser evidence"):
            eval_module.collect(args)
    submit.assert_called_once()
    assert write.call_args.args == ("local", json.dumps(baseline))
    assert not (tmp_path / "runs.jsonl").exists()


def change_revision(path, field, value):
    record = json.loads(path.read_text(encoding="utf-8"))
    if value is ...:
        record.pop(field, None)
    else:
        record[field] = value
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")


@pytest.mark.parametrize("boundary", ["report", "review"])
@pytest.mark.parametrize("conflict", ["series", "run", "unknown_manifest", "dirty_manifest"])
def test_revision_conflicts_rejected_before_any_output_or_review_write(
    tmp_path, boundary, conflict
):
    write_report_experiment(tmp_path, experiment_manifests())
    manifest = tmp_path / "high/manifest.json"
    run = tmp_path / "high/runs.jsonl"
    change_revision(run, "git_sha", "b" * 40)
    if conflict == "series":
        change_revision(manifest, "git_sha", "b" * 40)
    elif conflict == "unknown_manifest":
        change_revision(manifest, "git_sha", ...)
    elif conflict == "dirty_manifest":
        change_revision(manifest, "git_dirty", True)
    for name in ["report.html", "summary.json", "review-template.jsonl"]:
        (tmp_path / name).write_text("previous output", encoding="utf-8")
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    with (
        patch("builtins.input") as ask,
        pytest.raises(ValueError, match="source revision mismatch"),
    ):
        if boundary == "report":
            report_module.summarize(tmp_path)
        else:
            review_module.review(tmp_path, "Putilin")
    ask.assert_not_called()
    assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before


UNVERIFIED_REVISIONS = [
    ("manifest", "git_sha", ...), ("manifest", "git_sha", None),
    ("manifest", "git_sha", ""), ("manifest", "git_sha", "a" * 39),
    ("manifest", "git_sha", "g" * 40), ("manifest", "git_sha", "a" * 40 + "\n"),
    ("manifest", "git_sha", 123), ("manifest", "git_sha", []),
    ("manifest", "git_dirty", ...), ("manifest", "git_dirty", None),
    ("manifest", "git_dirty", True), ("manifest", "git_dirty", 0),
    ("manifest", "git_dirty", "false"),
    ("runs", "git_sha", ...), ("runs", "git_sha", "not-a-sha"),
    ("runs", "git_sha", {}), ("runs", "git_dirty", True), ("runs", "git_dirty", 0),
]


@pytest.mark.usefixtures("valid_report_runtime")
@pytest.mark.parametrize("target,field,value", UNVERIFIED_REVISIONS)
def test_unverified_revision_keeps_human_pass_but_blocks_technical_pass(
    tmp_path, target, field, value
):
    write_report_experiment(tmp_path, experiment_manifests())
    path = tmp_path / "high" / ("manifest.json" if target == "manifest" else "runs.jsonl")
    change_revision(path, field, value)
    verdicts = (tmp_path / "verdicts.jsonl").read_bytes()
    result = report_module.summarize(tmp_path)
    assert result["status"] == result["series"]["high"]["status"] == "PENDING"
    assert result["series"]["medium"]["status"] == "PASS"
    assert result["series"]["high"]["groups"]["case"]["usable"] == 0
    assert result["series"]["high"]["revision_issues"]["case-1"]
    assert "source revision" in (tmp_path / "report.html").read_text(encoding="utf-8")
    assert (tmp_path / "verdicts.jsonl").read_bytes() == verdicts
    [run] = eval_module.read_jsonl(tmp_path / "high/runs.jsonl")
    verdict = next(row for row in eval_module.read_jsonl(tmp_path / "verdicts.jsonl")
                   if row["series"] == "high")
    assert report_module.human_status(run, verdict) == ("PASS", False)


@pytest.mark.parametrize("field,value", [(f, v) for target, f, v in UNVERIFIED_REVISIONS
                                         if target == "manifest"])
def test_collector_and_resume_use_the_same_clean_revision_contract(tmp_path, field, value):
    args, _, _ = resume_collection(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    valid = json.loads(manifest_path.read_text(encoding="utf-8"))
    change_revision(manifest_path, field, value)
    invalid = json.loads(manifest_path.read_text(encoding="utf-8"))
    with (
        patch.object(eval_module, "_git_state", return_value=invalid),
        pytest.raises(ValueError, match="clean Git revision"),
    ):
        eval_module.collection_revision()
    with pytest.raises(ValueError, match="git_sha/git_dirty"):
        eval_module.validate_resume_manifest(invalid, valid)


@pytest.mark.usefixtures("valid_report_runtime")
def test_legacy_semantic_review_remains_possible_without_certifying_revision(tmp_path, capsys):
    manifest = experiment_manifests()["high"]
    manifest["suite"]["reasoning"] = ["high"]
    write_report_experiment(tmp_path, {"high": manifest})
    change_revision(tmp_path / "high/manifest.json", "git_sha", ...)
    change_revision(tmp_path / "high/runs.jsonl", "git_sha", ...)
    (tmp_path / "verdicts.jsonl").unlink()
    before = {path: path.read_bytes() for path in (tmp_path / "high").iterdir()}
    with patch("builtins.input", side_effect=["y", "n"]):
        review_module.review(tmp_path, "Putilin")
    assert "ревизия не подтверждена" in capsys.readouterr().out
    [run] = eval_module.read_jsonl(tmp_path / "high/runs.jsonl")
    assert report_module.human_status(run, saved_verdict(tmp_path)) == ("PASS", False)
    assert report_module.summarize(tmp_path)["status"] == "PENDING"
    assert {path: path.read_bytes() for path in (tmp_path / "high").iterdir()} == before


@pytest.mark.parametrize("length", [40, 64])
def test_valid_revision_contract_accepts_full_git_object_ids(length):
    revision = {"git_sha": "a" * length, "git_dirty": False}
    with patch.object(eval_module, "_git_state", return_value=revision):
        assert eval_module.collection_revision() == revision
    assert eval_module.revision_problems(revision, {"git_sha": revision["git_sha"]}) == []


@pytest.mark.usefixtures("valid_report_runtime")
def test_unverified_revision_does_not_hide_a_human_failure(tmp_path):
    write_report_experiment(tmp_path, experiment_manifests())
    change_revision(tmp_path / "high/manifest.json", "git_dirty", True)
    path = tmp_path / "verdicts.jsonl"
    verdicts = eval_module.read_jsonl(path)
    for verdict in verdicts:
        if verdict["series"] == "high":
            verdict["critical_error"] = True
    path.write_text("".join(json.dumps(row) + "\n" for row in verdicts), encoding="utf-8")
    assert report_module.summarize(tmp_path)["status"] == "FAIL"


@pytest.mark.parametrize("dirty", [False, True])
def test_revision_contract_rejects_conflict_even_if_clean_state_is_unverified(dirty):
    with pytest.raises(ValueError, match="source revision mismatch"):
        eval_module.revision_problems(
            {"git_sha": "a" * 40, "git_dirty": dirty}, {"git_sha": "b" * 40}
        )


def proved_report_experiment(directory, *, repeats=1, minimum=1):
    """Synthetic archives/ledger, with the real evidence and report validators."""
    manifests = {"medium": experiment_manifests()["medium"]}
    manifest = manifests["medium"]
    manifest["suite"].update(reasoning=["medium"], repeats=repeats, minimum_usable=minimum)
    write_report_experiment(directory, manifests)
    path = directory / "medium"
    prototype = eval_module.read_jsonl(path / "runs.jsonl")[0]
    decision = eval_module.read_jsonl(directory / "verdicts.jsonl")[0]
    runs, decisions = [], []
    for attempt in range(1, repeats + 1):
        run = deepcopy(prototype)
        run.update(id=f"case-{attempt}", attempt=attempt, session_id=f"scenario_session_{attempt}")
        run["visible_text"] = run["output"]["text"]
        trace = path / f"case-{attempt}.zip"
        with zipfile.ZipFile(trace, "w") as archive:
            archive.writestr("trace.trace", "{}")
            archive.writestr("trace.network", run["session_id"])
        run["origin"].update(
            trace=trace.name, trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest()
        )
        run["provider_calls"] = [{
            "model": run["model"], "status": "succeeded", "estimated_cost": 0.01,
            "metadata": {"reasoning_effort": run["reasoning_effort"]},
            "input_tokens": 10, "output_tokens": 5,
        }]
        runs.append(run)
        decisions.append({**decision, "id": run["id"]})
    write_rows(path / "runs.jsonl", runs)
    write_rows(directory / "verdicts.jsonl", decisions)
    return path, runs


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


@pytest.mark.parametrize("boundary", ["report", "review", "resume"])
@pytest.mark.parametrize("field", [
    "timeout", "temperature", "num_retries", "api_base", "router_settings",
])
def test_baseline_contract_at_every_entry_point(tmp_path, boundary, field):
    manifests = experiment_manifests()
    high = manifests["high"]
    if field == "router_settings":
        high["original_router"][field] = {"retry_after": 42}
    else:
        high["original_router"]["model_list"][0]["litellm_params"][field] = 42
    high["router"] = eval_module.selected_router(
        high["original_router"], high["model"], high["reasoning_effort"]
    )
    write_report_experiment(tmp_path, manifests)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="router"), patch("builtins.input") as ask:
        if boundary == "report":
            report_module.summarize(tmp_path)
        elif boundary == "review":
            review_module.review(tmp_path, "Putilin")
        else:
            snapshot = {**manifests["medium"], "original_router": high["original_router"]}
            eval_module.validate_resume_manifest(manifests["medium"], snapshot)
    ask.assert_not_called()
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("field,value", [
    ("original_router", None), ("original_router", {}),
    ("original_router", {"model_list": []}),
    ("original_router", {"model_list": [{"litellm_params": {"model": ""}}]}),
    ("router", None), ("router", "not a mapping"),
])
def test_unknown_router_never_becomes_proved_by_a_human(tmp_path, field, value):
    path, _ = proved_report_experiment(tmp_path)
    change_revision(path / "manifest.json", field, value)
    verdicts = (tmp_path / "verdicts.jsonl").read_bytes()
    result = report_module.summarize(tmp_path)
    assert result["status"] == "PENDING"
    assert result["series"]["medium"]["configuration_issues"]
    assert (tmp_path / "verdicts.jsonl").read_bytes() == verdicts


@pytest.mark.parametrize("boundary", ["report", "review", "resume"])
def test_selected_router_must_be_exactly_the_declared_override(tmp_path, boundary):
    path, _ = proved_report_experiment(tmp_path)
    manifest_path = path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    saved = deepcopy(manifest)
    manifest["router"]["model_list"][0]["litellm_params"]["timeout"] = 99
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="selected router differs"):
        if boundary == "report":
            report_module.summarize(tmp_path)
        elif boundary == "review":
            review_module.review(tmp_path, "Putilin")
        else:
            eval_module.validate_resume_manifest(manifest, saved)


@pytest.mark.parametrize("ui", ["result", "error", "unknown"])
@pytest.mark.parametrize("proof", ["valid", "missing", "corrupt", "unreadable"])
@pytest.mark.parametrize("human", ["PASS", "FAIL", "PENDING"])
def test_acceptance_axes_through_real_report(tmp_path, ui, proof, human):
    path, runs = proved_report_experiment(tmp_path)
    run = runs[0]
    run["origin"]["ui_outcome"] = ui
    trace = path / run["origin"]["trace"]
    if proof == "missing":
        trace.unlink()
    elif proof == "corrupt":
        trace.write_bytes(b"not a trace")
        run["origin"]["trace_sha256"] = hashlib.sha256(trace.read_bytes()).hexdigest()
    write_rows(path / "runs.jsonl", runs)
    verdict_path = tmp_path / "verdicts.jsonl"
    decisions = eval_module.read_jsonl(verdict_path)
    if human == "FAIL":
        decisions[0]["critical_error"] = True
    elif human == "PENDING":
        decisions = []
    write_rows(verdict_path, decisions)
    previous = verdict_path.read_bytes()
    original_read = Path.read_bytes

    def read_bytes(file):
        if proof == "unreadable" and file == trace:
            raise PermissionError("unreadable trace")
        return original_read(file)

    with patch.object(Path, "read_bytes", read_bytes):
        result = report_module.summarize(tmp_path)
    expected = "FAIL" if human == "FAIL" or ui == "error" else "PENDING"
    if ui == "result" and proof == "valid" and human == "PASS":
        expected = "PASS"
    assert result["status"] == expected
    assert verdict_path.read_bytes() == previous
    series = result["series"]["medium"]
    assert series["measured_ui_attempts"] == int(ui == "result" and proof == "valid")
    assert series["ledger_estimated_cost"] == run["provider_calls"][0]["estimated_cost"]


@pytest.mark.parametrize("latencies,expected,median", [
    ([50000, 55000, 80000, 90000], "FAIL", 67500),
    ([1000, 2000, 3000, 4000], "PASS", 2500),
])
def test_failed_attempts_never_reduce_delivery_latency(tmp_path, latencies, expected, median):
    path, runs = proved_report_experiment(tmp_path, repeats=5, minimum=4)
    for run, latency in zip(runs, [*latencies, 0], strict=True):
        run["origin"]["ui_latency_ms"] = latency
    runs[-1]["origin"]["ui_outcome"] = "error"
    write_rows(path / "runs.jsonl", runs)
    result = report_module.summarize(tmp_path)
    assert result["status"] == expected
    series = result["series"]["medium"]
    assert series["median_ui_ms"] == median
    assert series["measured_ui_attempts"] == len(latencies)
    assert series["groups"]["case"]["usable"] == len(latencies)
    assert series["provider_calls"] == len(runs)
    costs = [r["provider_calls"][0]["estimated_cost"] for r in runs]
    assert series["ledger_estimated_cost"] == sum(costs)


@pytest.mark.parametrize("latency", [None, True, -1, float("nan"), float("inf"), "1000"])
def test_unverified_delivery_time_cannot_pass_the_gate(tmp_path, latency):
    path, runs = proved_report_experiment(tmp_path)
    runs[0]["origin"]["ui_latency_ms"] = latency
    write_rows(path / "runs.jsonl", runs)
    result = report_module.summarize(tmp_path)
    assert result["status"] == "PENDING"
    assert result["series"]["medium"]["median_ui_ms"] is None


def test_technical_status_does_not_depend_on_diagnostic_wording():
    assert report_module.accepted_status("PENDING", "PASS", []) == "PENDING"
    assert report_module.accepted_status("PASS", "PASS", []) == "PASS"
    assert report_module.accepted_status("PASS", "PASS", ["unproven identity"]) == "PENDING"
    assert report_module.accepted_status("FAIL", "PASS", []) == "FAIL"


@pytest.mark.parametrize("failure,outcome,submitted", [
    ("capture-result", "result", True), ("trace-start", "result", True),
    ("start-journal", "result", True), ("submit-journal", "unknown", False),
    ("pre-submit", "unknown", False), ("submit-timeout", "error", True),
    ("capture-visible", "unknown", True),
])
def test_driver_records_only_what_was_observed(tmp_path, failure, outcome, submitted):
    result = driver_result({
        "trace": str(tmp_path / "attempt.zip"), "language": "en", "tone": "warm",
        "progress_notes": "Done", "web_url": "https://web",
    }, failure, eval_module.subprocess.run)
    assert result["record"]["ui_outcome"] == outcome
    assert result["calls"].count("submit") == int(submitted)
    assert result["calls"].count("close") == 1
    with pytest.raises(RuntimeError):
        eval_module.require_collection_ready(result["record"])


@pytest.mark.parametrize("stage,expected", [
    ("start_response", "PENDING"), ("result_response", "PENDING"),
    ("trace_start", "PENDING"), ("trace", "PENDING"),
    ("unknown_capture_stage", "PENDING"),
    ("screenshot", "PASS"), ("browser_close", "PASS"),
    ("journal", "PASS"), ("start_journal", "PASS"),
])
def test_capture_proof_and_cleanup_diagnostics_have_separate_meanings(tmp_path, stage, expected):
    path, runs = proved_report_experiment(tmp_path)
    runs[0]["diagnostic_errors"] = {stage: "failure"}
    write_rows(path / "runs.jsonl", runs)
    result = report_module.summarize(tmp_path)
    assert result["status"] == expected
    assert result["series"]["medium"]["collection_diagnostics"] == {"case-1": {stage: "failure"}}
    assert stage in (tmp_path / "report.html").read_text(encoding="utf-8")


def test_router_key_order_is_not_experiment_drift(tmp_path):
    path, _ = proved_report_experiment(tmp_path)
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    reordered = json.loads(json.dumps(manifest, sort_keys=True))
    eval_module.validate_resume_manifest(manifest, reordered)
    assert report_module.summarize(tmp_path)["status"] == "PASS"


@pytest.mark.parametrize("change", ["source", "input", "duplicate", "attempt"])
def test_resume_validates_imported_runs_before_mutating_worker(tmp_path, change):
    path, runs = proved_report_experiment(tmp_path)
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    args, baseline, prompt = resume_collection(tmp_path)
    args.out = path
    args.suite = tmp_path / "suite.json"
    args.suite.write_text(json.dumps(manifest["suite"]), encoding="utf-8")
    manifest.update(
        original_router=baseline, prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest()
    )
    manifest["router"] = eval_module.selected_router(baseline, args.model, args.reasoning)
    runs[0]["prompt_sha256"] = manifest["prompt_sha256"]
    if change == "source":
        runs[0]["git_sha"] = "b" * 40
    elif change == "input":
        runs[0]["input"] = {**runs[0]["input"], "progress_notes": "tampered"}
    elif change == "duplicate":
        runs.append(deepcopy(runs[0]))
    else:
        runs[0]["attempt"] = 99
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    write_rows(path / "runs.jsonl", runs)
    with (
        patch.object(eval_module, "_git_state", return_value={
            "git_sha": "a" * 40, "git_dirty": False,
        }),
        patch.object(eval_module, "_docker", side_effect=lambda *a:
                     prompt if a[-1].endswith(".md") else json.dumps(baseline)),
        patch.object(eval_module, "write_router") as write,
        pytest.raises(ValueError),
    ):
        eval_module.collect(args)
    write.assert_not_called()


def test_incomplete_slow_observations_are_not_a_final_latency_failure(tmp_path):
    path, runs = proved_report_experiment(tmp_path, repeats=5, minimum=4)
    runs[0]["origin"]["ui_latency_ms"] = 90000
    write_rows(path / "runs.jsonl", runs[:1])
    result = report_module.summarize(tmp_path)
    assert result["status"] == "PENDING"
    assert not result["series"]["medium"]["observations_complete"]


def test_unknown_identity_on_a_failed_attempt_cannot_complete_an_experiment(tmp_path):
    path, runs = proved_report_experiment(tmp_path, repeats=5, minimum=4)
    runs[-1]["origin"]["ui_outcome"] = "error"
    del runs[-1]["git_sha"]
    write_rows(path / "runs.jsonl", runs)
    result = report_module.summarize(tmp_path)
    assert result["status"] == "PENDING"
    assert not result["series"]["medium"]["observations_complete"]


@pytest.mark.parametrize("limit", [None, True, -1, float("nan"), float("inf"), "60000"])
def test_invalid_latency_limit_is_rejected_before_collect_or_report(tmp_path, limit):
    manifests = experiment_manifests()
    for manifest in manifests.values():
        manifest["suite"]["max_median_ui_ms"] = limit
    write_report_experiment(tmp_path, manifests)
    with pytest.raises(ValueError, match="max_median_ui_ms"):
        report_module.summarize(tmp_path)
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps(manifests["medium"]["suite"]), encoding="utf-8")
    with (
        patch.object(eval_module, "_docker") as docker,
        pytest.raises(ValueError, match="max_median_ui_ms"),
    ):
        eval_module.collect(SimpleNamespace(suite=suite))
    docker.assert_not_called()


@pytest.mark.parametrize("prompt_hash", [None, "", "bad-hash"])
def test_unknown_prompt_revision_is_not_certified_by_matching_unknown_values(tmp_path, prompt_hash):
    path, runs = proved_report_experiment(tmp_path)
    change_revision(path / "manifest.json", "prompt_sha256", prompt_hash)
    runs[0]["prompt_sha256"] = prompt_hash
    write_rows(path / "runs.jsonl", runs)
    assert report_module.summarize(tmp_path)["status"] == "PENDING"
