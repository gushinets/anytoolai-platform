"""Collect ANY-624 live web evidence; no automatic semantic PASS decisions.

Run with managed Python, a local dev-live stack and served web-mirror:
  .quick-check-venv/bin/python scripts/agent/client_update_writer_eval.py \
    --project anytoolai-xxxxxxxx --web-url http://localhost:3200 \
    --model <provider/model> --reasoning medium --out <results-directory>

Offline human review: use the review subcommand with --directory, --reviewer and optional
--series. It resumes saved verdicts without submitting new scenarios.

The worker router is overridden only inside its container, read back, and restored
in finally. Run one collector at a time on this isolated stack. Never use a production stack.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import signal
import subprocess
import sys
from itertools import islice
from pathlib import Path
from typing import Literal

import yaml
from proposal_ai_eval import (
    _docker,
    _git_state,
    _parse_compose_project,
    evidence_problems,
    read_jsonl,
)

EvaluationStatus = Literal["PASS", "FAIL", "PENDING"]

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/client_update_writer_eval/screening.json"
PRODUCT = (
    "packages/backend/product-platforms/freelancer-suite/src/"
    "anytoolai_freelancer_suite/products/client_update_writer"
)
ROUTER = "/app/configs/kernel/litellm_router.yaml"
DRIVER = ROOT / "tests/e2e/client-update-writer-smoke/collect-live.mjs"
DRIVER_TIMEOUT_SECONDS = 180
WORKER_RESTART_TIMEOUT_SECONDS = 90


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def provider_calls(project: str, session_id: str | None) -> list[dict]:
    if session_id is None:
        return []
    if not re.fullmatch(r"scenario_session_[A-Za-z0-9_]+", session_id):
        raise ValueError("invalid scenario session identifier")
    sql = (
        "select coalesce(json_agg(row_to_json(c)), '[]') from "
        "(select step_id, model, gateway_model, "
        "semantic_attempt_index, status, latency_ms, input_tokens, output_tokens, estimated_cost "
        f"from platform.provider_calls where scenario_session_id = '{session_id}' "
        "order by created_at) c"
    )
    return json.loads(
        _docker(
            project,
            "postgres",
            "sh",
            "-c",
            'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "$1"',
            "sh",
            sql,
        )
    )


def evidence_status(record: dict, directory: Path) -> tuple[EvaluationStatus, list[str]]:
    """Runtime failures fail; missing proof stays pending, even with a fluent output."""
    if record["origin"]["ui_outcome"] == "error":
        return "FAIL", ["UI did not deliver a result"]
    problems = evidence_problems(record, {"channel": "web_form"}, directory)
    calls = record["provider_calls"]
    if not calls:
        problems.append("provider ledger missing")
    if any(
        call["model"].removeprefix("openai/") != record["model"].removeprefix("openai/")
        for call in calls
    ):
        problems.append("provider model mismatch")
    if not any(call["status"] == "succeeded" for call in calls):
        problems.append("no successful provider call")
    output = record.get("output")
    if (
        not isinstance(output, dict)
        or not isinstance(output.get("text"), str)
        or not output["text"].strip()
    ):
        problems.append("canonical output missing")
    else:
        visible = output["text"]
        if output.get("call_to_action"):
            visible += "\n\n" + output["call_to_action"]
        if visible != record.get("visible_text"):
            problems.append("visible text differs from canonical text and call_to_action")
    return "PENDING", problems or ["human semantic review required"]


def write_router(project: str, content: str) -> None:
    project = _parse_compose_project(project)
    container = f"{project}-platform-worker-1"
    subprocess.run(
        [
            "docker",
            "exec",
            "--user",
            "root",
            "-i",
            "--",
            container,
            "python",
            "-c",
            "import sys; from pathlib import Path; Path(sys.argv[1]).write_text(sys.stdin.read())",
            ROUTER,
        ],
        input=content,
        text=True,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["docker", "restart", "--", container],
        check=True,
        capture_output=True,
        timeout=WORKER_RESTART_TIMEOUT_SECONDS,
    )
    if _docker(project, "platform-worker", "cat", ROUTER) != content:
        raise RuntimeError("worker router readback mismatch")


def collect(args: argparse.Namespace) -> None:
    suite = json.loads(args.suite.read_text())
    if args.model not in suite["models"] or args.reasoning not in suite["reasoning"]:
        raise ValueError("configuration outside frozen matrix")
    repeats = suite["repeats"] if args.repeats is None else args.repeats
    if not 1 <= repeats <= suite["repeats"]:
        raise ValueError("repeats must be between 1 and frozen screening repeats")
    args.out.mkdir(parents=True, exist_ok=args.resume)
    completed_ids = {row["id"] for row in read_jsonl(args.out / "runs.jsonl")}
    original = _docker(args.project, "platform-worker", "cat", ROUTER)
    router = yaml.safe_load(original)
    params = router["model_list"][0]["litellm_params"]
    params["model"] = args.model
    params["reasoning_effort"] = args.reasoning
    selected = yaml.safe_dump(router)
    prompt = _docker(
        args.project, "platform-worker", "cat", f"/app/{PRODUCT}/prompts/update_compose_reply.v1.md"
    )
    snapshot = {
        "suite": suite,
        "suite_sha256": digest(suite),
        **_git_state(),
        "model": args.model,
        "reasoning_effort": args.reasoning,
        "router": router,
        "original_router": yaml.safe_load(original),
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
    }
    manifest_path = args.out / "manifest.json"
    if manifest_path.exists():
        saved = json.loads(manifest_path.read_text())
        original = yaml.safe_dump(saved["original_router"])
        for field in ("suite_sha256", "model", "reasoning_effort", "prompt_sha256"):
            if saved[field] != snapshot[field]:
                raise ValueError(f"resume manifest mismatch: {field}")
    else:
        manifest_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
    try:
        write_router(args.project, selected)
        attempts = (
            (case, attempt)
            for case in suite["cases"]
            for attempt in range(1, repeats + 1)
            if f"{case['id']}-{attempt}" not in completed_ids
        )
        for case, attempt in islice(attempts, args.max_attempts):
            run_id = f"{case['id']}-{attempt}"
            trace = args.out / f"{run_id}.zip"
            if trace.exists() or Path(str(trace) + ".journal.json").exists():
                raise RuntimeError(
                    "orphaned browser evidence: reconcile before retrying this attempt"
                )
            spec = {**case, "web_url": args.web_url, "trace": str(trace.resolve())}
            completed = subprocess.run(
                ["node", str(DRIVER)],
                input=json.dumps(spec),
                text=True,
                capture_output=True,
                check=True,
                timeout=DRIVER_TIMEOUT_SECONDS,
            )
            observed = json.loads(completed.stdout)
            (args.out / f"{run_id}.browser.json").write_text(completed.stdout)
            record = {
                **observed,
                "id": run_id,
                "case": case["id"],
                "attempt": attempt,
                "channel": "web_form",
                "input": case,
                "input_sha256": digest(case),
                "output_sha256": digest(observed["output"]),
                "model": args.model,
                "reasoning_effort": args.reasoning,
                "prompt_sha256": snapshot["prompt_sha256"],
                "provider_calls": provider_calls(args.project, observed["session_id"]),
                "origin": {
                    "ui_outcome": observed["ui_outcome"],
                    "ui_latency_ms": observed["ui_latency_ms"],
                    "trace": trace.name,
                    "trace_sha256": hashlib.sha256(trace.read_bytes()).hexdigest(),
                },
            }
            record["status"], record["review_needed"] = evidence_status(record, args.out)
            with (args.out / "runs.jsonl").open("a") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(
                f"{run_id}: {record['status']}, {observed['ui_latency_ms'] / 1000:.1f}s",
                flush=True,
            )
            if _docker(args.project, "platform-worker", "cat", ROUTER) != selected:
                raise RuntimeError("worker configuration changed during collection")
            if observed["ui_outcome"] == "error":
                raise RuntimeError(
                    "UI failed; evidence retained. Diagnose before spending on more attempts."
                )
    finally:
        write_router(args.project, original)
        (args.out / "router-restored.txt").write_text(
            "Original worker router restored and read back.\n"
        )


def interrupt_collection(_signum, _frame) -> None:
    raise KeyboardInterrupt("collector terminated; restoring worker router")


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "review":
        # Review imports this collector through the report module.
        from client_update_writer_review import main as review_main  # noqa: PLC0415

        review_main(argv[1:])
        return
    signal.signal(signal.SIGTERM, interrupt_collection)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=None,
        help="Checkpoint after this many new attempts; resume keeps the frozen plan.",
    )
    parser.add_argument(
        "--suite", type=Path, default=FIXTURE, help="Frozen input/criteria manifest."
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--web-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--reasoning", required=True, choices=["medium", "high"])
    parser.add_argument(
        "--repeats", type=int, default=None, help="Defaults to the frozen suite repeats."
    )
    parser.add_argument("--out", required=True, type=Path)
    collect(parser.parse_args(argv))


if __name__ == "__main__":
    main()
