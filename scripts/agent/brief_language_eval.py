"""Collect ANY-761 canonical outputs and ledger evidence on an isolated local live stack.

Model selection belongs to the stack's backend configuration. This collector never changes it.
Each invocation creates a new directory; failures and previous series are never overwritten.
The report requires a human decision for every authored field and semantic criterion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlsplit

from proposal_ai_eval import _docker, _git_state, _parse_compose_project, _request

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "tests/fixtures/brief_language_eval/cases.json"
WORKER_PYTHON = "/app/apps/platform-worker/.venv/bin/python"
SCENARIOS = (
    "brief_decoder.decode_v1",
    "acceptance_builder.draft_v1",
    "acceptance_builder.check_v1",
)

# Read the running worker's files, not a potentially different host checkout. Never export keys.
SNAPSHOT = """
import hashlib, json
from pathlib import Path
import yaml
root = Path('/app')
products = (root / 'packages/backend/product-platforms/freelancer-suite/src'
            / 'anytoolai_freelancer_suite/products')
files = [root / 'configs/kernel/litellm_router.yaml']
for name in ('brief_decoder', 'acceptance_builder'):
    files += sorted(p for p in (products / name).rglob('*') if p.is_file())
hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
router = yaml.safe_load(files[0].read_text())
models = [{k: e['litellm_params'].get(k) for k in ('model', 'reasoning_effort')}
          | {'alias': e['model_name']} for e in router['model_list']]
print(json.dumps({'source_sha256': hashes, 'configured_models': models}))
"""

# SQLAlchemy binds the session ID; all credentials stay inside the worker.
LEDGER = """
import json, sys
import sqlalchemy as sa
from anytoolai_platform_worker.settings import WorkerSettings
from anytoolai_platform_core.storage.db import (
    action_runs_table, artifacts_table, provider_calls_table, create_sync_engine,
)
settings = WorkerSettings.from_env()
engine = create_sync_engine(settings.database_url,
                            decode_database_name=settings.decode_database_name)
with engine.connect() as connection:
    result = {}
    tables = [('actions', action_runs_table), ('artifacts', artifacts_table),
              ('calls', provider_calls_table)]
    for name, table in tables:
        query = sa.select(table).where(table.c.scenario_session_id == sys.argv[1])
        rows = connection.execute(query).mappings()
        result[name] = [dict(row) for row in rows]
print(json.dumps(result, default=str))
"""


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def authored_fields(output: dict) -> dict[str, str]:
    """Enumerate prose, including mixed quotation/explanation fields, without guessing language."""
    fields = {}

    def visit(value: object, path: str) -> None:
        if isinstance(value, str):
            fields[path] = value
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{path}/{index}")
        elif isinstance(value, dict):
            for key, item in value.items():
                visit(item, f"{path}/{key}")

    for key in ("brief", "extracted"):
        values = output.get(key, {}).get("values", {})
        visit(
            {name: value for name, value in values.items() if name != "analysis_language"},
            f"/{key}/values",
        )
    for key, names in (
        ("issues", ("description", "evidence")),
        ("questions", ("question", "rationale")),
    ):
        for index, item in enumerate(output.get(key, [])):
            for name in names:
                if name in item:
                    visit(item[name], f"/{key}/{index}/{name}")
    comparison = output.get("comparison", {})
    if "rationale" in comparison:
        visit(comparison["rationale"], "/comparison/rationale")
    for index, delta in enumerate(comparison.get("deltas", [])):
        visit(delta["evidence"], f"/comparison/deltas/{index}/evidence")
    document = output.get("document", {})
    if "summary" in document:
        visit(document["summary"], "/document/summary")
    for index, section in enumerate(document.get("sections", [])):
        visit(section["content"], f"/document/sections/{index}/content")
    return fields


def review_template(record: dict) -> dict:
    return {
        "evidence_sha256": digest(record),
        "reviewer": "",
        "fields": {path: None for path in authored_fields(record.get("output") or {})},
        "criteria": {question: None for question in record["case"]["criteria"]},
        "notes": "",
    }


def review_status(record: dict, review: dict) -> str:
    expected = review_template(record)
    if review.get("evidence_sha256") != expected["evidence_sha256"]:
        raise ValueError("review does not belong to this evidence")
    decisions = []
    for group in ("fields", "criteria"):
        if set(review.get(group, {})) != set(expected[group]):
            raise ValueError(f"incomplete or unexpected review {group}")
        decisions += list(review[group].values())
    if any(value is not None and type(value) is not bool for value in decisions):
        raise ValueError("review decisions must be true, false or null")
    if record.get("error") or record.get("evidence_error") or False in decisions:
        return "FAIL"
    ledger = record.get("ledger") or {}
    if not record.get("output") or not ledger.get("calls"):
        return "PENDING"
    actions, artifacts = ledger.get("actions", []), ledger.get("artifacts", [])
    if not actions or not artifacts or not record.get("session_id") or not record.get("result_id"):
        return "PENDING"
    if any(
        row.get("scenario_session_id") != record["session_id"]
        for row in [*actions, *artifacts, *ledger["calls"]]
    ):
        raise ValueError("ledger belongs to another session")
    artifact_ids = {artifact["id"] for artifact in artifacts}
    action_ids = {action["id"] for action in actions}
    scenario = record["case"]["scenario_id"]
    expected_steps = {
        "brief_decoder.decode_v1": {
            "extract",
            "detect_issues",
            "generate_questions",
            "generate_document",
        },
        "acceptance_builder.draft_v1": {"extract"},
        "acceptance_builder.check_v1": {"extract", "compare"},
    }[scenario]
    if scenario.startswith("acceptance_builder.") and "document" in record["output"]:
        expected_steps = expected_steps | {"generate_document"}  # Retained pre-correction evidence.
    if scenario == "brief_decoder.decode_v1" and not record["output"]["issues"]:
        expected_steps.remove("generate_questions")
    completed = [action for action in actions if action["status"] != "skipped"]
    successful_calls = {
        call["action_run_id"] for call in ledger["calls"] if call["status"] == "succeeded"
    }
    if (
        record["result_id"] not in artifact_ids
        or {action["step_id"] for action in completed} != expected_steps
        or len(completed) != len(expected_steps)
        or any(
            action["status"] != "succeeded" or action["id"] not in successful_calls
            for action in completed
        )
        or any(action.get("output_artifact_id") not in artifact_ids for action in completed)
        or any(call.get("action_run_id") not in action_ids for call in ledger["calls"])
        or not any(
            artifact["id"] == record["result_id"]
            and artifact.get("content_json") == record["output"]
            for artifact in artifacts
        )
    ):
        return "PENDING"
    if (
        any(not call.get("model") or not call.get("id") for call in ledger["calls"])
        or not review.get("reviewer", "").strip()
        or None in decisions
    ):
        return "PENDING"
    return "PASS"


def collect(args: argparse.Namespace, case: dict, attempt: int, snapshot: dict) -> dict:
    record = {
        "case": case,
        "attempt": attempt,
        "snapshot": snapshot,
        "channel": "api",
        "session_id": None,
        "job_id": None,
        "result_id": None,
        "output": None,
        "error": None,
        "evidence_error": None,
        "ledger": None,
        "confirmed_reasoning_effort": None,
    }
    started = time.monotonic()
    try:
        guest = _request(f"{args.api_url}/v1/identity/guest", method="POST")["guest_id"]
        scenario = case["scenario_id"]
        product = scenario.split(".")[0]
        start = _request(
            f"{args.api_url}/v1/products/{product}/scenarios/{scenario}/start",
            method="POST",
            payload={"frontend_id": "web_mirror", "guest_id": guest, "input": case["input"]},
        )
        record.update(session_id=start["scenario_session_id"], job_id=start["job_id"])
        while time.monotonic() - started < args.timeout:
            session = _request(f"{args.api_url}/v1/scenario-sessions/{record['session_id']}")
            if session["status"] == "completed":
                record["result_id"] = session["result_artifact_id"]
                record["output"] = _request(f"{args.api_url}/v1/results/{record['result_id']}")[
                    "output"
                ]
                break
            if session["status"] in ("failed", "cancelled", "expired"):
                raise RuntimeError(f"session ended: {session['status']}")
            time.sleep(1)
        else:
            raise TimeoutError("workflow timed out")
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        record["latency_ms"] = round((time.monotonic() - started) * 1000)
        if record["session_id"]:
            try:
                record["ledger"] = json.loads(
                    _docker(
                        args.project,
                        "platform-worker",
                        WORKER_PYTHON,
                        "-c",
                        LEDGER,
                        record["session_id"],
                    )
                )
                after = json.loads(
                    _docker(args.project, "platform-worker", WORKER_PYTHON, "-c", SNAPSHOT)
                )
                if after != snapshot:
                    record["evidence_error"] = "running configuration changed during collection"
            except (
                Exception
            ) as exc:  # Preserve the completed run even when evidence retrieval fails.
                record["evidence_error"] = f"{type(exc).__name__}: {exc}"
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--api-url", required=True)
    run.add_argument("--project", required=True, type=_parse_compose_project)
    run.add_argument("--scenario", choices=SCENARIOS, required=True)
    run.add_argument("--family", choices=("basic", "weak", "mixed", "override"))
    run.add_argument("--repeats", type=int, default=3)
    run.add_argument("--timeout", type=int, default=240)
    run.add_argument("--out", type=Path, required=True)
    report = commands.add_parser("report")
    report.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "report":
        manifest = json.loads((args.out / "manifest.json").read_text(encoding="utf-8"))
        statuses = []
        for key in manifest["runs"]:
            path = args.out / f"{key}.json"
            if not path.exists():
                status = "PENDING"
            else:
                record = json.loads(path.read_text(encoding="utf-8"))
                case_id, attempt = key.rsplit("--", 1)
                expected_case = next(case for case in manifest["cases"] if case["id"] == case_id)
                if (
                    record["case"] != expected_case
                    or record["attempt"] != int(attempt)
                    or record["snapshot"] != manifest["snapshot"]
                ):
                    raise ValueError("run differs from the planned case/configuration")
                review = json.loads((args.out / f"{key}.review.json").read_text(encoding="utf-8"))
                status = review_status(record, review)
            statuses.append(status)
            print(f"{key}: {status}")
        return 0 if statuses and set(statuses) == {"PASS"} else 1
    url = urlsplit(args.api_url)
    if (
        url.scheme != "http"
        or url.hostname not in ("localhost", "127.0.0.1", "::1")
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in ("", "/")
    ):
        parser.error("use the isolated local development API URL")
    if args.repeats < 1 or args.timeout < 1:
        parser.error("repeats and timeout must be positive")
    args.api_url = args.api_url.rstrip("/")
    cases = [
        case
        for case in json.loads(SUITE.read_text(encoding="utf-8"))["cases"]
        if case["scenario_id"] == args.scenario
        and (args.family is None or case["family"] == args.family)
    ]
    snapshot = json.loads(_docker(args.project, "platform-worker", WORKER_PYTHON, "-c", SNAPSHOT))
    args.out.mkdir(parents=True, exist_ok=False)
    runs = [f"{case['id']}--{attempt}" for attempt in range(1, args.repeats + 1) for case in cases]
    write_json(
        args.out / "manifest.json",
        {"cases": cases, "runs": runs, "snapshot": snapshot, "source": _git_state()},
    )
    for attempt in range(1, args.repeats + 1):
        for case in cases:
            key = f"{case['id']}--{attempt}"
            record = collect(args, case, attempt, snapshot)
            write_json(args.out / f"{key}.json", record)
            write_json(args.out / f"{key}.review.json", review_template(record))
            print(
                f"{key}: {'ERROR' if record['error'] else 'collected; review pending'}", flush=True
            )
            if record["error"] or record["evidence_error"]:
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
