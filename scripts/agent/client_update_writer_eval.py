"""Collect ANY-624 live web evidence; no automatic semantic PASS decisions.

Run with managed Python, a local dev-live stack and served web-mirror:
  .quick-check-venv/bin/python scripts/agent/client_update_writer_eval.py \
    --project anytoolai-xxxxxxxx --web-url http://localhost:3200 \
    --model <provider/model> --reasoning medium --out <results-directory>

Offline human review: use the review subcommand with --directory, --reviewer and optional
--series. It resumes saved verdicts without submitting new scenarios.

The worker router is overridden only inside its container, read back, and restored
in finally. Run one collector at a time on this isolated stack. Never use a production stack.
Commit source changes before collecting; resume requires the same clean Git revision.
This identifies the checkout, not the container build; keep the stack on that revision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import signal
import subprocess
import sys
from collections.abc import Iterable
from copy import deepcopy
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


def validate_suite(suite: dict) -> None:
    if not isinstance(suite, dict):
        raise ValueError("suite must be an object")
    cases = suite.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("suite must contain cases")
    seen = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("suite case must be an object")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip() or case_id in seen:
            raise ValueError("suite case ids must be nonempty and unique")
        seen.add(case_id)
        criteria = case.get("criteria")
        if not isinstance(criteria, list) or not criteria or any(
            not isinstance(question, str) or not question.strip() for question in criteria
        ):
            raise ValueError("suite cases must have nonempty criteria")
    repeats, minimum = suite.get("repeats"), suite.get("minimum_usable")
    if type(repeats) is not int or type(minimum) is not int or not 1 <= minimum <= repeats:
        raise ValueError("suite requires integer 1 <= minimum_usable <= repeats")
    limit = suite.get("max_median_ui_ms")
    if type(limit) not in (int, float) or not math.isfinite(limit) or limit < 0:
        raise ValueError("suite requires a finite nonnegative max_median_ui_ms")


def source_revision(record: dict) -> str | None:
    sha = record.get("git_sha")
    if isinstance(sha, str) and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", sha):
        return sha
    return None


def clean_source_revision(record: dict) -> str | None:
    return source_revision(record) if record.get("git_dirty") is False else None


def validate_source_revisions(records: Iterable[dict]) -> None:
    revisions = {source_revision(record) for record in records} - {None}
    if len(revisions) > 1:
        raise ValueError("source revision mismatch")


def revision_problems(manifest: dict, run: dict) -> list[str]:
    validate_source_revisions((manifest, run))
    problems = []
    if clean_source_revision(manifest) is None:
        problems.append("manifest source revision is missing, malformed or not proven clean")
    if source_revision(run) is None:
        problems.append("run source revision is missing or malformed")
    # Runs inherit clean state from their matching manifest unless they explicitly contradict it.
    if run.get("git_dirty", False) is not False:
        problems.append("run source revision is not proven clean")
    return problems


def baseline_router(manifest: dict) -> dict | None:
    router = manifest.get("original_router")
    if not isinstance(router, dict):
        return None
    models = router.get("model_list")
    if not isinstance(models, list) or not models:
        return None
    for model in models:
        params = model.get("litellm_params") if isinstance(model, dict) else None
        if not isinstance(params, dict) or not isinstance(params.get("model"), str):
            return None
        if not params["model"].strip():
            return None
    return router


def selected_router(baseline: dict, model: str, effort: str) -> dict:
    if baseline_router({"original_router": baseline}) is None:
        raise ValueError("baseline router missing or malformed")
    router = deepcopy(baseline)
    router["model_list"][0]["litellm_params"].update(model=model, reasoning_effort=effort)
    return router


def router_problems(manifest: dict) -> list[str]:
    baseline = baseline_router(manifest)
    if baseline is None:
        return ["baseline router missing or malformed"]
    actual = manifest.get("router")
    if not isinstance(actual, dict):
        return ["selected router missing or malformed"]
    expected = selected_router(baseline, manifest["model"], manifest["reasoning_effort"])
    if digest(actual) != digest(expected):
        raise ValueError("selected router differs from baseline model/effort override")
    return []


def configuration_problems(manifest: dict) -> list[str]:
    problems = router_problems(manifest)
    prompt_hash = manifest.get("prompt_sha256")
    if not isinstance(prompt_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", prompt_hash):
        problems.append("prompt revision missing or malformed")
    return problems


def validate_manifest_identity(manifests: Iterable[dict]) -> None:
    """All known fixed coordinates must agree; absent proof is assessed separately."""
    manifests = list(manifests)
    validate_source_revisions(manifests)
    for manifest in manifests:
        if "suite" in manifest and manifest.get("suite_sha256") != digest(manifest["suite"]):
            raise ValueError("suite manifest digest mismatch")
    for field in ("suite_sha256", "prompt_sha256"):
        values = {digest(m[field]) for m in manifests if m.get(field) is not None}
        if len(values) > 1:
            raise ValueError(f"experiment {field.removesuffix('_sha256')} mismatch")
    baselines = {digest(router) for m in manifests if (router := baseline_router(m)) is not None}
    if len(baselines) > 1:
        raise ValueError("experiment baseline router mismatch")
    for manifest in manifests:
        router_problems(manifest)


def validate_runs(manifest: dict, runs: list[dict]) -> None:
    cases = {case["id"]: case for case in manifest["suite"]["cases"]}
    if manifest["suite_sha256"] != digest(manifest["suite"]):
        raise ValueError("suite manifest digest mismatch")
    validate_source_revisions([manifest, *runs])
    seen = set()
    identifiers = set()
    for run in runs:
        key = run["case"], run["attempt"]
        if key in seen or run["case"] not in cases or run["id"] in identifiers:
            raise ValueError("duplicate or unplanned attempt")
        if (type(run["attempt"]) is not int
                or not 1 <= run["attempt"] <= manifest["suite"]["repeats"]):
            raise ValueError("unplanned attempt")
        seen.add(key)
        identifiers.add(run["id"])
        if run["input"] != cases[run["case"]]:
            raise ValueError("input differs from planned case")
        for field in ("input", "output"):
            if run[field + "_sha256"] != digest(run[field]):
                raise ValueError(f"{field} digest mismatch")
        for field in ("model", "reasoning_effort", "prompt_sha256"):
            if run[field] != manifest[field]:
                raise ValueError(f"configuration mismatch: {field}")


def collection_revision() -> dict:
    revision = _git_state()
    if clean_source_revision(revision) is None:
        raise ValueError("collection requires an identifiable clean Git revision")
    return revision


def validate_resume_manifest(saved: dict, snapshot: dict) -> None:
    if clean_source_revision(saved) is None:
        raise ValueError("resume manifest mismatch: unverified git_sha/git_dirty")
    for field in (
        "suite_sha256", "model", "reasoning_effort", "prompt_sha256", "original_router",
        "git_sha", "git_dirty",
    ):
        if saved.get(field) != snapshot[field]:
            raise ValueError(f"resume manifest mismatch: {field}")
    validate_manifest_identity((saved, snapshot))
    if configuration_problems(saved):
        raise ValueError("resume manifest mismatch: unverified router or prompt")


def provider_calls(project: str, session_id: str | None) -> list[dict]:
    if session_id is None:
        return []
    if not re.fullmatch(r"scenario_session_[A-Za-z0-9_]+", session_id):
        raise ValueError("invalid scenario session identifier")
    sql = (
        "select coalesce(json_agg(row_to_json(c)), '[]') from "
        "(select step_id, model, gateway_model, "
        "semantic_attempt_index, status, latency_ms, input_tokens, output_tokens, estimated_cost, "
        "metadata "
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
    """Technical proof only; PASS never substitutes for a human semantic decision."""
    if (record.get("origin") or {}).get("ui_outcome") == "error":
        return "FAIL", ["UI did not deliver a result"]
    problems = evidence_problems(record, {"channel": "web_form"}, directory)
    calls = record["provider_calls"]
    if not calls:
        problems.append("provider ledger missing")
    effort = record.get("reasoning_effort")
    for call in calls:
        metadata = call.get("metadata")
        recorded = metadata.get("reasoning_effort") if isinstance(metadata, dict) else None
        if not effort or not recorded:
            problems.append("provider reasoning effort evidence missing")
        elif recorded != effort:
            return "FAIL", ["provider reasoning effort mismatch"]
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
    return ("PENDING", problems) if problems else ("PASS", [])


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
        encoding="utf-8",
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


def trace_origin(observed: dict, trace: Path) -> dict:
    try:
        trace_hash = hashlib.sha256(trace.read_bytes()).hexdigest()
    except OSError as error:
        trace_hash = None
        observed["trace_error"] = str(error)
    return {
        "ui_outcome": observed["ui_outcome"],
        "ui_latency_ms": observed["ui_latency_ms"],
        "trace": trace.name,
        "trace_sha256": trace_hash,
    }


def require_collection_ready(observed: dict) -> None:
    """Stopping further paid work does not reclassify the saved observation."""
    if observed["ui_outcome"] == "error":
        raise RuntimeError(
            "UI failed; evidence retained. Diagnose before spending on more attempts."
        )
    if observed["ui_outcome"] != "result":
        raise RuntimeError("UI outcome unknown; attempt retained. Reconcile before continuing.")
    if observed.get("diagnostic_errors") or observed.get("trace_error"):
        raise RuntimeError(
            "Evidence collection failed; attempt retained. Reconcile before continuing."
        )


def collect(args: argparse.Namespace) -> None:
    suite = json.loads(args.suite.read_text(encoding="utf-8"))
    validate_suite(suite)
    if args.model not in suite["models"] or args.reasoning not in suite["reasoning"]:
        raise ValueError("configuration outside frozen matrix")
    repeats = suite["repeats"] if args.repeats is None else args.repeats
    if not 1 <= repeats <= suite["repeats"]:
        raise ValueError("repeats must be between 1 and frozen screening repeats")
    revision = collection_revision()
    args.out.mkdir(parents=True, exist_ok=args.resume)
    completed = read_jsonl(args.out / "runs.jsonl")
    completed_ids = {row["id"] for row in completed}
    original = _docker(args.project, "platform-worker", "cat", ROUTER)
    baseline = yaml.safe_load(original)
    router = selected_router(baseline, args.model, args.reasoning)
    selected = yaml.safe_dump(router)
    prompt = _docker(
        args.project, "platform-worker", "cat", f"/app/{PRODUCT}/prompts/update_compose_reply.v1.md"
    )
    snapshot = {
        "suite": suite,
        "suite_sha256": digest(suite),
        **revision,
        "model": args.model,
        "reasoning_effort": args.reasoning,
        "router": router,
        "original_router": baseline,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
    }
    manifest_path = args.out / "manifest.json"
    if manifest_path.exists():
        saved = json.loads(manifest_path.read_text(encoding="utf-8"))
        validate_resume_manifest(saved, snapshot)
        validate_runs(snapshot, completed)
    else:
        manifest_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
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
                encoding="utf-8",
                capture_output=True,
                check=True,
                timeout=DRIVER_TIMEOUT_SECONDS,
            )
            observed = json.loads(completed.stdout)
            origin = trace_origin(observed, trace)
            (args.out / f"{run_id}.browser.json").write_text(completed.stdout, encoding="utf-8")
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
                "git_sha": revision["git_sha"],
                "provider_calls": provider_calls(args.project, observed["session_id"]),
                "origin": origin,
            }
            technical, problems = evidence_status(record, args.out)
            record["status"] = "FAIL" if technical == "FAIL" else "PENDING"
            record["review_needed"] = problems or ["human semantic review required"]
            with (args.out / "runs.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(
                f"{run_id}: {record['status']}, {observed['ui_latency_ms'] / 1000:.1f}s",
                flush=True,
            )
            if _docker(args.project, "platform-worker", "cat", ROUTER) != selected:
                raise RuntimeError("worker configuration changed during collection")
            require_collection_ready(observed)
    finally:
        write_router(args.project, original)
        (args.out / "router-restored.txt").write_text(
            "Original worker router restored and read back.\n", encoding="utf-8"
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
