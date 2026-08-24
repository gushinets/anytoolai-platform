#!/usr/bin/env python3
"""ANY-220: one reproducible command that proves all 11 generic atoms and all 3 composite
kernel_demo workflows run through the production-shaped API -> worker -> DB path, live.

This is a third proof mechanism, not a refactor of the other two:

- apps/platform-api/tests/test_atom_runtime_matrix.py + test_composite_workflow_matrix.py prove
  the same ledger/event correlation, but in-process (no live HTTP) against a throwaway
  per-test-run database.
- scripts/agent/kernel_demo_smoke.py proves the HTTP surface against a live compose stack, but
  deliberately has no DB access (see its own module docstring).

atoms_proof.py drives every case over live HTTP (reusing kernel_demo_smoke.py's
guest/start/poll/schema_ref logic verbatim) and then, on HTTP success, opens a short-lived
read-only DB connection to confirm the action_run/provider_call/artifact/event ledger this run
actually left behind -- the "ledger/event mismatch" failure category the ticket requires, which
neither existing mechanism proves for a live run. See _build_engine()'s and _classify_ledger()'s
own docstrings/comments below for the job_id resolution, postgresql+psycopg driver, and
result_artifact_id rationale.

Invoked by scripts/agent/runner.py's atoms-proof command, parameterized by api_url (positional
argv, not a secret) and --database-url-env (the *name* of an environment variable holding the
database URL, not the URL itself) -- the URL can embed credentials
(ANYTOOLAI_POSTGRES_PASSWORD), so it's kept off argv/process listings.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
PLATFORM_API_TESTS_ROOT = REPO_ROOT / "apps" / "platform-api" / "tests"


# Loaded once at import time, guarded like kernel_demo_smoke.py's own _ATOM_MATRIX_LOAD_ERROR:
# a broken import here must still let this script run far enough to print a clear PROOF00x
# error, not crash with a raw traceback before argparse/main() ever runs.
_MODULE_LOAD_ERROR: str | None = None
try:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    import collect_context
    from tests.module_loading import load_cached_module
    from tests.test_kernel_demo_smoke import load_smoke_module

    smoke = load_smoke_module()

    # apps/platform-api/tests has no __init__.py (pytest's rootless import mode), so
    # test_atom_runtime_matrix.py's own bare `from test_scenario_runtime_api import ...` only
    # resolves if that directory is on sys.path directly, the same way pytest puts it there
    # for test collection.
    if str(PLATFORM_API_TESTS_ROOT) not in sys.path:
        sys.path.insert(0, str(PLATFORM_API_TESTS_ROOT))
    # test_atom_runtime_matrix.py itself does `_SMOKE_MODULE = load_smoke_module()` at module
    # level; load_smoke_module() is cached (see its docstring), so this resolves to the same
    # module object already loaded as `smoke` above instead of a second, independently re-parsed
    # module -- no monkeypatch/sys.modules juggling needed here.
    _atom_runtime_matrix_module = load_cached_module(
        "atom_runtime_matrix_module", PLATFORM_API_TESTS_ROOT / "test_atom_runtime_matrix.py"
    )
    _EXPECTED_EVENT_TYPES: frozenset[str] = frozenset(
        _atom_runtime_matrix_module._EXPECTED_EVENT_TYPES
    )

    import sqlalchemy as sa
    from anytoolai_platform_core.storage.db import (
        action_runs_table,
        artifacts_table,
        create_sync_engine,
        event_log_table,
        jobs_table,
        provider_calls_table,
    )
except Exception as exc:  # noqa: BLE001 -- reported as a clean PROOF000, not a raw traceback
    _MODULE_LOAD_ERROR = f"PROOF000: could not load required proof dependencies: {exc}"


ATOM_SMOKE_CASES = getattr(smoke, "ATOM_SMOKE_CASES", ()) if _MODULE_LOAD_ERROR is None else ()
COMPOSITE_SMOKE_CASES = (
    getattr(smoke, "COMPOSITE_SMOKE_CASES", ()) if _MODULE_LOAD_ERROR is None else ()
)

DEFAULT_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class StepEvidence:
    step_id: str
    action_type: str
    action_config_id: str
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost: float | None = None


@dataclass(frozen=True)
class EvidenceCase:
    """Privacy-safe by construction: only ids/labels/booleans and numeric ledger metrics
    (latency, token counts, estimated cost) -- no fixture payload bodies, no prompts, no
    generated text, no PII -- exactly what gets serialized into the evidence report."""

    label: str
    scenario_id: str
    kind: str  # "atom" | "composite"
    status: str  # "pass" | "fail"
    session_id: str | None
    job_id: str | None
    error_code: str | None
    error_message: str | None
    steps: tuple[StepEvidence, ...]


def _build_engine(database_url: str, *, decode_database_name: bool = False) -> "sa.engine.Engine":
    """A thin context="atoms-proof" wrapper -- storage/db.py's create_sync_engine() now owns
    the whole contract directly: DSN parsing, bare "postgresql://" driver coercion, rejecting
    any driver but the one this repo installs (postgresql+psycopg), the decode_database_name
    percent-decode rule, and engine construction, all raising RuntimeError instead of a raw
    sqlalchemy.exc.ArgumentError/ModuleNotFoundError/etc. This function used to keep its own
    copy of the coercion+allowlist logic; three separate review rounds each found a new
    exception type escaping through that duplicate before it was moved here for good (a prior
    round of this review found the sibling decode_database_name contract had already drifted
    the same way) -- one implementation now, not two to keep in sync.

    context="atoms-proof": create_sync_engine()'s default "Runtime storage" label describes
    platform-api/platform-worker's boot path, not this CLI's operator-facing configuration
    errors (e.g. a bad --database-url-env DSN) -- twenty-first code review pass finding."""
    return create_sync_engine(
        database_url, decode_database_name=decode_database_name, context="atoms-proof"
    )


def _orphan_ids(*count_dicts: dict, known_ids: set) -> list:
    """Sorted, None-safe list of ids seen as keys in any of count_dicts but absent from
    known_ids. Shared by the PROOF014/PROOF015 orphan-event checks below: action_run_id and
    provider_call_id are nullable event_log columns (storage/db.py), so an orphan row's id can
    be None, and plain sorted() raises TypeError comparing None to a str."""
    orphans: set = set()
    for counts in count_dicts:
        orphans |= set(counts)
    orphans -= known_ids
    return sorted(orphans, key=lambda orphan_id: (orphan_id is None, orphan_id))


def _first_job_id_mismatch(
    rows: list[dict], *, job_id: str, error_code: str, describe, allow_none: bool = False
) -> str | None:
    """Shared by the PROOF011 (action_runs)/PROOF016 (provider_calls)/PROOF019 (event_log)
    ownership checks below: rows filtered independently by scenario_session_id (see
    _check_ledger) must also carry the resolved job's own job_id -- three near-identical loops
    otherwise, differing only in field name and (for event_log) whether a null job_id is
    tolerated. Returns an error_message for the first mismatch, or None if every row agrees.
    describe() renders one row for the message; allow_none skips rows whose job_id is None
    instead of treating None as a mismatch (event_log's job_id is nullable -- some
    session-scoped events, e.g. scenario.started, are emitted before a job exists)."""
    for row in rows:
        row_job_id = row.get("job_id") if allow_none else row["job_id"]
        if allow_none and row_job_id is None:
            continue
        if row_job_id != job_id:
            return f"{error_code}: {describe(row)} has job_id {row_job_id!r}, expected {job_id!r}"
    return None


def _correlate_events_by_id(events: list[dict], *, event_type: str, id_field: str) -> Counter:
    """Counts of `events` rows with event_type `event_type`, keyed by row[id_field]. Shared by
    the PROOF006/013/020 count checks and their PROOF014/015/021 orphan checks below -- five
    near-identical counting loops otherwise (action.started, action.succeeded,
    provider.request_started, provider.request_succeeded, artifact.created)."""
    return Counter(event.get(id_field) for event in events if event["event_type"] == event_type)


def _fail(
    *, label: str, scenario_id: str, kind: str, session_id: str | None, job_id: str | None,
    error_code: str, error_message: str,
    steps: tuple[StepEvidence, ...] = (),
) -> EvidenceCase:
    """steps defaults to () for the common case (nothing ran yet, so no cost was incurred) but
    _classify_ledger's PROOF00x branches pass known_steps -- see its own comment -- so a case
    that already made a real, billed provider call before failing a later correctness check still
    reports its real cost instead of silently reporting 0."""
    return EvidenceCase(
        label=label,
        scenario_id=scenario_id,
        kind=kind,
        status="fail",
        session_id=session_id,
        job_id=job_id,
        error_code=error_code,
        error_message=error_message,
        steps=steps,
    )


def _best_effort_steps_from_provider_calls(
    action_runs: list[dict], provider_calls: list[dict]
) -> tuple[StepEvidence, ...]:
    """Best-effort StepEvidence built directly from provider_calls, independent of whether the
    correlation checks _classify_ledger runs below have passed -- used only for _fail()'s
    steps=known_steps so a case that already made a real, billed provider call before failing a
    later correctness check still reports its real cost (live_canary.py's cost cap sums exactly
    this field), instead of silently reporting 0. Tolerant of any of the correlation defects those
    checks exist to catch (duplicate/orphan calls, mismatched action_run_id) -- falls back to the
    bare action_run_id when a provider_calls row can't be matched to a known action_run."""
    action_run_by_id = {action_run["id"]: action_run for action_run in action_runs}
    steps = []
    for call in provider_calls:
        action_run = action_run_by_id.get(call["action_run_id"])
        steps.append(
            StepEvidence(
                step_id=(
                    action_run["step_id"] if action_run is not None else call["action_run_id"]
                ),
                action_type=action_run["action_type"] if action_run is not None else "unknown",
                action_config_id=(
                    action_run["action_config_id"] if action_run is not None else "unknown"
                ),
                latency_ms=call["latency_ms"],
                input_tokens=call["input_tokens"],
                output_tokens=call["output_tokens"],
                total_tokens=call["total_tokens"],
                estimated_cost=call["estimated_cost"],
            )
        )
    return tuple(steps)


def _step_evidence_from_action_run(action_run: dict, calls: list[dict]) -> StepEvidence:
    """Aggregates every physical provider_calls row for one action_run into a single StepEvidence
    -- default_text_generation_v1's retry_policy.hard_limits permits up to 4 physical calls per
    logical action (structured-output/transport retries), so more than one row for a single,
    successfully-completed action is a legitimate outcome, not a correlation defect (code review
    finding: PROOF003 below used to require exactly one, which would fail a live case's own
    legitimate retry as a correctness bug). Summing keeps every real, billed attempt's
    cost/latency/tokens in the evidence and in live_canary.py's cost cap, instead of the previous
    single-row lookup silently dropping every retry but the last one's own cost."""
    return StepEvidence(
        step_id=action_run["step_id"],
        action_type=action_run["action_type"],
        action_config_id=action_run["action_config_id"],
        latency_ms=sum(call["latency_ms"] for call in calls),
        input_tokens=sum(call["input_tokens"] for call in calls),
        output_tokens=sum(call["output_tokens"] for call in calls),
        total_tokens=sum(call["total_tokens"] for call in calls),
        estimated_cost=sum(call["estimated_cost"] for call in calls),
    )


def _classify_ledger(
    *,
    label: str,
    scenario_id: str,
    kind: str,
    scenario_session_id: str,
    job_row: dict | None,
    action_runs: list[dict],
    provider_calls: list[dict],
    artifacts: list[dict],
    events: list[dict],
    expected_event_types: frozenset[str],
    max_provider_calls_per_action: int = 1,
) -> EvidenceCase:
    """Pure pass/fail classification over already-fetched rows -- no DB access. Split out from
    _check_ledger so the PROOF00x branches are unit-testable with fake dict rows, no real
    Postgres needed.

    max_provider_calls_per_action bounds PROOF003's per-action_run provider_calls count (default
    1, this script's own fake-provider callers never retry). live_canary.py passes a higher bound
    matching default_text_generation_v1's own retry_policy.hard_limits.max_physical_provider_calls_
    per_action (code review finding: the exactly-one invariant only ever held for the fake
    provider, and legitimately fails a live case's own retry as a PROOF003 correctness bug).

    Every internal failure returns through `fail` (functools.partial over _fail(), bound once
    with label/scenario_id/kind/session_id/steps=known_steps -- the fields every PROOF00x branch
    shares -- leaving each call site to supply only job_id/error_code/error_message) instead of
    calling _fail() directly at each of the 19 return sites below -- `/code-review` #4 (2026-08-24)
    finding #6: a manually repeated steps=known_steps() at every call site meant a missed site (as
    in finding #1, the _check_ledger() except-branch) silently produced incomplete evidence.
    Binding the shared fields once makes that particular class of typo far less likely, since a
    call site no longer has to hand-type steps=known_steps() (or any of the other shared fields)
    at all -- but `_fail()` itself is still directly importable/callable from this same scope, so
    this is a strong convention this function's own 19 call sites all follow, not a
    language-enforced guarantee (`/code-review` #5, 2026-08-24 finding #1: an earlier version of
    this docstring overclaimed "structurally impossible"). known_steps is computed eagerly (not
    lazily, unlike a prior round -- `/code-review` #4 finding #5: a per-call-scoped @cache on a
    closure that's provably called at most once per invocation, since every call site immediately
    returns, was pure overhead and a misleading "memoized for reuse" signal) -- the small, bounded
    cost of this on the success path (which builds its own, differently-ordered `steps` tuple from
    action_runs and never touches `fail`) is worth the added safety."""
    known_steps = _best_effort_steps_from_provider_calls(action_runs, provider_calls)
    fail = partial(
        _fail, label=label, scenario_id=scenario_id, kind=kind,
        session_id=scenario_session_id, steps=known_steps,
    )
    if job_row is None:
        return fail(
            job_id=None,
            error_code="PROOF001",
            error_message=(
                f"PROOF001: no jobs_table row found for scenario_session_id "
                f"{scenario_session_id}"
            ),
        )
    job_id = job_row["id"]
    result_artifact_id = job_row["result_artifact_id"]

    if not action_runs:
        return fail(
            job_id=job_id,
            error_code="PROOF002",
            error_message=(
                f"PROOF002: no action_runs rows found for scenario_session_id "
                f"{scenario_session_id}"
            ),
        )

    # scenario_session_id alone doesn't guarantee an action_run actually belongs to this job --
    # both columns are filtered independently at query time (see _check_ledger), so a mislinked
    # row would otherwise pass every downstream check silently.
    mismatch = _first_job_id_mismatch(
        action_runs, job_id=job_id, error_code="PROOF011",
        describe=lambda run: f"action_run {run['id']} (step {run['step_id']})",
    )
    if mismatch is not None:
        return fail(
            job_id=job_id,
            error_code="PROOF011", error_message=mismatch,
        )

    action_run_ids = {action_run["id"] for action_run in action_runs}

    # provider_calls, artifacts, and event_log are all filtered independently by
    # scenario_session_id only (see _check_ledger) -- action_run_id membership (PROOF012 below)
    # already implies a provider_calls row belongs to *an* action_run of this job, but not that
    # the row's own job_id column agrees. Check it directly so a mislinked row can't pass
    # silently.
    mismatch = _first_job_id_mismatch(
        provider_calls, job_id=job_id, error_code="PROOF016",
        describe=lambda call: f"provider_calls row {call['id']}",
    )
    if mismatch is not None:
        return fail(
            job_id=job_id,
            error_code="PROOF016", error_message=mismatch,
        )

    # Groups (not counts) provider_calls by action_run_id -- one action_run can legitimately have
    # more than one physical provider_calls row (retries, bounded by max_provider_calls_per_action;
    # see this function's own docstring), so a plain Counter (round #2's own dedup fix) would only
    # tell us "how many", losing which specific rows to sum into that step's evidence below.
    provider_calls_by_action_run_id: dict[str, list[dict]] = defaultdict(list)
    for call in provider_calls:
        provider_calls_by_action_run_id[call["action_run_id"]].append(call)
    for action_run in action_runs:
        calls = provider_calls_by_action_run_id.get(action_run["id"], [])
        if not (1 <= len(calls) <= max_provider_calls_per_action):
            return fail(
                job_id=job_id,
                error_code="PROOF003",
                error_message=(
                    f"PROOF003: expected 1-{max_provider_calls_per_action} provider_calls "
                    f"row(s) for action_run {action_run['id']} (step {action_run['step_id']}), "
                    f"found {len(calls)}"
                ),
            )
    # An orphan provider_calls row (right scenario_session_id, action_run_id pointing outside
    # this session's own action_runs) would never surface above -- the count loop only walks
    # known action_runs, so it can't detect an extra row keyed to nothing real.
    for call in provider_calls:
        if call["action_run_id"] not in action_run_ids:
            return fail(
                job_id=job_id,
                error_code="PROOF012",
                error_message=(
                    f"PROOF012: provider_calls row {call['id']} references action_run_id "
                    f"{call['action_run_id']!r}, which is not among this session's action_runs"
                ),
            )

    artifacts_by_id = {artifact["id"]: artifact for artifact in artifacts}
    # artifacts is filtered independently by scenario_session_id only (see _check_ledger), so an
    # extra, unreferenced row for a different job could be present alongside the rows
    # action_runs/job actually reference. If that row happens to carry exactly one matching
    # artifact.created event, PROOF020/021's per-artifact_id correlation below would never
    # notice either, since it only asks "does this id have exactly one creation event", not
    # "does this id belong here at all". Scanned here, before the PROOF004/017/018
    # reference-specific checks below -- mirroring PROOF016's placement before PROOF003/012 for
    # provider_calls -- rather than as an ad hoc fourth check appended after them.
    # No allow_none here, unlike PROOF019's event_log scan: event_log.job_id has a genuine,
    # reachable null case (scenario.started is emitted before a job exists), but no current
    # ArtifactService caller ever creates a job-less artifact -- tolerating job_id=None here
    # would let an unowned artifact (and its own job-less artifact.created event, which PROOF019
    # would also tolerate) pass this entire proof as a PASS with an artifact nothing actually
    # claims. If job-less artifacts become a real, intentional state, restrict the tolerance to
    # that specific role rather than every fetched session row (team-lead-#5 review).
    mismatch = _first_job_id_mismatch(
        artifacts, job_id=job_id, error_code="PROOF023",
        describe=lambda artifact: f"artifacts_table row {artifact['id']}",
    )
    if mismatch is not None:
        return fail(
            job_id=job_id,
            error_code="PROOF023", error_message=mismatch,
        )

    for action_run in action_runs:
        output_artifact_id = action_run["output_artifact_id"]
        artifact = artifacts_by_id.get(output_artifact_id)
        if artifact is None:
            return fail(
                job_id=job_id,
                error_code="PROOF004",
                error_message=(
                    f"PROOF004: action_run {action_run['id']} (step "
                    f"{action_run['step_id']}) has no matching artifacts_table row"
                ),
            )
        # PROOF023 above already guarantees every fetched artifact's job_id is exactly job_id
        # (no tolerance), so only the action_run_id lineage PROOF023's row-level scan can't
        # express is left to check here -- mirrors provider_calls' PROOF012, which likewise
        # never re-touches job_id after PROOF016.
        if artifact["action_run_id"] != action_run["id"]:
            return fail(
                job_id=job_id,
                error_code="PROOF017",
                error_message=(
                    f"PROOF017: artifact {output_artifact_id} for action_run "
                    f"{action_run['id']} (step {action_run['step_id']}) has action_run_id "
                    f"{artifact['action_run_id']!r}, expected {action_run['id']!r}"
                ),
            )
    # result_artifact_id is a separate artifact row (action_run_id=None), never a step's own
    # output_artifact_id -- workflows/runner.py's _create_final_artifact always creates a fresh
    # row from the final workflow_output.
    result_artifact = artifacts_by_id.get(result_artifact_id)
    if result_artifact is None:
        return fail(
            job_id=job_id,
            error_code="PROOF004",
            error_message=(
                f"PROOF004: job result_artifact_id {result_artifact_id} not found among "
                f"artifacts_table rows for scenario_session_id {scenario_session_id}"
            ),
        )
    # Same reasoning as PROOF017 above: PROOF023 already guarantees job_id, only action_run_id
    # lineage remains to check.
    if result_artifact["action_run_id"] is not None:
        return fail(
            job_id=job_id,
            error_code="PROOF018",
            error_message=(
                f"PROOF018: job result_artifact_id {result_artifact_id} has action_run_id "
                f"{result_artifact['action_run_id']!r}, expected None"
            ),
        )

    observed_event_types = {event["event_type"] for event in events}
    if not expected_event_types.issubset(observed_event_types):
        missing = sorted(expected_event_types - observed_event_types)
        return fail(
            job_id=job_id,
            error_code="PROOF005",
            error_message=(
                f"PROOF005: event_log_table is missing expected event types {missing} for "
                f"scenario_session_id {scenario_session_id}"
            ),
        )

    # job_id is nullable on event_log (some session-scoped events, e.g. scenario.started, are
    # emitted before a job exists), so only a *non-null* mismatch is a real ownership defect.
    mismatch = _first_job_id_mismatch(
        events, job_id=job_id, error_code="PROOF019", allow_none=True,
        describe=lambda event: f"event_log row (event_type {event['event_type']!r})",
    )
    if mismatch is not None:
        return fail(
            job_id=job_id,
            error_code="PROOF019", error_message=mismatch,
        )

    # PROOF005 above only checks the *type* is present anywhere in the session, so one
    # artifact.created row can satisfy a multi-artifact workflow with several artifacts_table
    # rows. Correlate by artifact_id, matching the same per-entity correlation this check class
    # already does for action_run_id/provider_call_id below.
    artifact_created_counts = _correlate_events_by_id(
        events, event_type="artifact.created", id_field="artifact_id"
    )
    for artifact_id in artifacts_by_id:
        count = artifact_created_counts.get(artifact_id, 0)
        if count != 1:
            return fail(
                job_id=job_id,
                error_code="PROOF020",
                error_message=(
                    f"PROOF020: expected exactly one artifact.created event_log row for "
                    f"artifact {artifact_id}, found {count}"
                ),
            )
    orphan_artifact_event_ids = _orphan_ids(
        artifact_created_counts, known_ids=set(artifacts_by_id)
    )
    if orphan_artifact_event_ids:
        return fail(
            job_id=job_id,
            error_code="PROOF021",
            error_message=(
                f"PROOF021: event_log has artifact.created rows for artifact_id(s) "
                f"{orphan_artifact_event_ids}, not among this session's artifacts_table rows"
            ),
        )

    # PROOF005 above only checks the *set* of event types seen anywhere in the session -- it
    # would pass even if every action.started/succeeded event were misattributed to one
    # action_run and none to another (counts still sum right), or duplicated once and missing
    # once. Correlate by action_run_id/provider_call_id, not just event_type, to catch that.
    action_started_counts = _correlate_events_by_id(
        events, event_type="action.started", id_field="action_run_id"
    )
    action_succeeded_counts = _correlate_events_by_id(
        events, event_type="action.succeeded", id_field="action_run_id"
    )
    for action_run in action_runs:
        run_id = action_run["id"]
        started = action_started_counts.get(run_id, 0)
        succeeded = action_succeeded_counts.get(run_id, 0)
        if started != 1 or succeeded != 1:
            return fail(
                job_id=job_id,
                error_code="PROOF006",
                error_message=(
                    f"PROOF006: expected exactly one action.started and one "
                    f"action.succeeded event_log row for action_run {run_id} (step "
                    f"{action_run['step_id']}), found {started} and {succeeded}"
                ),
            )
    # The per-run loop above only walks known action_runs, so an orphan event_log row (same
    # scenario_session_id, but an action_run_id not among this session's action_runs -- e.g.
    # misattributed to another session's run) would never surface, mirroring the PROOF012 gap
    # this same check class already closed for provider_calls.
    orphan_action_event_ids = _orphan_ids(
        action_started_counts, action_succeeded_counts, known_ids=action_run_ids
    )
    if orphan_action_event_ids:
        return fail(
            job_id=job_id,
            error_code="PROOF014",
            error_message=(
                f"PROOF014: event_log has action.started/action.succeeded rows for "
                f"action_run_id(s) {orphan_action_event_ids}, not among this "
                f"session's action_runs"
            ),
        )

    provider_call_ids = {call["id"] for call in provider_calls}
    provider_started_counts = _correlate_events_by_id(
        events, event_type="provider.request_started", id_field="provider_call_id"
    )
    provider_succeeded_counts = _correlate_events_by_id(
        events, event_type="provider.request_succeeded", id_field="provider_call_id"
    )
    for call in provider_calls:
        call_id = call["id"]
        started = provider_started_counts.get(call_id, 0)
        succeeded = provider_succeeded_counts.get(call_id, 0)
        if started != 1 or succeeded != 1:
            return fail(
                job_id=job_id,
                error_code="PROOF013",
                error_message=(
                    f"PROOF013: expected exactly one provider.request_started and one "
                    f"provider.request_succeeded event_log row for provider_call {call_id} "
                    f"(action_run {call['action_run_id']}), found {started} and {succeeded}"
                ),
            )
    orphan_provider_event_ids = _orphan_ids(
        provider_started_counts, provider_succeeded_counts, known_ids=provider_call_ids
    )
    if orphan_provider_event_ids:
        return fail(
            job_id=job_id,
            error_code="PROOF015",
            error_message=(
                f"PROOF015: event_log has provider.request_started/"
                f"provider.request_succeeded rows for provider_call_id(s) "
                f"{orphan_provider_event_ids}, not among this session's "
                f"provider_calls"
            ),
        )

    steps = tuple(
        _step_evidence_from_action_run(row, provider_calls_by_action_run_id[row["id"]])
        for row in action_runs
    )
    return EvidenceCase(
        label=label,
        scenario_id=scenario_id,
        kind=kind,
        status="pass",
        session_id=scenario_session_id,
        job_id=job_id,
        error_code=None,
        error_message=None,
        steps=steps,
    )


def _fetch_action_runs(conn: "sa.engine.Connection", scenario_session_id: str) -> list[dict]:
    """Shared by _check_ledger()'s main fetch and _known_steps_for_session()'s recovery fetch --
    `/code-review` #4 (2026-08-24) finding: those two used to run this exact query independently,
    risking the two drifting apart on a future schema change applied to only one of them."""
    return list(
        conn.execute(
            sa.select(action_runs_table)
            .where(action_runs_table.c.scenario_session_id == scenario_session_id)
            .order_by(action_runs_table.c.created_at, action_runs_table.c.id)
        ).mappings()
    )


def _fetch_provider_calls(conn: "sa.engine.Connection", scenario_session_id: str) -> list[dict]:
    """Shared by _check_ledger()'s main fetch and _known_steps_for_session()'s recovery fetch --
    see _fetch_action_runs()'s docstring."""
    return list(
        conn.execute(
            sa.select(provider_calls_table).where(
                provider_calls_table.c.scenario_session_id == scenario_session_id
            )
        ).mappings()
    )


def _known_steps_for_session(
    engine: "sa.engine.Engine", scenario_session_id: str | None
) -> tuple[StepEvidence, ...]:
    """`/code-review` #3 (2026-08-24) finding: a case can fail at the HTTP/status-polling layer
    (_run_case_with_ledger_check's `result.error_message is not None` branch) *after* a real,
    billed provider call already happened server-side -- that branch never reaches
    _check_ledger()/_classify_ledger(), the only place known_steps recovery was wired in, so the
    spend would otherwise silently report 0 to live_canary.py's cost cap. This is that same
    recovery for the HTTP-layer failure path: a minimal, best-effort query for just the two tables
    _best_effort_steps_from_provider_calls() needs, not a full _check_ledger() run (which would
    misclassify an HTTP-layer failure as a ledger-correctness one). Also reused by _check_ledger()
    itself for the same recovery when its own 5-table fetch raises (`/code-review` #4, 2026-08-24
    finding #1 -- a case that made a real provider call and then hit a transient SQLAlchemyError
    fetching the ledger was losing its cost the same way). Tolerant of everything -- no
    scenario_session_id yet (nothing could have run), a DB error, or a session with no rows yet --
    all resolve to () rather than raising, since this is best-effort recovery on an
    already-failing path, not a correctness check of its own."""
    if scenario_session_id is None:
        return ()
    try:
        with engine.connect() as conn:
            action_runs = _fetch_action_runs(conn, scenario_session_id)
            provider_calls = _fetch_provider_calls(conn, scenario_session_id)
    except sa.exc.SQLAlchemyError:
        return ()
    return _best_effort_steps_from_provider_calls(action_runs, provider_calls)


def _check_ledger(
    engine: "sa.engine.Engine",
    *,
    label: str,
    scenario_id: str,
    kind: str,
    scenario_session_id: str,
    max_provider_calls_per_action: int = 1,
) -> EvidenceCase:
    try:
        with engine.connect() as conn:
            job_row = (
                conn.execute(
                    sa.select(jobs_table).where(
                        jobs_table.c.scenario_session_id == scenario_session_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            action_runs = _fetch_action_runs(conn, scenario_session_id)
            provider_calls = _fetch_provider_calls(conn, scenario_session_id)
            artifacts = list(
                conn.execute(
                    sa.select(artifacts_table).where(
                        artifacts_table.c.scenario_session_id == scenario_session_id
                    )
                ).mappings()
            )
            events = list(
                conn.execute(
                    sa.select(event_log_table).where(
                        event_log_table.c.scenario_session_id == scenario_session_id
                    )
                ).mappings()
            )
    except sa.exc.SQLAlchemyError as exc:
        # Exception class name only, not str(exc) -- database_url (and therefore this
        # connection's credentials) isn't guaranteed to be the fixed dev-only default; a driver
        # error message is free-form text this script doesn't control, so it doesn't belong in a
        # persisted "privacy-safe" evidence artifact. The class name is still enough to tell
        # e.g. OperationalError (connection/auth) from ProgrammingError (bad query) at a glance.
        # steps recovers a real, billed provider call this same batch's own SQLAlchemyError
        # (connection drop, pool exhaustion, statement timeout right after a slow live provider
        # round-trip) would otherwise have silently lost -- `/code-review` #4 finding #1.
        return _fail(
            label=label, scenario_id=scenario_id, kind=kind,
            session_id=scenario_session_id, job_id=None,
            error_code="PROOF000",
            error_message=(
                f"PROOF000: database ledger check failed for scenario_session_id "
                f"{scenario_session_id}: {type(exc).__name__}"
            ),
            steps=_known_steps_for_session(engine, scenario_session_id),
        )

    return _classify_ledger(
        label=label,
        scenario_id=scenario_id,
        kind=kind,
        scenario_session_id=scenario_session_id,
        job_row=job_row,
        action_runs=action_runs,
        provider_calls=provider_calls,
        artifacts=artifacts,
        events=events,
        expected_event_types=_EXPECTED_EVENT_TYPES,
        max_provider_calls_per_action=max_provider_calls_per_action,
    )


def _run_case_with_ledger_check(
    api_url: str,
    engine: "sa.engine.Engine",
    *,
    kind: str,
    label: str,
    scenario_id: str,
    scenario_input: dict,
    timeout: float,
    expected_schema_ref_by_scenario: dict[str, str] | None = None,
    live_canary_token: str | None = None,
    max_provider_calls_per_action: int = 1,
) -> EvidenceCase:
    """expected_schema_ref_by_scenario/live_canary_token are forwarded to smoke._run_one_case()
    verbatim -- see its own docstring. None (this script's own dev-smoke/prod-smoke-style
    fake-provider callers) keeps smoke._run_one_case()'s defaults (module-level schema-ref lookup,
    no X-Live-Canary-Token header); live_canary.py passes its own values for both.
    max_provider_calls_per_action is forwarded to _check_ledger()/_classify_ledger() verbatim --
    see _classify_ledger()'s own docstring."""
    result = smoke._run_one_case(
        api_url, scenario_id, scenario_input, timeout,
        expected_schema_ref_by_scenario=expected_schema_ref_by_scenario,
        live_canary_token=live_canary_token,
    )
    if result.error_message is not None:
        # result.error_message is free-form text this script doesn't control (e.g. SMOKE004
        # embeds the whole raw scenario-session response body) -- print it once here for a human
        # to read, but don't let it flow into EvidenceCase, which is persisted to disk and
        # documented as privacy-safe-by-construction (ids/labels/booleans only).
        print(f"{label} ({scenario_id}): {result.error_message}", file=sys.stderr)
        error_code = result.error_code or "PROOF000"
        return _fail(
            label=label, scenario_id=scenario_id, kind=kind,
            session_id=result.session_id, job_id=None,
            error_code=error_code,
            error_message=(
                f"{error_code}: HTTP-layer case failed for scenario_id {scenario_id} "
                "(see stderr for full diagnostic)"
            ),
            steps=_known_steps_for_session(engine, result.session_id),
        )
    return _check_ledger(
        engine, label=label, scenario_id=scenario_id, kind=kind,
        scenario_session_id=result.session_id,
        max_provider_calls_per_action=max_provider_calls_per_action,
    )


def _run_case_group(
    api_url: str,
    engine: "sa.engine.Engine",
    cases_spec: tuple[tuple[str, str, dict], ...],
    *,
    kind: str,
    timeout: float,
    case_timeout: float,
) -> tuple[list[EvidenceCase], int, float]:
    """Runs one group (atom or composite) of cases, threading the degraded case_timeout through
    via smoke._next_case_timeout() -- the same shared chaining rule kernel_demo_smoke.py's own
    _run_case_batch() uses, so a stuck platform-worker detected in the atom group doesn't make
    the composite group wait a full timeout per case all over again."""
    results: list[EvidenceCase] = []
    for label, scenario_id, scenario_input in cases_spec:
        case = _run_case_with_ledger_check(
            api_url, engine, kind=kind, label=label, scenario_id=scenario_id,
            scenario_input=scenario_input, timeout=case_timeout,
        )
        results.append(case)
        if case.status == "pass":
            print(f"PASS {label}: {scenario_id} (session {case.session_id})")
        else:
            print(f"FAIL {label}: {scenario_id} -> {case.error_message}", file=sys.stderr)
        case_timeout = smoke._next_case_timeout(
            case_timeout, timeout, timed_out=case.error_code == smoke._TIMEOUT_ERROR_CODE
        )
    passed = sum(1 for case in results if case.status == "pass")
    return results, passed, case_timeout


def run(
    api_url: str, database_url: str, timeout: float, *, decode_database_name: bool = False
) -> tuple[list[EvidenceCase], int]:
    """Runs ATOM_SMOKE_CASES then COMPOSITE_SMOKE_CASES against a live api_url/database_url.

    Precondition owned by the caller, not enforced here: main() must call
    smoke._coverage_gate_error() first -- same contract as kernel_demo_smoke.py's own run().
    run() doesn't re-check coverage so tests can call it directly to exercise per-case behavior
    in isolation from the coverage guard.

    decode_database_name is forwarded to _build_engine() verbatim -- see its own docstring.
    """
    # Same vacuous-success guard as kernel_demo_smoke.py's run(): an empty ATOM_SMOKE_CASES/
    # COMPOSITE_SMOKE_CASES (e.g. a caller-supplied monkeypatch, per this function's own
    # "callable directly, bypassing main()'s coverage guard" contract above) must not read as
    # "0/0 passed" success -- 0 == 0 would otherwise report exit 0.
    atom_total = len(ATOM_SMOKE_CASES)
    empty_error = smoke._empty_cases_error(
        ATOM_SMOKE_CASES, error_code="PROOF008", tuple_name="ATOM_SMOKE_CASES", purpose="prove"
    )
    if empty_error is not None:
        print(empty_error, file=sys.stderr)
        return [], 1

    # _build_engine() can raise RuntimeError for any engine-configuration problem it or
    # create_sync_engine() detects -- not only the decode-with-nothing-to-decode contract (see
    # _build_engine()'s own docstring), but also e.g. a non-PostgreSQL --database-url-env value
    # (require_postgresql_url()). PROOF022 is deliberately this broad, not one specific cause:
    # left uncaught, any of these propagated as a raw traceback instead of the PROOF0xx failure
    # category the module docstring promises for every category of failure, and skipped
    # write_evidence_report() entirely; the exception text (never a credential -- database_url
    # itself is never part of RuntimeError's own message here) still tells them apart.
    try:
        engine = _build_engine(database_url, decode_database_name=decode_database_name)
    except RuntimeError as exc:
        print(f"PROOF022: engine configuration error: {exc}", file=sys.stderr)
        return [], 1

    cases: list[EvidenceCase] = []
    try:
        atom_cases, atom_passed, case_timeout = _run_case_group(
            api_url, engine, ATOM_SMOKE_CASES, kind="atom", timeout=timeout, case_timeout=timeout,
        )
        cases.extend(atom_cases)
        print(f"{atom_passed}/{atom_total} kernel_demo atoms passed")

        composite_total = len(COMPOSITE_SMOKE_CASES)
        empty_error = smoke._empty_cases_error(
            COMPOSITE_SMOKE_CASES, error_code="PROOF009", tuple_name="COMPOSITE_SMOKE_CASES",
            purpose="prove",
        )
        if empty_error is not None:
            print(empty_error, file=sys.stderr)
            return cases, 1

        composite_cases, composite_passed, _case_timeout = _run_case_group(
            api_url, engine, COMPOSITE_SMOKE_CASES, kind="composite", timeout=timeout,
            case_timeout=case_timeout,
        )
        cases.extend(composite_cases)
        print(f"{composite_passed}/{composite_total} kernel_demo composite workflows passed")

        exit_code = 0 if atom_passed == atom_total and composite_passed == composite_total else 1
        return cases, exit_code
    finally:
        engine.dispose()


def write_evidence_report(
    cases: list[EvidenceCase], exit_code: int, *, output_root: Path | None = None
) -> Path:
    # A caller passing exit_code=0 alongside a `cases` list that actually contains a failure
    # would make the payload's own "all_passed": true contradict its own "cases" detail below --
    # exactly the class of drift the fifth-pass fix (exit_code-derived all_passed) was meant to
    # prevent. Only this direction is checked: exit_code=1 with all-passing `cases` is the
    # legitimate PROOF008/PROOF009 empty-case-guard shape, not a caller bug.
    # A bare `assert` here would be compiled out under `python -O`/PYTHONOPTIMIZE, silently
    # disabling the invariant; `raise` isn't.
    if exit_code == 0 and any(case.status == "fail" for case in cases):
        raise ValueError(
            "write_evidence_report called with exit_code=0 but `cases` contains a failing case"
        )
    target_root = output_root or REPO_ROOT / ".agent" / "atoms-proof"
    atom_cases = [case for case in cases if case.kind == "atom"]
    composite_cases = [case for case in cases if case.kind == "composite"]
    payload = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "atoms_passed": sum(1 for case in atom_cases if case.status == "pass"),
        "atoms_total": len(atom_cases),
        "composite_passed": sum(1 for case in composite_cases if case.status == "pass"),
        "composite_total": len(composite_cases),
        # Derived from run()'s own exit_code, not re-derived from `cases` here -- an empty
        # `cases` (PROOF008/PROOF009's empty-case guards) would otherwise read as vacuous
        # 0-passed-of-0 "success" even though run() itself returned a non-zero exit_code.
        "all_passed": exit_code == 0,
        "cases": [asdict(case) for case in cases],
    }
    return collect_context.write_timestamped_json_bundle(target_root, "evidence", payload)


def _default_timeout() -> float:
    raw = os.environ.get("ANYTOOLAI_SMOKE_TIMEOUT")
    if raw is None:
        return DEFAULT_TIMEOUT_SECONDS
    return float(raw)


def _build_arg_parser(
    description: str | None, *, default_timeout: float
) -> argparse.ArgumentParser:
    """Shared by this script's own main() below and live_canary.py's -- both need the identical
    api_url/--database-url-env/--timeout/--database-url-is-percent-encoded arguments (same help
    text, same DSN-passing/timeout contract, see _run_case_with_ledger_check/_build_engine), since
    live_canary.py reuses this script's HTTP/DB/evidence machinery wholesale. A near-copy of this
    parser previously lived in live_canary.py too; --database-url-is-percent-encoded once drifted
    out of sync between the two (caught only on review), precisely because they were declared
    separately instead of sharing this builder. live_canary.py adds its own --max-total-cost-usd
    on top of what this returns."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "api_url", help="Base URL of a live platform-api, e.g. http://127.0.0.1:8000"
    )
    parser.add_argument(
        "--database-url-env",
        required=True,
        metavar="ENV_VAR",
        help="Name of an environment variable holding the PostgreSQL URL for the same stack's "
        "database, e.g. ANYTOOLAI_ATOMS_PROOF_DATABASE_URL -- the URL itself is read from the "
        "environment, not passed here, since it can embed credentials that argv/process "
        "listings would otherwise expose.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=default_timeout,
        help="Seconds to wait for each scenario to complete (default: %(default)s, "
        "also settable via ANYTOOLAI_SMOKE_TIMEOUT)",
    )
    parser.add_argument(
        "--database-url-is-percent-encoded",
        action="store_true",
        help="Set when the DSN in --database-url-env's env var had its database-name path "
        "segment percent-encoded by its producer (e.g. scripts/agent/runner.py's "
        "RuntimeIdentity.database_url) -- decodes it back before connecting. Leave unset for a "
        "hand-written or otherwise arbitrary DSN, whose database name is used exactly as given.",
    )
    return parser


def main() -> int:
    if _MODULE_LOAD_ERROR is not None:
        print(_MODULE_LOAD_ERROR, file=sys.stderr)
        return 1

    try:
        default_timeout = _default_timeout()
    except ValueError as exc:
        print(f"PROOF007: ANYTOOLAI_SMOKE_TIMEOUT must be a number: {exc}", file=sys.stderr)
        return 2

    parser = _build_arg_parser(__doc__, default_timeout=default_timeout)
    args = parser.parse_args()

    database_url = os.environ.get(args.database_url_env)
    if not database_url:
        print(
            f"PROOF010: environment variable {args.database_url_env!r} (--database-url-env) "
            "is not set or empty",
            file=sys.stderr,
        )
        return 2

    coverage_error = smoke._coverage_gate_error(ATOM_SMOKE_CASES, COMPOSITE_SMOKE_CASES)
    if coverage_error is not None:
        print(coverage_error, file=sys.stderr)
        # Persisting an evidence report is this script's whole point (module docstring); a
        # coverage-gate failure is one of the ticket's required non-zero-exit failure categories
        # too, so it must leave the same kind of inspectable artifact behind as a live-case
        # failure does, instead of silently exiting with nothing written.
        cases, exit_code = [], 1
    else:
        cases, exit_code = run(
            args.api_url.rstrip("/"), database_url, args.timeout,
            decode_database_name=args.database_url_is_percent_encoded,
        )

    report_path = write_evidence_report(cases, exit_code)
    print(f"Evidence report: {report_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
