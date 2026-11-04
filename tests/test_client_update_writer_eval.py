"""Update evidence cannot become accepted from successful backend output alone."""

import hashlib
import importlib.util
import json
import sys
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


def record():
    return {
        "origin": {"ui_outcome": "result", "ui_latency_ms": 1000},
        "model": "openai/gpt-6-luna",
        "output": {"text": "Done.", "call_to_action": "Send photos."},
        "visible_text": "Done.\n\nSend photos.",
        "provider_calls": [{"model": "gpt-6-luna", "status": "succeeded"}],
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
    suite = json.loads(eval_module.FIXTURE.read_text())
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


report_spec = importlib.util.spec_from_file_location(
    "client_update_writer_eval_report", ROOT / "scripts/agent/client_update_writer_eval_report.py"
)
report_module = importlib.util.module_from_spec(report_spec)
report_spec.loader.exec_module(report_module)


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


def test_missing_configuration_keeps_overall_pending(tmp_path):
    suite = {"models": ["openai/gpt-6-luna"], "reasoning": ["medium", "high"]}
    series = tmp_path / "luna-medium"
    series.mkdir()
    (series / "manifest.json").write_text(
        json.dumps({"model": "openai/gpt-6-luna", "reasoning_effort": "medium"})
    )
    result = report_module.overall_summary({"luna-medium": {"status": "PASS"}}, tmp_path, suite)
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
    (tmp_path / "U01-ru-1.zip.journal.json").write_text('{"phase":"started"}')
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
        patch.object(eval_module, "_git_state", return_value={}),
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
