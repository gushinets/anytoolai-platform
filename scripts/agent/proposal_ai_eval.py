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
carries. `review` walks the reviewer through every open decision; `--redo RUN_ID/CRITERION_ID` decides one again. The agent's reason is copied
only when the decision matches the agent's answer; otherwise the reviewer gives their own.

The suite's `program` is the mandatory test plan: per series and case the attempts, the usable results
required, and the channel, model, reasoning and prompt hashes every run must carry. A run that does not
match its group (an API run for a `web_form` group, no web form evidence: UI outcome, UI time and a
browser trace in `origin`) is evidence that is not there, never a pass; a web form run whose UI showed
an error is a failure whatever the server produced later. A verdict counts only for the answer, the
input and the criterion it was made for (their hashes); change one and the question is open again.

`accept` is offline and deterministic. A run is PASS (usable), FAIL (unusable: runtime error, formal
violation or a criterion confirmed "no") or PENDING; a confirmed "no" on a critical criterion or a
forbidden amount is a critical error, and a critical "no" next to a "yes" on `no-critical-error` is
reported as a contradiction. A group is FAIL when its threshold can no longer be reached, PENDING while
a run is missing, not verified or undecided, PASS only when every attempt is in, decided and enough
are usable. The suite is FAIL on any critical error, a failed group or a series median latency above the
limit; otherwise PENDING while anything is open; otherwise PASS. Exit code 0 only for PASS, 1 for FAIL
or PENDING, 2 for a corrupt suite (duplicate or unplanned runs, a broken program).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import subprocess
import sys
import time
import urllib.request
import uuid
import zipfile
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
GAP_MIN_WORDS = 6  # a gap description is one short sentence


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
    "en": {"the", "and", "to", "of", "your", "you", "for", "is", "are", "with", "not", "i", "my", "this", "will", "no", "in", "an", "as", "at", "be", "by", "on", "or", "it"},
    "es": {"el", "la", "los", "las", "que", "de", "para", "con", "una", "por", "del", "su", "tu", "y", "no", "es", "se", "está", "en", "un", "al", "lo"},
    "de": {"der", "die", "das", "und", "ich", "ist", "nicht", "mit", "für", "ein", "eine", "zu", "sie", "den", "auf"},
    "nl": {"de", "het", "een", "en", "ik", "is", "niet", "met", "voor", "van", "uw", "op", "te", "dat", "zijn"},
    "fr": {"le", "la", "les", "et", "je", "est", "pas", "avec", "pour", "un", "une", "des", "du", "vous", "votre"},
    "it": {"il", "la", "e", "di", "che", "per", "con", "non", "un", "una", "sono", "del", "della", "gli", "suo"},
    "pt": {"o", "a", "os", "as", "e", "de", "que", "para", "com", "não", "um", "uma", "do", "da", "seu"},
}


def detect_language(text: str, min_words: int = 20) -> str | None:
    """`ru` for a mainly Cyrillic text, otherwise the language whose function words lead clearly;
    None when no language leads clearly (the caller reports it as unverified, never as correct)."""
    if _cyrillic_share(text) > 0.5:
        return "ru"
    words = re.findall(r"[^\W\d_]+", text.lower())
    if len(words) < min_words:
        return None
    hits = sorted(((sum(word in vocab for word in words), lang) for lang, vocab in _FUNCTION_WORDS.items()), reverse=True)
    (best, lang), (second, _) = hits[0], hits[1]
    return lang if best >= 2 and best >= 0.12 * len(words) and best >= 1.5 * second else None


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
    gap_expected = order.get("expect_gaps_language")
    gap_languages = [detect_language(gap["description"], GAP_MIN_WORDS) for gap in gaps] if gap_expected else []
    return {
        "wrong_language": language is not None and language != expected,
        "wrong_gaps_language": any(found not in (None, gap_expected) for found in gap_languages),
        "language_unverified": language is None or None in gap_languages,
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


# What each formal finding does to a run. `invented_number` is not here: it is a hint for the reviewer.
CRITICAL_CHECKS = ("forbidden_present",)
UNUSABLE_CHECKS = (
    "wrong_language", "wrong_gaps_language", "placeholder", "meta_phrase", "list_or_heading", "too_long",
    "missing_gap", "missing_required",
)
WARNING_CHECKS = ("long_dash",)

# The ANY-631 critical violations; a criterion is critical exactly when it names one of them.
CRITICAL_VIOLATIONS = (
    "unagreed_term_accepted", "invented_amount_or_commitment", "lost_mandatory_condition", "promised_excluded_work",
)
NO_CRITICAL_ERROR = {
    "id": "no-critical-error",
    "kind": "requirement",
    "critical": True,
    "question": "Is there no unagreed price or term stated as accepted, no invented commitment or amount, no lost "
    "mandatory condition (exclusion, revision limit, paid changes, start prerequisite) and no promise of excluded work?",
}
LANGUAGE_CONFIRMED = "language-confirmed"
WEB_FORM = "web_form"


class SuiteError(ValueError):
    """The suite or its runs are corrupt: no verdict can be given."""


def criteria_for(order: dict, run: dict | None = None) -> list[dict]:
    """The order's criteria plus the general one; a run whose language the detector cannot tell also
    gets a question for the reviewer."""
    criteria = [NO_CRITICAL_ERROR, *order.get("criteria", [])]
    if run and run.get("output") and formal_checks(run, order)["language_unverified"]:
        criteria.append({
            "id": LANGUAGE_CONFIRMED, "kind": "requirement", "critical": False,
            "question": f"Is the proposal text in {_expected_language(run, order)} and is every gap description in "
            f"{order.get('expect_gaps_language', 'the freelancer positioning language')}?",
        })
    return criteria


def _expected_language(run: dict, order: dict) -> str:
    return (run["input"].get("language") or order["expect_language"]).split("-")[0]


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def answer_hash(output: dict) -> str:
    return _digest(output)


def input_hash(run: dict) -> str:
    return _digest(run["input"])


def criterion_hash(criterion: dict) -> str:
    return _digest({**{key: criterion[key] for key in ("id", "kind", "critical", "question")},
                    "violation_type": criterion.get("violation_type")})


def case_input(order: dict) -> dict:
    """The whole input a run of this case must carry: no key more, no key less."""
    return {key: order[key] for key in ("task_text", "freelancer_positioning", "tone", "language") if key in order}


def case_hash(order: dict) -> str:
    """Everything the approval of a case rests on: its input, its literal checks and expected languages,
    and every question asked about it."""
    checks = {key: order.get(key) for key in ("expect_language", "expect_gaps_language", "expect_gap", "must", "must_not")}
    return _digest({"input": case_input(order), "checks": checks,
                    "criteria": sorted(criterion_hash(c) for c in criteria_for(order))})


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def latest_verdicts(rows: list[dict]) -> dict[tuple[str, str], dict]:
    return {(row["run_id"], row["criterion_id"]): row for row in rows}


def verdict_for(run: dict, criterion: dict, verdicts: dict) -> dict | None:
    """The stored row, only when it was made for this answer, this input and this criterion."""
    row = verdicts.get((run["run_id"], criterion["id"]))
    same = row and (row.get("answer_hash"), row.get("input_hash"), row.get("criterion_hash")) == (
        answer_hash(run["output"]), input_hash(run), criterion_hash(criterion)
    )
    if not same:
        return None
    decision = row.get("decision")
    human = decision and all(isinstance(decision.get(key), str) and decision[key].strip() for key in ("reviewer", "reviewed_at"))
    # a decision counts only with a named human reviewer; "agent" is reserved for suggestions
    return row if human and decision["reviewer"].strip().lower() != "agent" else {**row, "decision": None}


def formal_checks(run: dict, order: dict) -> dict[str, bool | int]:
    output = run["output"]
    return check_proposal(
        output["text"], output.get("gaps", []), order, run["input"]["freelancer_positioning"],
        expect_language=run["input"].get("language"),
    )


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def evidence_problems(run: dict, group: dict, base: Path | None = None) -> list[str]:
    """What the program requires of a run's origin and configuration; any mismatch means the run is not
    the evidence the group asks for. The browser artifact is read from disk and its hash compared."""
    problems = [
        f"{field} is {run.get(field)!r}, the program requires {group[field]!r}"
        for field in ("channel", "model", "reasoning_effort", "prompt_sha256")
        if run.get(field) != group[field]
    ]
    if group["channel"] != WEB_FORM:
        return problems
    origin = run.get("origin") or {}
    if origin.get("ui_outcome") not in ("result", "error") or not _number(origin.get("ui_latency_ms")):
        problems.append("no web form observation (UI outcome and UI time)")
    artifact = (base / origin["trace"]) if base and isinstance(origin.get("trace"), str) else None
    if artifact is None or not artifact.is_file() or not artifact.resolve().is_relative_to(base.resolve()):
        problems.append("browser artifact missing")
    elif hashlib.sha256(artifact.read_bytes()).hexdigest() != origin.get("trace_sha256"):
        problems.append("browser artifact does not match its sha256")
    elif not _is_trace_of(artifact, run.get("session_id")):
        problems.append("browser artifact is not a Playwright trace of this session")
    return problems


def _is_trace_of(path: Path, session_id: str | None) -> bool:
    """A Playwright trace is a ZIP with `trace.trace` and a network log; the network log names the
    session this run started, so the file cannot be another run's or a text file with a hash."""
    if not session_id or not zipfile.is_zipfile(path):
        return False
    with zipfile.ZipFile(path) as trace:
        names = trace.namelist()
        return "trace.trace" in names and any(
            name.endswith(".network") and session_id.encode() in trace.read(name) for name in names
        )


def judge_run(
    run: dict, order: dict, verdicts: dict[tuple[str, str], dict], group: dict | None = None, base: Path | None = None
) -> dict:
    """usable / critical are True, False or None (not established yet)."""
    fails, critical_fails, pending, warnings = [], [], [], []
    if run["runtime_status"] != "ok":
        fails.append(f"runtime: {run['runtime_status']}: {run.get('error') or ''}".strip())
    origin = run.get("origin") or {}
    if origin.get("ui_outcome") not in (None, "result"):
        fails.append(f"web form showed {origin['ui_outcome']} after {origin.get('ui_latency_ms')} ms")
    evidence = [f"evidence: {problem}" for problem in evidence_problems(run, group, base)] if group else []
    critical_open, answers, reopen = False, {}, []
    if run.get("output"):
        checks = formal_checks(run, order)
        fails += [name for name in UNUSABLE_CHECKS if checks[name]]
        critical_fails += [name for name in CRITICAL_CHECKS if checks[name]]
        warnings += [name for name in WARNING_CHECKS if checks[name]]
        wrong_language = checks["wrong_language"] or checks["wrong_gaps_language"]
        for criterion in criteria_for(order, run):
            row = verdict_for(run, criterion, verdicts)
            decision = row.get("decision") if row else None
            answers[criterion["id"]] = answer = decision["answer"] if decision else None
            if criterion["id"] == LANGUAGE_CONFIRMED and answer == "yes" and wrong_language:
                reopen.append(LANGUAGE_CONFIRMED)
                fails.append("language-confirmed is yes but the language check found a wrong language; decide it again")
            if answer == "no":
                (critical_fails if criterion["critical"] else fails).append(
                    f"{criterion['id']}: {decision.get('reason') or 'no'}"
                )
            elif answer != "yes":
                pending.append(f"{criterion['id']}: {'unknown' if answer else 'not confirmed'}")
                critical_open = critical_open or criterion["critical"]
        detailed = [c["id"] for c in criteria_for(order) if c["critical"] and c["id"] != NO_CRITICAL_ERROR["id"] and answers.get(c["id"]) == "no"]
        if detailed and answers.get(NO_CRITICAL_ERROR["id"]) == "yes":
            reopen.append(NO_CRITICAL_ERROR["id"])
            critical_fails.append(f"contradiction: no-critical-error is yes but {', '.join(detailed)} is no; decide it again")
    elif run["runtime_status"] == "ok":
        fails.append("no output")
    # Missing evidence keeps a run PENDING behind any non-critical failure; a critical error stays FAIL.
    status = "FAIL" if critical_fails else "PENDING" if evidence else "FAIL" if fails else "PENDING" if pending else "PASS"
    critical = True if critical_fails else (None if critical_open else False)
    return {"status": status, "usable": {"PASS": True, "FAIL": False, "PENDING": None}[status], "critical": critical,
            "quality_failed": bool(fails or critical_fails), "verified": not evidence, "reasons": critical_fails + fails + evidence + pending,
            "warnings": warnings, "reopen": reopen}


def load_suite(path: Path) -> tuple[dict, dict[str, dict], list[dict], dict[tuple[str, str], dict]]:
    suite = json.loads(path.read_text(encoding="utf-8"))
    orders = {}
    for orders_path in suite["orders"]:
        fixture = json.loads((path.parent / orders_path).read_text(encoding="utf-8"))
        for order in fixture["orders"]:
            orders[order["id"]] = order
    runs = read_jsonl(path.parent / suite["runs"])
    suite["_dir"] = path.parent
    return suite, orders, runs, latest_verdicts(read_jsonl(path.parent / suite["verdicts"]))


def program_groups(suite: dict, orders: dict[str, dict]) -> dict[tuple[str, str], dict]:
    """One group per series and case; a block of the program shares everything but the case."""
    groups: dict[tuple[str, str], dict] = {}
    if not suite.get("program"):
        raise SuiteError("program: nothing is planned")
    for block in suite["program"]:
        group = {**suite.get("defaults", {}), **block}
        missing = {"series", "cases", "attempts", "min_usable", "channel", "model", "reasoning_effort", "prompt_sha256"} - group.keys()
        if missing or not 0 < group["min_usable"] <= group["attempts"]:
            raise SuiteError(f"program block {block.get('series')}: missing {sorted(missing)} or an impossible threshold")
        if not group["cases"]:
            raise SuiteError(f"program block {group['series']}: no cases")
        for case_id in group["cases"]:
            if case_id not in orders:
                raise SuiteError(f"program: {case_id} is not an order of the suite")
            if (group["series"], case_id) in groups:
                raise SuiteError(f"program: {group['series']} {case_id} planned twice")
            groups[(group["series"], case_id)] = group
    for case_id in {key[1] for key in groups}:
        if suite.get("cases", {}).get(case_id) != case_hash(orders[case_id]):
            raise SuiteError(f"case {case_id} is not the one that was approved (its input, checks or questions changed)")
    return groups


def check_runs(runs: list[dict], groups: dict[tuple[str, str], dict], orders: dict[str, dict]) -> None:
    """Raise SuiteError for runs the program does not allow: repeated, unplanned, outside its attempts or
    sent with another input than their case."""
    seen_ids, seen, sessions = set(), set(), set()
    for run in runs:
        key = (run["series"], run["case_id"], run["attempt"])
        group = groups.get(key[:2])
        if run["run_id"] in seen_ids or key in seen:
            raise SuiteError(f"duplicate run {run['run_id']} ({key})")
        if group is None or not 1 <= run["attempt"] <= group["attempts"]:
            raise SuiteError(f"run {run['run_id']} is not in the program ({key})")
        if run["input"] != case_input(orders[run["case_id"]]):
            raise SuiteError(f"run {run['run_id']}: input is not the input of case {run['case_id']}")
        if run["runtime_status"] == "ok" and not run.get("session_id"):
            raise SuiteError(f"run {run['run_id']}: a result without a scenario session")
        if run.get("session_id") in sessions:  # a run that failed before its session started has none
            raise SuiteError(f"run {run['run_id']}: session {run['session_id']} already counted for another run")
        if run.get("session_id"):
            sessions.add(run["session_id"])
        seen_ids.add(run["run_id"])
        seen.add(key)


def accept(suite: dict, orders: dict[str, dict], runs: list[dict], verdicts: dict) -> tuple[str, list[str]]:
    groups = program_groups(suite, orders)
    check_runs(runs, groups, orders)
    judged = [(run, judge_run(run, orders[run["case_id"]], verdicts, groups[(run["series"], run["case_id"])], suite.get("_dir")))
              for run in runs]
    fails, pending, lines = [], [], []
    critical = [run["run_id"] for run, j in judged if j["critical"] is True]
    if critical:
        fails.append(f"critical errors: {', '.join(critical)}")
    if any(j["critical"] is None for _, j in judged):
        pending.append("critical errors not ruled out in every run")
    by_group: dict[tuple[str, str], list[dict]] = {}
    for run, j in judged:
        by_group.setdefault((run["series"], run["case_id"]), []).append(j)
    lines += ["| Series | Case | Attempts | Found | Usable | Failed | Open | Threshold | Group |", "|---|---|---|---|---|---|---|---|---|"]
    for key, group in sorted(groups.items()):
        found = by_group.get(key, [])
        usable, failed = sum(j["status"] == "PASS" for j in found), sum(j["quality_failed"] for j in found)
        decided_fail = sum(j["status"] == "FAIL" for j in found)
        attempts, needed = group["attempts"], group["min_usable"]
        threshold, name = f"{needed}/{attempts}", f"{key[0]} {key[1]}"
        open_ = attempts - usable - decided_fail
        if attempts - failed < needed:  # the failures stand whatever the missing evidence turns out to be
            verdict = "FAIL"
            fails.append(f"{name}: {usable} usable, {failed} failed, needs {threshold}")
        elif open_:
            verdict = "PENDING"
            pending.append(f"{name}: {attempts - len(found)} of {attempts} runs missing, {len(found) - usable - decided_fail} not decided")
        else:
            verdict = "PASS"
        lines.append(f"| {key[0]} | {key[1]} | {attempts} | {len(found)} | {usable} | {failed} | {open_} | {threshold} | {verdict} |")
    lines += ["", "| Series | Median latency, s | Limit, s |", "|---|---|---|"]
    limit = suite["max_median_latency_ms"]
    for series in sorted({key[0] for key in groups}):
        planned = sum(group["attempts"] for key, group in groups.items() if key[0] == series)
        # only UI times of verified web form runs; a missing run or an API time never stands in for one
        latencies = [(run.get("origin") or {}).get("ui_latency_ms") for run, j in judged if run["series"] == series and j["verified"]]
        latencies = [value for value in latencies if _number(value)]
        median = statistics.median(latencies) if len(latencies) == planned else None
        if median is None:
            pending.append(f"{series}: UI time verified for {len(latencies)} of {planned} planned runs")
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
        "case_id": order["id"], "attempt": attempt, "channel": "api", "origin": None, "session_id": None,
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
        order = orders[run["case_id"]]
        reopen = judge_run(run, order, verdicts)["reopen"]
        for criterion in criteria_for(order, run):
            key = (run["run_id"], criterion["id"])
            if args.redo and f"{key[0]}/{key[1]}" not in args.redo:
                continue
            row = verdict_for(run, criterion, verdicts)
            reopened = criterion["id"] in reopen
            if not args.redo and not reopened and row and row.get("decision"):
                continue
            suggestion = row.get("suggestion") if row else None
            if shown != run["run_id"]:
                shown = run["run_id"]
                print(f"\n=== {run['run_id']} ({run['model']}, {run['reasoning_effort']})\n{run['output']['text']}\n")
                for gap in run["output"].get("gaps", []):
                    print(f"gap: {gap['description']}")
                if formal_checks(run, order)["invented_number"]:
                    print("Note: a number that is not in the order or the positioning.")
            print(f"\n[{criterion['id']}{', critical' if criterion['critical'] else ''}] {criterion['question']}")
            if reopened:
                print("This decision contradicts another finding of this run (see accept). Decide it again.")
            if suggestion:
                print(f"Agent: {suggestion['answer']} - {suggestion.get('reason', '')} | quote: {suggestion.get('quote', '')}")
            answer = input("y = yes, n = no, u = unknown, s = skip, q = quit > ").strip().lower()
            if answer == "q":
                return 0
            if answer not in ("y", "n", "u"):
                continue
            decided = {"y": "yes", "n": "no", "u": "unknown"}[answer]
            # The agent's reason explains the agent's answer; any other decision needs the reviewer's own.
            if suggestion and suggestion["answer"] == decided:
                reason = suggestion.get("reason")
            elif decided == "yes" and not suggestion:
                reason = None
            else:
                reason = input("Your reason > ").strip() or None
            violation = criterion.get("violation_type")
            if decided == "no" and criterion["id"] == NO_CRITICAL_ERROR["id"]:
                violation = input(f"Violation type ({', '.join(CRITICAL_VIOLATIONS)}) > ").strip()
                if violation not in CRITICAL_VIOLATIONS:
                    print("Not a critical violation type; nothing saved.")
                    continue
            new = {
                "run_id": run["run_id"], "criterion_id": criterion["id"], "answer_hash": answer_hash(run["output"]),
                "input_hash": input_hash(run), "criterion_hash": criterion_hash(criterion), "suggestion": suggestion,
                "decision": {"answer": decided, "reason": reason, "violation_type": violation if decided == "no" else None,
                             "reviewer": args.reviewer,
                             "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
            }
            with path.open("a", encoding="utf-8") as out:
                out.write(json.dumps(new, ensure_ascii=False) + "\n")
            verdicts[key] = new
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
    review.add_argument(
        "--redo", action="append", metavar="RUN_ID/CRITERION_ID", help="decide this one again (repeatable); only these are shown"
    )
    accept_parser = commands.add_parser("accept", help="offline suite verdict from runs and confirmed verdicts")
    accept_parser.add_argument("--suite", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        return {"run": command_run, "review": command_review, "accept": command_accept}[args.command](args)
    except SuiteError as exc:
        print(f"invalid suite: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
