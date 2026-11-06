"""Render full ANY-624 outputs and summarize measured evidence without inventing semantic verdicts.

  LITELLM_LOCAL_MODEL_COST_MAP=True .quick-check-venv/bin/python \
    scripts/agent/client_update_writer_eval_report.py .agent/any-624

Writes report.html, summary.json and review-template.jsonl. Human decisions belong in
verdicts.jsonl: copy a template row, answer each criterion yes/no/unknown with quote/reason,
set critical_error to true/false and reviewer to a human identifier. Hashes bind the verdict
to the input, output and questions. Missing or stale decisions never produce PASS.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import statistics
from pathlib import Path

from client_update_writer_eval import (
    EvaluationStatus,
    configuration_problems,
    digest,
    evidence_status,
    revision_problems,
    validate_manifest_identity,
    validate_runs,
    validate_source_revisions,
    validate_suite,
)
from proposal_ai_eval import delivery_latency, read_jsonl


def human_status(run: dict, verdict: dict | None) -> tuple[EvaluationStatus, bool]:
    if verdict is None:
        return "PENDING", False
    for field in ("input_sha256", "output_sha256", "criteria_sha256"):
        expected = digest(run["input"]["criteria"]) if field == "criteria_sha256" else run[field]
        if verdict.get(field) != expected:
            return "PENDING", False
    reviewer = verdict.get("reviewer")
    answers = verdict.get("answers")
    if (
        not isinstance(reviewer, str)
        or not reviewer.strip()
        or reviewer.strip().lower() == "agent"
        or not isinstance(verdict.get("critical_error"), bool)
        or not isinstance(answers, list)
        or len(answers) != len(run["input"]["criteria"])
    ):
        return "PENDING", False
    if any(
        not isinstance(answer, dict)
        or answer.get("decision") not in ("yes", "no", "unknown")
        or not isinstance(answer.get("reason"), str)
        or not answer["reason"].strip()
        or not isinstance(answer.get("quote"), str)
        or answer.get("question") != question
        for question, answer in zip(run["input"]["criteria"], answers, strict=True)
    ):
        return "PENDING", False
    if verdict["critical_error"] or any(answer["decision"] == "no" for answer in answers):
        return "FAIL", verdict["critical_error"]
    undecided = any(answer["decision"] == "unknown" for answer in answers)
    return ("PENDING" if undecided else "PASS"), False


def render_run(series: str, run: dict, status: str, case: dict, evidence_issues: list[str]) -> str:
    output = json.dumps(run.get("output"), ensure_ascii=False, indent=2)
    questions = "".join("<li>" + html.escape(q) + "</li>" for q in case["criteria"])
    evidence = html.escape(
        json.dumps(
            {
                "evidence_issues": evidence_issues,
                **{
                    key: run.get(key)
                    for key in (
                        "session_id",
                        "model",
                        "reasoning_effort",
                        "prompt_sha256",
                        "git_sha",
                        "origin",
                        "provider_calls",
                        "review_needed",
                        "recovery_note",
                        "diagnostic_reason",
                        "diagnostic_errors",
                        "trace_error",
                        "error",
                    )
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return (
        f"<h2>{html.escape(series + '/' + run['id'])} — {status}</h2>"
        f"<h3>Input</h3><pre>{html.escape(case['progress_notes'])}</pre>"
        f"<h3>Full output</h3><pre>{html.escape(output)}</pre>"
        f"<h3>Review questions</h3><ol>{questions}</ol>"
        f"<details><summary>Evidence and provider ledger</summary><pre>{evidence}</pre></details>"
    )


def validate_experiment(manifests: dict[str, dict]) -> tuple[dict, set[tuple[str, str]]]:
    if not manifests:
        raise ValueError("no experiment manifests found")
    reference = next(iter(manifests.values()))
    suite = reference["suite"]
    validate_suite(suite)
    validate_manifest_identity(manifests.values())
    planned = {(model, effort) for model in suite["models"] for effort in suite["reasoning"]}
    if not planned or len(planned) != len(suite["models"]) * len(suite["reasoning"]):
        raise ValueError("empty or duplicate experiment configuration matrix")
    observed: set[tuple[str, str]] = set()
    for manifest in manifests.values():
        if manifest["suite_sha256"] != digest(manifest["suite"]):
            raise ValueError("suite manifest digest mismatch")
        pair = (manifest["model"], manifest["reasoning_effort"])
        if pair not in planned:
            raise ValueError("configuration outside experiment plan")
        if pair in observed:
            raise ValueError("duplicate experiment configuration")
        observed.add(pair)
    return suite, observed


def overall_summary(summary: dict, suite: dict, observed: set[tuple[str, str]]) -> dict:
    if not summary:
        raise ValueError("no experiment manifests found")
    missing = [
        {"model": model, "reasoning_effort": effort}
        for model in suite["models"]
        for effort in suite["reasoning"]
        if (model, effort) not in observed
    ]
    overall = (
        "PENDING" if missing or any(s["status"] == "PENDING" for s in summary.values()) else "PASS"
    )
    if any(s["status"] == "FAIL" for s in summary.values()):
        overall = "FAIL"
    return {"status": overall, "series": summary, "missing_configurations": missing}


def measured_metrics(
    runs: list[dict], diagnostics: list[dict], groups: dict, verified_runs: list[dict]
) -> dict:
    times = [
        value
        for run in verified_runs
        if (value := delivery_latency(run)) is not None
    ]
    calls = [call for run in runs + diagnostics for call in run["provider_calls"]]
    costs = [
        call["estimated_cost"]
        for call in calls
        if isinstance(call.get("estimated_cost"), (int, float))
        and math.isfinite(call["estimated_cost"])
        and call["estimated_cost"] >= 0
    ]
    median = statistics.median(times) if times else None
    usable = sum(group["usable"] for group in groups.values())
    return {
        "median_ui_ms": median,
        "mean_ui_ms": statistics.mean(times) if times else None,
        "p90_ui_ms": sorted(times)[math.ceil(len(times) * 0.9) - 1] if times else None,
        "measured_ui_attempts": len(times),
        "provider_calls": len(calls),
        "provider_retries": sum(
            max(len(run["provider_calls"]) - 1, 0) for run in runs + diagnostics
        ),
        "input_tokens": sum(call["input_tokens"] for call in calls),
        "output_tokens": sum(call["output_tokens"] for call in calls),
        "diagnostic_attempts": len(diagnostics),
        "ledger_estimated_cost": sum(costs),
        "calls_without_cost": len(calls) - len(costs),
        "cost_per_usable": sum(costs) / usable if usable and len(costs) == len(calls) else None,
    }


def accepted_status(
    technical: EvaluationStatus, human: EvaluationStatus, problems: list[str]
) -> EvaluationStatus:
    if "FAIL" in (technical, human):
        return "FAIL"
    return "PASS" if technical == human == "PASS" and not problems else "PENDING"


def summarize(directory: Path) -> dict:
    manifests = {
        path.parent.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*/manifest.json"))
    }
    suite, observed = validate_experiment(manifests)
    series_runs = {
        series: read_jsonl(directory / series / "runs.jsonl") for series in manifests
    }
    validate_source_revisions([
        *manifests.values(), *(run for runs in series_runs.values() for run in runs)
    ])
    verdicts = {(row["series"], row["id"]): row for row in read_jsonl(directory / "verdicts.jsonl")}
    summary = {}
    template = []
    sections = []
    for series, manifest in manifests.items():
        series_directory = directory / series
        runs = series_runs[series]
        diagnostics = read_jsonl(series_directory / "diagnostics.jsonl")
        sections.extend(
            render_run(series, run, "DIAGNOSTIC", run["input"], []) for run in diagnostics
        )
        validate_runs(manifest, runs)
        revision_issues = {
            run["id"]: issues for run in runs if (issues := revision_problems(manifest, run))
        }
        configuration_issues = configuration_problems(manifest)
        assessments = {run["id"]: evidence_status(run, series_directory) for run in runs}
        groups = {}
        for case in manifest["suite"]["cases"]:
            group = [run for run in runs if run["case"] == case["id"]]
            expected = manifest["suite"]["repeats"]
            statuses = []
            critical = 0
            for run in group:
                measured, problems = assessments[run["id"]]
                problems = problems + revision_issues.get(run["id"], []) + configuration_issues
                human, is_critical = human_status(run, verdicts.get((series, run["id"])))
                status = accepted_status(measured, human, problems)
                statuses.append(status)
                critical += is_critical
                template.append(
                    {
                        "series": series,
                        "id": run["id"],
                        "input_sha256": run["input_sha256"],
                        "output_sha256": run["output_sha256"],
                        "criteria_sha256": digest(case["criteria"]),
                        "reviewer": None,
                        "critical_error": None,
                        "answers": [
                            {"question": q, "decision": None, "quote": "", "reason": ""}
                            for q in case["criteria"]
                        ],
                    }
                )
                sections.append(
                    render_run(series, run, status, case, problems)
                )
            passed = statuses.count("PASS")
            pending = statuses.count("PENDING") + expected - len(group)
            state = "PENDING" if pending else "PASS"
            if critical or passed + pending < manifest["suite"]["minimum_usable"]:
                state = "FAIL"
            groups[case["id"]] = {
                "status": state,
                "attempts": len(group),
                "usable": passed,
                "pending": pending,
                "critical_errors": critical,
            }
        verified_runs = [run for run in runs if assessments[run["id"]][0] == "PASS"
                         and not revision_issues.get(run["id"]) and not configuration_issues]
        metrics = measured_metrics(runs, diagnostics, groups, verified_runs)
        median = metrics["median_ui_ms"]
        complete = (
            len(runs) == manifest["suite"]["repeats"] * len(manifest["suite"]["cases"])
            and not revision_issues and not configuration_issues
            and all(assessments[run["id"]][0] == "PASS"
                    or (run.get("origin") or {}).get("ui_outcome") == "error" for run in runs)
        )
        state = "PENDING" if not complete or median is None or any(
            g["status"] == "PENDING" for g in groups.values()
        ) else "PASS"
        if any(g["status"] == "FAIL" for g in groups.values()) or (
            complete and median is not None and median > manifest["suite"]["max_median_ui_ms"]
        ):
            state = "FAIL"
        summary[series] = {
            "status": state, "groups": groups, "revision_issues": revision_issues,
            "observations_complete": bool(complete),
            "configuration_issues": configuration_issues,
            "evidence_issues": {key: issues for key, (_, issues) in assessments.items() if issues},
            "collection_diagnostics": {
                run["id"]: run["diagnostic_errors"] for run in runs if run.get("diagnostic_errors")
            },
            **metrics
        }
    result = overall_summary(summary, suite, observed)
    (directory / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (directory / "review-template.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in template), encoding="utf-8"
    )
    (directory / "report.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>ANY-624 review</title>'
        "<style>body{max-width:70rem;margin:2rem auto;font-family:system-ui}"
        "pre{white-space:pre-wrap}</style>"
        "<h1>ANY-624 — human review pending</h1>" + "".join(sections),
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.directory), ensure_ascii=False, indent=2))
