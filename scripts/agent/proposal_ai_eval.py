"""ProposalAI evaluation: collect outputs, check what a text match can prove, accept on human verdicts.

Three steps, each its own command (the quick-check environment, because the number check is imported
from the A06 validator):

    .quick-check-venv/bin/python scripts/agent/proposal_ai_eval.py run --api-url http://localhost:8000 \
        --orders tests/fixtures/proposal_ai_eval/terms.json --series luna-medium --out runs.jsonl [--repeats 3] \
        [--compose-project anytoolai-xxxxxxxx]
    .quick-check-venv/bin/python scripts/agent/proposal_ai_eval.py review --suite suite.json --reviewer <id>
    .quick-check-venv/bin/python scripts/agent/proposal_ai_eval.py accept --suite suite.json

`run` sends every order through a running platform-api + worker (one fresh guest per run, the guest
quota is lifetime) and appends one record per run to `--out`: input, full output, session, timing and,
with `--compose-project` (a local dev-live stack), the prompt hashes and model read from the running
worker and every provider call with its cost. A failed or timed-out run is recorded too. Exit code 0
when the records are written, whatever the model did; 1 only when they cannot be.

Formal checks need no judgement and are recomputed from the stored output by `review` and `accept`:
placeholders, meta phrases, lists or headings, length, a required literal (`must`), a forbidden amount
(`must_not`, a critical error), the language (a clearly wrong language makes the run unusable, an
unclear one leaves it pending), long dashes (a warning). A number absent from the order and the
positioning is shown to the reviewer, never decided here.

Meaning is never decided by a regular expression. Each order lists `criteria`, questions a human
answers yes, no or unknown for every output (see tests/fixtures/proposal_ai_eval/qa_cases.json), and
every run also has `no-critical-error`. Verdicts live in a JSONL file next to the runs, one line per run
and criterion with the agent's `suggestion` and the human `decision` (null until a person confirms
it); the last line for a run and criterion wins, and it counts only for the answer whose hash it
carries. `review` walks the reviewer through every open decision.

`accept` is offline and deterministic. A run is PASS (usable), FAIL (unusable: runtime error, formal
violation or a criterion confirmed "no") or PENDING; a confirmed "no" on a critical criterion or a
forbidden amount is a critical error. The suite is FAIL on any critical error, a group below its
threshold or a series median latency above the limit; otherwise PENDING while a decision is open, a run
is not verified or a group has no approved threshold; otherwise PASS. Exit code 0 only for PASS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import subprocess
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import re2

from anytoolai_platform_actions.structured_llm.cross_validation.persuasive_text import numbers_absent_from_context

ORDERS_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "proposal_ai_eval" / "orders.json"
# RE2, like the A06 validator that runs the same placeholder patterns (`\pL` is any letter there).
_RE2_IGNORE_CASE = re2.Options()
_RE2_IGNORE_CASE.case_sensitive = False
PLACEHOLDER = re2.compile(
    r"\[[^\]\n]{1,80}\]|\{[^{}\n]{1,80}\}|\{\{|\}\}|\byour name\b|<[^\s\d<>=][^<>\n]{0,79}>|%\pL[\pL\pN_.]{0,39}%",
    _RE2_IGNORE_CASE,
)
META = re.compile(
    r"based on the information i(?:.m| am| have| was| can)|truthfully|as an ai (?:language )?model"
    r"|as an ai,? i (?:can|cannot|can.?t|am|do|don.?t)\b|my listed experience|haven.t specified"
    r"|в описании моего опыта|не буду заявлять",
    re.IGNORECASE,
)
LONG_DASH = re.compile(r"—| – ")
LIST_OR_HEADING_LINE = re.compile(r"^\s*(#{1,6}\s|[-*+•]\s|\d+[.)]\s)")
MAX_WORDS = 250


def _has_invented_number(text: str, *sources: str) -> bool:
    # The validator's own reading of numbers; each source is a separate string so the end of one field
    # and the start of the next are never one number.
    return bool(numbers_absent_from_context(text, list(sources)))


def _cyrillic_share(value: str) -> float:
    letters = [char for char in value if char.isalpha()]
    return sum("Ѐ" <= char <= "ӿ" for char in letters) / len(letters) if letters else 0.0


# Function words that are frequent in one language and rare in the others. ANY-631 saw whole English
# orders answered in Spanish, Dutch and German; a Cyrillic share alone calls all of those "en".
_FUNCTION_WORDS = {
    "en": {"the", "and", "to", "of", "your", "you", "for", "is", "are", "with", "not", "i", "my", "this", "will"},
    "es": {"el", "la", "los", "las", "que", "de", "para", "con", "una", "por", "del", "su", "tu", "y", "no", "es"},
    "de": {"der", "die", "das", "und", "ich", "ist", "nicht", "mit", "für", "ein", "eine", "zu", "sie", "den", "auf"},
    "nl": {"de", "het", "een", "en", "ik", "is", "niet", "met", "voor", "van", "uw", "op", "te", "dat", "zijn"},
    "fr": {"le", "la", "les", "et", "je", "est", "pas", "avec", "pour", "un", "une", "des", "du", "vous", "votre"},
    "it": {"il", "la", "e", "di", "che", "per", "con", "non", "un", "una", "sono", "del", "della", "gli", "suo"},
    "pt": {"o", "a", "os", "as", "e", "de", "que", "para", "com", "não", "um", "uma", "do", "da", "seu"},
}


def detect_language(text: str) -> str | None:
    """`ru` for a mainly Cyrillic text, otherwise the language whose function words lead clearly;
    None when no language leads clearly (the caller reports it as unverified, never as correct)."""
    if _cyrillic_share(text) > 0.5:
        return "ru"
    words = re.findall(r"[^\W\d_]+", text.lower())
    if len(words) < 20:
        return None
    hits = sorted(((sum(word in vocab for word in words), lang) for lang, vocab in _FUNCTION_WORDS.items()), reverse=True)
    (best, lang), (second, _) = hits[0], hits[1]
    return lang if best >= 0.12 * len(words) and best >= 1.5 * second else None


def _is_heading_like(line: str) -> bool:
    stripped = line.strip()
    return 0 < len(stripped) <= 60 and stripped[-1] not in ".!?:;,…" and len(stripped.split()) <= 8


def check_proposal(
    text: str, gaps: list, order: dict, profile: str, *, expect_language: str | None = None
) -> dict[str, bool | int]:
    """Formal checks (True means violated) plus the word count. `expect_language` overrides the
    order's own (an explicit `language`). A language the detector cannot tell apart is reported as
    `language_unverified`, never as correct."""
    lines = [line for line in text.splitlines() if line.strip()]
    language = detect_language(text)
    expected = (expect_language or order["expect_language"]).split("-")[0]
    return {
        "wrong_language": language is not None and language != expected,
        "language_unverified": language is None,
        "placeholder": bool(PLACEHOLDER.search(text)),
        "meta_phrase": bool(META.search(text)),
        "invented_number": _has_invented_number(text, order["task_text"], profile),
        "list_or_heading": any(LIST_OR_HEADING_LINE.match(line) for line in lines)
        or (len(lines) > 1 and any(_is_heading_like(line) for line in lines)),
        "long_dash": bool(LONG_DASH.search(text)),
        "too_long": len(text.split()) > MAX_WORDS,
        "missing_gap": bool(order.get("expect_gap")) and not gaps,
        "missing_required": any(not re.search(p, text, re.IGNORECASE) for p in order.get("must", [])),
        "forbidden_present": any(re.search(p, text, re.IGNORECASE) for p in order.get("must_not", [])),
        "words": len(text.split()),
    }


# What each formal finding does to a run. `invented_number` and `language_unverified` are not here:
# the first is a hint for the reviewer, the second leaves the run pending.
CRITICAL_CHECKS = ("forbidden_present",)
UNUSABLE_CHECKS = (
    "wrong_language", "placeholder", "meta_phrase", "list_or_heading", "too_long", "missing_gap", "missing_required",
)
WARNING_CHECKS = ("long_dash",)

NO_CRITICAL_ERROR = {
    "id": "no-critical-error",
    "kind": "requirement",
    "critical": True,
    "question": "Is there no unagreed price or term stated as accepted, no invented commitment or amount, no lost "
    "mandatory condition (exclusion, revision limit, paid changes, start prerequisite) and no promise of excluded work?",
}


def criteria_for(order: dict) -> list[dict]:
    return [NO_CRITICAL_ERROR, *order.get("criteria", [])]


def answer_hash(output: dict) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(output, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def latest_verdicts(rows: list[dict]) -> dict[tuple[str, str], dict]:
    return {(row["run_id"], row["criterion_id"]): row for row in rows}


def formal_checks(run: dict, order: dict) -> dict[str, bool | int]:
    output = run["output"]
    return check_proposal(
        output["text"], output.get("gaps", []), order, run["input"]["freelancer_positioning"],
        expect_language=run["input"].get("language"),
    )


def judge_run(run: dict, order: dict, verdicts: dict[tuple[str, str], dict]) -> dict:
    """usable / critical are True, False or None (not established yet)."""
    fails, critical_fails, pending, warnings = [], [], [], []
    if run["runtime_status"] != "ok":
        fails.append(f"runtime: {run['runtime_status']}: {run.get('error') or ''}".strip())
    if not run.get("prompt_sha256") or not run.get("model") or not run.get("reasoning_effort"):
        pending.append("prompt version or model not read from the running stack")
    critical_open = False
    if run.get("output"):
        checks = formal_checks(run, order)
        fails += [name for name in UNUSABLE_CHECKS if checks[name]]
        critical_fails += [name for name in CRITICAL_CHECKS if checks[name]]
        warnings += [name for name in WARNING_CHECKS if checks[name]]
        if checks["language_unverified"]:
            pending.append("language not detected")
        digest = answer_hash(run["output"])
        for criterion in criteria_for(order):
            row = verdicts.get((run["run_id"], criterion["id"]))
            decision = row.get("decision") if row and row.get("answer_hash") == digest else None
            answer = decision["answer"] if decision else None
            if answer == "no":
                (critical_fails if criterion["critical"] else fails).append(
                    f"{criterion['id']}: {decision.get('reason') or 'no'}"
                )
            elif answer != "yes":
                pending.append(f"{criterion['id']}: {'unknown' if answer else 'not confirmed'}")
                critical_open = critical_open or criterion["critical"]
    elif run["runtime_status"] == "ok":
        fails.append("no output")
    usable = False if fails or critical_fails else (None if pending else True)
    critical = True if critical_fails else (None if critical_open else False)
    status = {True: "PASS", False: "FAIL", None: "PENDING"}[usable]
    return {"status": status, "usable": usable, "critical": critical, "reasons": critical_fails + fails + pending,
            "warnings": warnings}


def load_suite(path: Path) -> tuple[dict, dict[str, dict], list[dict], dict[tuple[str, str], dict]]:
    suite = json.loads(path.read_text(encoding="utf-8"))
    orders = {}
    for orders_path in suite["orders"]:
        fixture = json.loads((path.parent / orders_path).read_text(encoding="utf-8"))
        for order in fixture["orders"]:
            orders[order["id"]] = order
    runs = read_jsonl(path.parent / suite["runs"])
    return suite, orders, runs, latest_verdicts(read_jsonl(path.parent / suite["verdicts"]))


def accept(suite: dict, orders: dict[str, dict], runs: list[dict], verdicts: dict) -> tuple[str, list[str]]:
    judged = [(run, judge_run(run, orders[run["case_id"]], verdicts)) for run in runs]
    fails, pending, lines = [], [], []
    critical = [run["run_id"] for run, j in judged if j["critical"] is True]
    if critical:
        fails.append(f"critical errors: {', '.join(critical)}")
    if any(j["critical"] is None for _, j in judged):
        pending.append("critical errors not ruled out in every run")
    groups: dict[tuple[str, str], list[dict]] = {}
    for run, j in judged:
        groups.setdefault((run["series"], run["case_id"]), []).append(j)
    lines += ["| Series | Case | Runs | Usable | Unusable | Pending | Threshold | Group |", "|---|---|---|---|---|---|---|---|"]
    for (series, case_id), js in sorted(groups.items()):
        usable = sum(j["usable"] is True for j in js)
        unusable = sum(j["usable"] is False for j in js)
        rule = next((t for t in suite.get("thresholds", []) if t["series"] == series and case_id in t["cases"]), None)
        if rule is None:
            verdict, threshold = "PENDING", "none approved"
            pending.append(f"{series} {case_id}: no approved threshold")
        else:
            threshold = f"{rule['min_usable']}/{rule['of']}"
            if len(js) != rule["of"]:
                verdict = "PENDING"
                pending.append(f"{series} {case_id}: {len(js)} runs, the threshold is for {rule['of']}")
            elif usable >= rule["min_usable"]:
                verdict = "PASS"
            elif len(js) - unusable < rule["min_usable"]:
                verdict = "FAIL"
                fails.append(f"{series} {case_id}: {usable} usable, needs {threshold}")
            else:
                verdict = "PENDING"
                pending.append(f"{series} {case_id}: threshold {threshold} not decided yet")
        lines.append(f"| {series} | {case_id} | {len(js)} | {usable} | {unusable} | {len(js) - usable - unusable} | {threshold} | {verdict} |")
    lines += ["", "| Series | Median latency, s | Limit, s |", "|---|---|---|"]
    for series in sorted({run["series"] for run in runs}):
        latencies = [run["latency_ms"] for run in runs if run["series"] == series and run.get("latency_ms") is not None]
        median = statistics.median(latencies) if latencies else None
        limit = suite["max_median_latency_ms"]
        if median is None:
            pending.append(f"{series}: no latency recorded")
        elif median > limit:
            fails.append(f"{series}: median latency {median / 1000:.1f} s above {limit / 1000:.0f} s")
        lines.append(f"| {series} | {'-' if median is None else f'{median / 1000:.1f}'} | {limit / 1000:.0f} |")
    lines += ["", "Runs that are not PASS or carry a warning:", ""]
    for run, j in judged:
        if j["status"] != "PASS" or j["warnings"]:
            notes = "; ".join(j["reasons"] + [f"warning: {w}" for w in j["warnings"]])
            lines.append(f"- {j['status']}{' critical' if j['critical'] else ''} `{run['run_id']}`: {notes}")
    status = "FAIL" if fails else ("PENDING" if pending else "PASS")
    head = [f"# Suite {suite['id']}: {status}", ""] + [f"- FAIL: {x}" for x in fails] + [f"- PENDING: {x}" for x in sorted(set(pending))]
    return status, head + [""] + lines


def _request(url: str, *, payload: dict | None = None, method: str = "GET") -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Accept": "application/json", **({"Content-Type": "application/json"} if data else {})}
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method=method), timeout=30) as response:
        return json.loads(response.read())


PROMPTS = Path("packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products/proposal_ai/prompts")


def _docker(project: str, service: str, *command: str) -> str:
    return subprocess.run(
        ["docker", "exec", f"{project}-{service}-1", *command], check=True, capture_output=True, text=True
    ).stdout


def read_stack(project: str) -> dict:
    """The prompt hashes and the model entries as the running worker has them."""
    hashes = {}
    for line in _docker(project, "platform-worker", "sh", "-c", f"sha256sum /app/{PROMPTS}/*.md").splitlines():
        digest, path = line.split()
        hashes[Path(path).name] = digest
    import yaml  # noqa: PLC0415 - only `run --compose-project` needs it

    router = yaml.safe_load(_docker(project, "platform-worker", "cat", "/app/configs/kernel/litellm_router.yaml"))
    models = {entry["model_name"]: entry["litellm_params"] for entry in router["model_list"]}
    return {"prompt_sha256": hashes, "models": models}


def read_provider_calls(project: str, session_id: str) -> list[dict]:
    # ponytail: dev-live database credentials; another stack needs its own.
    sql = (
        "select coalesce(json_agg(row_to_json(c) order by c.created_at), '[]') from (select step_id, model, gateway_model,"
        " semantic_attempt_index, status, latency_ms, estimated_cost, created_at from platform.provider_calls"
        f" where scenario_session_id = '{session_id}') c"
    )
    rows = json.loads(_docker(project, "postgres", "psql", "-U", "produser", "-d", "proddb", "-Atc", sql))
    for row in rows:
        row.pop("created_at")
    return rows


def _git_state() -> dict:
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout.strip())
    return {"git_sha": sha or None, "git_dirty": dirty}


def run_once(args: argparse.Namespace, order: dict, attempt: int, profile: str, stack: dict | None) -> dict:
    scenario_input = {"task_text": order["task_text"], "freelancer_positioning": profile, "tone": order.get("tone", args.tone)}
    language = order.get("language", args.language)
    if language:
        scenario_input["language"] = language
    record = {
        "run_id": f"{args.series}-{order['id']}-{attempt}-{uuid.uuid4().hex[:8]}", "series": args.series,
        "case_id": order["id"], "attempt": attempt, "channel": "api", "session_id": None,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **_git_state(),
        "prompt_sha256": stack and stack["prompt_sha256"], "model": None, "reasoning_effort": None,
        "input": scenario_input, "output": None, "runtime_status": "ok", "error": None,
        "latency_ms": None, "estimated_cost": None, "provider_calls": None,
    }
    started = time.monotonic()
    try:
        guest_id = _request(f"{args.api_url}/v1/identity/guest", method="POST")["guest_id"]
        start = _request(
            f"{args.api_url}/v1/products/proposal_ai/scenarios/proposal_ai.generate_v1/start",
            payload={"frontend_id": "web_mirror", "guest_id": guest_id, "input": scenario_input},
            method="POST",
        )
        record["session_id"] = start["scenario_session_id"]
        session_url = f"{args.api_url}/v1/scenario-sessions/{record['session_id']}"
        while True:
            session = _request(session_url)
            if session["status"] == "completed":
                record["output"] = _request(f"{args.api_url}/v1/results/{session['result_artifact_id']}")["output"]
                break
            if session["status"] == "failed":
                raise RuntimeError(f"session failed: {session.get('status')}")
            if time.monotonic() - started > args.timeout:
                raise TimeoutError(f"no result after {args.timeout:.0f} s")
            time.sleep(1.0)
    except (OSError, RuntimeError, TimeoutError, KeyError, ValueError) as exc:
        record["runtime_status"], record["error"] = "error", str(exc)
    record["latency_ms"] = round((time.monotonic() - started) * 1000)
    if stack and record["session_id"]:
        calls = read_provider_calls(args.compose_project, record["session_id"])
        record["provider_calls"] = calls
        costs = [call["estimated_cost"] for call in calls]
        record["estimated_cost"] = sum(costs) if costs and None not in costs else None
        aliases = {call["gateway_model"] for call in calls}
        if len(aliases) == 1:
            params = stack["models"].get(aliases.pop(), {})
            record["model"], record["reasoning_effort"] = params.get("model"), params.get("reasoning_effort")
    return record


def command_run(args: argparse.Namespace) -> int:
    fixture = json.loads(args.orders.read_text(encoding="utf-8"))
    stack = read_stack(args.compose_project) if args.compose_project else None
    try:
        with args.out.open("a", encoding="utf-8") as out:
            for attempt in range(1, args.repeats + 1):
                for order in fixture["orders"]:
                    profile = order.get("freelancer_positioning", fixture.get("freelancer_positioning"))
                    record = run_once(args, order, attempt, profile, stack)
                    out.write(json.dumps(record, ensure_ascii=False) + "\n")
                    out.flush()
                    print(f"{record['run_id']} {record['runtime_status']} {record['latency_ms']} ms", flush=True)
    except OSError as exc:
        print(f"cannot write {args.out}: {exc}", file=sys.stderr)
        return 1
    return 0


def command_review(args: argparse.Namespace) -> int:
    suite, orders, runs, verdicts = load_suite(args.suite)
    path = args.suite.parent / suite["verdicts"]
    shown = None
    for run in runs:
        if not run.get("output"):
            continue
        order, digest = orders[run["case_id"]], answer_hash(run["output"])
        for criterion in criteria_for(order):
            row = verdicts.get((run["run_id"], criterion["id"]))
            if row and row.get("answer_hash") == digest and row.get("decision"):
                continue
            suggestion = row.get("suggestion") if row and row.get("answer_hash") == digest else None
            if shown != run["run_id"]:
                shown = run["run_id"]
                print(f"\n=== {run['run_id']} ({run['model']}, {run['reasoning_effort']})\n{run['output']['text']}\n")
                if formal_checks(run, order)["invented_number"]:
                    print("Note: a number that is not in the order or the positioning.")
            print(f"\n[{criterion['id']}{', critical' if criterion['critical'] else ''}] {criterion['question']}")
            if suggestion:
                print(f"Agent: {suggestion['answer']} - {suggestion.get('reason', '')} | quote: {suggestion.get('quote', '')}")
            answer = input("y = yes, n = no, u = unknown, s = skip, q = quit > ").strip().lower()
            if answer == "q":
                return 0
            if answer not in ("y", "n", "u"):
                continue
            reason = input("Reason > ").strip() if answer in ("n", "u") else (suggestion or {}).get("reason")
            new = {
                "run_id": run["run_id"], "criterion_id": criterion["id"], "answer_hash": digest, "suggestion": suggestion,
                "decision": {"answer": {"y": "yes", "n": "no", "u": "unknown"}[answer], "reason": reason,
                             "reviewer": args.reviewer,
                             "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
            }
            with path.open("a", encoding="utf-8") as out:
                out.write(json.dumps(new, ensure_ascii=False) + "\n")
    return 0


def command_accept(args: argparse.Namespace) -> int:
    status, lines = accept(*load_suite(args.suite))
    print("\n".join(lines))
    return 0 if status == "PASS" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="collect outputs from a running stack")
    run.add_argument("--api-url", required=True)
    run.add_argument("--orders", type=Path, default=ORDERS_PATH, help="order set, default: orders.json")
    run.add_argument("--series", required=True, help="the configuration under test, for example luna-medium")
    run.add_argument("--out", type=Path, required=True, help="runs JSONL, appended to")
    run.add_argument("--repeats", type=int, default=1)
    run.add_argument("--tone", default="warm", choices=["neutral", "warm", "firm"])
    run.add_argument("--language", help="explicit proposal language, default: the task's language")
    run.add_argument("--timeout", type=float, default=120.0)
    run.add_argument("--compose-project", help="local stack to read the prompt hashes, model and provider calls from")
    review = commands.add_parser("review", help="confirm or correct every open verdict")
    review.add_argument("--suite", type=Path, required=True)
    review.add_argument("--reviewer", required=True, help="who confirms, recorded in every decision")
    accept_parser = commands.add_parser("accept", help="offline suite verdict from runs and confirmed verdicts")
    accept_parser.add_argument("--suite", type=Path, required=True)
    args = parser.parse_args(argv)
    return {"run": command_run, "review": command_review, "accept": command_accept}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
