"""Collect multilingual brief evaluations and ledger evidence on an isolated local live stack.

Model selection belongs to the stack's backend configuration. This collector never changes it.
Each invocation creates a new directory; failures and previous series are never overwritten.
The report requires a human decision for every authored field and semantic criterion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from functools import cache
from pathlib import Path
from urllib.parse import urlsplit

from anytoolai_platform_core.structured_output.schemas import publication_schema
from draft_risk_review import DECISION_FIELDS, decision_questions
from jsonschema import Draft202012Validator
from proposal_ai_eval import _docker, _git_state, _parse_compose_project, _request

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "tests/fixtures/brief_language_eval/cases.json"
WORKER_PYTHON = "/app/apps/platform-worker/.venv/bin/python"
PRODUCTS = (
    ROOT / "packages/backend/product-platforms/freelancer-suite/src"
    / "anytoolai_freelancer_suite/products"
)
DRAFT = "acceptance_builder.draft_v1"
CHECK = "acceptance_builder.check_v1"
OUTPUT_SCHEMAS = {
    "brief_decoder.decode_v1": "brief_decoder/schemas/decode_output.schema.json",
    DRAFT: "acceptance_builder/schemas/draft_output.schema.json",
    CHECK: "acceptance_builder/schemas/check_output.schema.json",
}
SCENARIOS = tuple(OUTPUT_SCHEMAS)

# Read the running worker's files, not a potentially different host checkout. Never export keys.
SNAPSHOT = """
import hashlib, json
from pathlib import Path
import yaml
root = Path('/app')
products = (root / 'packages/backend/product-platforms/freelancer-suite/src'
            / 'anytoolai_freelancer_suite/products')
files = [root / 'configs/kernel/litellm_router.yaml']
kernel = root / 'configs/kernel/schemas'
files.extend(kernel / name for name in (
    'extract_input.schema.json', 'extract_output.schema.json', 'issue_detection_output.schema.json',
    'generate_questions_input.schema.json', 'generate_questions_output.schema.json',
))
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


def evidence_path(directory: Path, filename: str) -> Path:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*(?:\.review)?\.json", filename) is None:
        raise ValueError("invalid evidence filename")
    path = directory / filename
    if not path.resolve().is_relative_to(directory.resolve()):
        raise ValueError("evidence path resolves outside the output directory")
    return path


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


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


@cache
def _output_validator(scenario: str, *, historical: bool = False) -> Draft202012Validator:
    path = PRODUCTS / OUTPUT_SCHEMAS[scenario]
    schema = json.loads(path.read_text(encoding="utf-8"))
    return Draft202012Validator(schema if historical else publication_schema(schema))


def output_contract_error(record: dict, *, historical: bool = False) -> str | None:
    """Check the planned scenario before treating its output as reviewable evidence."""
    output = record.get("output")
    if output is None and not record.get("result_id"):
        return None
    scenario = record["case"]["scenario_id"]
    if isinstance(output, dict):
        if historical and scenario.startswith("acceptance_builder.") and "document" in output:
            # The archived document shape predates the current stored-result schema.
            return None
        if scenario == DRAFT and not historical and not {"issues", "questions"} <= output.keys():
            return f"{scenario} output requires both issues and questions"
    error = next(_output_validator(scenario, historical=historical).iter_errors(output), None)
    if error is not None:
        return f"{scenario} output violates {error.validator} at {error.json_path}"
    if "issues" in output:
        issue_count = len(output["issues"])
        for index, question in enumerate(output["questions"]):
            if not 0 <= question["source_issue_index"] < issue_count:
                return (
                    f"{scenario} output at $.questions[{index}].source_issue_index "
                    f"must reference an issue (expected 0 <= index < {issue_count})"
                )
    return None


def review_template(record: dict, *, historical: bool = False) -> dict:
    decision_field = DECISION_FIELDS.get(record["case"].get("family"))
    output = record.get("output") or {}
    fields = {} if output_contract_error(record, historical=historical) else authored_fields(output)
    return {
        "evidence_sha256": digest(record),
        **({decision_field: None} if decision_field else {}),
        "reviewer": "",
        "fields": dict.fromkeys(fields),
        "criteria": {question: None for question in record["case"]["criteria"]},
        "notes": "",
    }


def primary_language(tag: object) -> str | None:
    """Accept the AB contract's language tags, matching the presenter's primary subtag."""
    if not isinstance(tag, str) or not re.fullmatch(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*", tag):
        return None
    return tag.split("-")[0].lower()


def analysis_language_matches(record: dict, *, historical: bool = False) -> bool:
    output = record.get("output")
    if not output or not record["case"]["scenario_id"].startswith("acceptance_builder."):
        return True
    values = output.get("extracted", {}).get("values", {})
    # Historical document outputs must also pass the generate_document ledger check below.
    if historical and "document" in output and "analysis_language" not in values:
        return True
    actual = primary_language(values.get("analysis_language"))
    expected = primary_language(record["case"].get("expected_language"))
    return actual is not None and expected is not None and actual == expected


def review_status(record: dict, review: dict, *, historical: bool = False) -> str:
    """Grade current evidence. Historical contracts require an explicit archive replay."""
    if review.get("evidence_sha256") != digest(record):
        raise ValueError("review does not belong to this evidence")
    if record.get("error") or record.get("evidence_error") or output_contract_error(
        record, historical=historical
    ):
        return "FAIL"
    expected = review_template(record, historical=historical)
    decisions = []
    for group in ("fields", "criteria"):
        if set(review.get(group, {})) != set(expected[group]):
            raise ValueError(f"incomplete or unexpected review {group}")
        decisions += list(review[group].values())
    if any(value is not None and type(value) is not bool for value in decisions):
        raise ValueError("review decisions must be true, false or null")
    if False in decisions or not analysis_language_matches(record, historical=historical):
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
        DRAFT: {"extract", "detect_issues", "generate_questions"},
        CHECK: {"extract", "compare"},
    }[scenario]
    output = record["output"]
    if historical and scenario.startswith("acceptance_builder.") and "document" in output:
        expected_steps.add("generate_document")
    if historical and scenario == DRAFT and "issues" not in output:
        expected_steps -= {"detect_issues", "generate_questions"}
    elif "generate_questions" in expected_steps and not output["issues"]:
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
    family = record["case"].get("family")
    if family in DECISION_FIELDS:
        if "detect_issues" not in expected_steps:
            return "FAIL"
        language = primary_language(record["case"].get("expected_language"))
        if language not in {"ru", "en", "es"}:
            return "FAIL"
        eligible = decision_questions(output, family, language)
        if not eligible:
            return "FAIL"
        field = DECISION_FIELDS[family]
        quotes = [q["question"] for q in eligible]
        if field in review or family == "feasibility":
            if review.get(field) not in quotes:
                return "PENDING"
        # Earlier contradiction reviews recorded the exact linked quotation at the end of notes.
        elif not any(quote and review.get("notes", "").endswith(quote) for quote in quotes):
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
    record["evidence_error"] = output_contract_error(record) or record["evidence_error"]
    return record


def draft_risk_cases() -> list[dict]:
    suite = json.loads(
        (ROOT / "tests/fixtures/acceptance_builder_eval/draft_risks_questions.json").read_text(
            encoding="utf-8"
        )
    )
    cases = []
    for case in suite["cases"]:
        briefs = {case["language"]: case["input"]["brief_text"], **case.get("translations", {})}
        for lang, brief in briefs.items():
            cases.append(
                {
                    "id": f"{case['id'].rsplit('-', 1)[0]}-{lang.upper()}",
                    "scenario_id": "acceptance_builder.draft_v1",
                    "family": case["checks"],
                    "expected_language": lang,
                    "input": {"brief_text": brief},
                    "criteria": suite["review_rubric"][case["checks"]],
                }
            )
    return cases


def _is_any761_archive_case(case: dict) -> bool:
    prefix = {DRAFT: "ANY761-AB-D", CHECK: "ANY761-AB-C"}.get(case["scenario_id"])
    return (
        prefix is not None
        and re.fullmatch(rf"{prefix}-(?:RU|EN|ES)-(?:basic|weak|mixed|override)", case["id"])
        is not None
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--api-url", required=True)
    run.add_argument("--project", required=True, type=_parse_compose_project)
    run.add_argument("--suite", choices=("language", "draft-risks"), default="language")
    run.add_argument("--scenario", choices=SCENARIOS, required=True)
    run.add_argument("--family", help="Filter by a family in the selected suite and scenario")
    run.add_argument("--repeats", type=int, default=3)
    run.add_argument("--timeout", type=int, default=240)
    run.add_argument("--out", type=Path, required=True)
    report = commands.add_parser("report")
    report.add_argument("--out", type=Path, required=True)
    report.add_argument(
        "--historical-any-761",
        action="store_true",
        help="Read an unversioned ANY-761 Acceptance Builder archive under its original contract",
    )
    args = parser.parse_args()
    if args.command == "report":
        manifest = json.loads(evidence_path(args.out, "manifest.json").read_text(encoding="utf-8"))
        historical = args.historical_any_761
        if historical:
            cases = manifest.get("cases", [])
            if "evidence_contract" in manifest or not cases or not all(
                _is_any761_archive_case(case) for case in cases
            ):
                report.error("--historical-any-761 requires an unversioned ANY-761 AB archive")
        statuses = []
        for key in manifest["runs"]:
            reason = None
            path = evidence_path(args.out, f"{key}.json")
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
                reason = output_contract_error(record, historical=historical)
                if reason or record.get("error") or record.get("evidence_error"):
                    status = "FAIL"
                else:
                    review_path = evidence_path(args.out, f"{key}.review.json")
                    status = (
                        review_status(
                            record,
                            json.loads(review_path.read_text(encoding="utf-8")),
                            historical=historical,
                        )
                        if review_path.exists()
                        else "PENDING"
                    )
            statuses.append(status)
            print(f"{key}: {status}" + (f" ({reason})" if reason else ""))
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
    cases = (
        draft_risk_cases()
        if args.suite == "draft-risks"
        else json.loads(SUITE.read_text(encoding="utf-8"))["cases"]
    )
    cases = [case for case in cases if case["scenario_id"] == args.scenario]
    if not cases:
        parser.error("no cases match the selected suite and scenario")
    if args.family is not None:
        families = sorted({case["family"] for case in cases})
        if args.family not in families:
            parser.error(
                f"unknown family for {args.suite}/{args.scenario}; choose from {', '.join(families)}"
            )
        cases = [case for case in cases if case["family"] == args.family]
    runs = [f"{case['id']}--{attempt}" for attempt in range(1, args.repeats + 1) for case in cases]
    for key in runs:
        evidence_path(args.out, f"{key}.json")
    snapshot = json.loads(_docker(args.project, "platform-worker", WORKER_PYTHON, "-c", SNAPSHOT))
    args.out.mkdir(parents=True, exist_ok=False)
    write_json(
        evidence_path(args.out, "manifest.json"),
        {
            "cases": cases,
            "runs": runs,
            "snapshot": snapshot,
            "source": _git_state(),
            "evidence_contract": "current",
        },
    )
    for attempt in range(1, args.repeats + 1):
        for case in cases:
            key = f"{case['id']}--{attempt}"
            record = collect(args, case, attempt, snapshot)
            write_json(evidence_path(args.out, f"{key}.json"), record)
            write_json(
                evidence_path(args.out, f"{key}.review.json"), review_template(record)
            )
            error = record["error"] or record["evidence_error"]
            if error:
                print(f"{key}: ERROR ({error})", flush=True)
                return 1
            print(f"{key}: collected; review pending", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
