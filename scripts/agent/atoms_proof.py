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
neither existing mechanism proves for a live run. See plans/ANY-220.md's Design section for the
full rationale (job_id resolution via jobs_table, the postgresql+psycopg driver requirement,
and why "last step's artifact" is not the same row as result_artifact_id).

Invoked by scripts/agent/runner.py's atoms-proof command, parameterized by api_url and
database_url (same subprocess pattern as dev-smoke/prod-smoke).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
PLATFORM_API_TESTS_ROOT = REPO_ROOT / "apps" / "platform-api" / "tests"


def _load_module_from_path(name: str, path: Path) -> ModuleType:
    """Same load-by-path technique tests/test_kernel_demo_smoke.py's load_smoke_module() uses:
    registers the module in sys.modules before exec_module() so a `from __future__ import
    annotations` dataclass in the loaded file can resolve its string annotations."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# Loaded once at import time, guarded like kernel_demo_smoke.py's own _ATOM_MATRIX_LOAD_ERROR:
# a broken import here must still let this script run far enough to print a clear PROOF00x
# error, not crash with a raw traceback before argparse/main() ever runs.
_MODULE_LOAD_ERROR: str | None = None
try:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from tests.test_kernel_demo_smoke import load_smoke_module

    smoke = load_smoke_module()

    # apps/platform-api/tests has no __init__.py (pytest's rootless import mode), so
    # test_atom_runtime_matrix.py's own bare `from test_scenario_runtime_api import ...` only
    # resolves if that directory is on sys.path directly, the same way pytest puts it there
    # for test collection.
    if str(PLATFORM_API_TESTS_ROOT) not in sys.path:
        sys.path.insert(0, str(PLATFORM_API_TESTS_ROOT))
    _atom_runtime_matrix_module = _load_module_from_path(
        "atom_runtime_matrix_module", PLATFORM_API_TESTS_ROOT / "test_atom_runtime_matrix.py"
    )
    _EXPECTED_EVENT_TYPES: frozenset[str] = frozenset(
        _atom_runtime_matrix_module._EXPECTED_EVENT_TYPES
    )

    import sqlalchemy as sa
    from sqlalchemy.engine import make_url
    from anytoolai_platform_core.storage.db import (
        action_runs_table,
        artifacts_table,
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

DEGRADED_TIMEOUT_SECONDS = 5.0
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


def _build_engine(database_url: str) -> "sa.engine.Engine":
    """RuntimeIdentity.database_url is a bare postgresql:// URL with no driver suffix; this
    repo only installs psycopg v3 (no psycopg2), so SQLAlchemy's bare-scheme default dialect
    would fail at engine-creation time. Coerce the driver explicitly, matching every other
    engine/URL construction site in the codebase (storage/db.py's build_postgres_url_from_env,
    CI's ANYTOOLAI_POSTGRES_TEST_DATABASE_URL)."""
    url = make_url(database_url)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return sa.create_engine(url, future=True)


def _fail(
    *, label: str, scenario_id: str, kind: str, session_id: str | None, job_id: str | None,
    error_code: str, error_message: str,
) -> EvidenceCase:
    return EvidenceCase(
        label=label,
        scenario_id=scenario_id,
        kind=kind,
        status="fail",
        session_id=session_id,
        job_id=job_id,
        error_code=error_code,
        error_message=error_message,
        steps=(),
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
) -> EvidenceCase:
    """Pure pass/fail classification over already-fetched rows -- no DB access. Split out from
    _check_ledger so the PROOF00x branches are unit-testable with fake dict rows (no real
    Postgres), per plans/ANY-220.md's test strategy."""
    if job_row is None:
        return _fail(
            label=label, scenario_id=scenario_id, kind=kind,
            session_id=scenario_session_id, job_id=None,
            error_code="PROOF001",
            error_message=(
                f"PROOF001: no jobs_table row found for scenario_session_id "
                f"{scenario_session_id}"
            ),
        )
    job_id = job_row["id"]
    result_artifact_id = job_row["result_artifact_id"]

    if not action_runs:
        return _fail(
            label=label, scenario_id=scenario_id, kind=kind,
            session_id=scenario_session_id, job_id=job_id,
            error_code="PROOF002",
            error_message=(
                f"PROOF002: no action_runs rows found for scenario_session_id "
                f"{scenario_session_id}"
            ),
        )

    provider_call_counts: dict[str, int] = {}
    provider_call_by_action_run_id: dict[str, dict] = {}
    for call in provider_calls:
        provider_call_counts[call["action_run_id"]] = (
            provider_call_counts.get(call["action_run_id"], 0) + 1
        )
        provider_call_by_action_run_id[call["action_run_id"]] = call
    for action_run in action_runs:
        count = provider_call_counts.get(action_run["id"], 0)
        if count != 1:
            return _fail(
                label=label, scenario_id=scenario_id, kind=kind,
                session_id=scenario_session_id, job_id=job_id,
                error_code="PROOF003",
                error_message=(
                    f"PROOF003: expected exactly one provider_calls row for "
                    f"action_run {action_run['id']} (step {action_run['step_id']}), "
                    f"found {count}"
                ),
            )

    artifact_ids = {artifact["id"] for artifact in artifacts}
    for action_run in action_runs:
        output_artifact_id = action_run["output_artifact_id"]
        if output_artifact_id is None or output_artifact_id not in artifact_ids:
            return _fail(
                label=label, scenario_id=scenario_id, kind=kind,
                session_id=scenario_session_id, job_id=job_id,
                error_code="PROOF004",
                error_message=(
                    f"PROOF004: action_run {action_run['id']} (step "
                    f"{action_run['step_id']}) has no matching artifacts_table row"
                ),
            )
    # result_artifact_id is a separate artifact row (action_run_id=None), never a step's own
    # output_artifact_id -- workflows/runner.py's _create_final_artifact always creates a fresh
    # row from the final workflow_output. See plans/ANY-220.md's Design section.
    if result_artifact_id not in artifact_ids:
        return _fail(
            label=label, scenario_id=scenario_id, kind=kind,
            session_id=scenario_session_id, job_id=job_id,
            error_code="PROOF004",
            error_message=(
                f"PROOF004: job result_artifact_id {result_artifact_id} not found among "
                f"artifacts_table rows for scenario_session_id {scenario_session_id}"
            ),
        )

    observed_event_types = {event["event_type"] for event in events}
    if not expected_event_types.issubset(observed_event_types):
        missing = sorted(expected_event_types - observed_event_types)
        return _fail(
            label=label, scenario_id=scenario_id, kind=kind,
            session_id=scenario_session_id, job_id=job_id,
            error_code="PROOF005",
            error_message=(
                f"PROOF005: event_log_table is missing expected event types {missing} for "
                f"scenario_session_id {scenario_session_id}"
            ),
        )
    started_count = sum(1 for event in events if event["event_type"] == "action.started")
    succeeded_count = sum(1 for event in events if event["event_type"] == "action.succeeded")
    if started_count != len(action_runs) or succeeded_count != len(action_runs):
        return _fail(
            label=label, scenario_id=scenario_id, kind=kind,
            session_id=scenario_session_id, job_id=job_id,
            error_code="PROOF006",
            error_message=(
                f"PROOF006: expected {len(action_runs)} action.started and "
                f"{len(action_runs)} action.succeeded events, found {started_count} and "
                f"{succeeded_count}"
            ),
        )

    steps = tuple(
        StepEvidence(
            step_id=row["step_id"],
            action_type=row["action_type"],
            action_config_id=row["action_config_id"],
            latency_ms=provider_call_by_action_run_id[row["id"]]["latency_ms"],
            input_tokens=provider_call_by_action_run_id[row["id"]]["input_tokens"],
            output_tokens=provider_call_by_action_run_id[row["id"]]["output_tokens"],
            total_tokens=provider_call_by_action_run_id[row["id"]]["total_tokens"],
            estimated_cost=provider_call_by_action_run_id[row["id"]]["estimated_cost"],
        )
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


def _check_ledger(
    engine: "sa.engine.Engine", *, label: str, scenario_id: str, kind: str, scenario_session_id: str
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
            action_runs = list(
                conn.execute(
                    sa.select(action_runs_table)
                    .where(action_runs_table.c.scenario_session_id == scenario_session_id)
                    .order_by(action_runs_table.c.created_at, action_runs_table.c.id)
                ).mappings()
            )
            provider_calls = list(
                conn.execute(
                    sa.select(provider_calls_table).where(
                        provider_calls_table.c.scenario_session_id == scenario_session_id
                    )
                ).mappings()
            )
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
        return _fail(
            label=label, scenario_id=scenario_id, kind=kind,
            session_id=scenario_session_id, job_id=None,
            error_code="PROOF000",
            error_message=(
                f"PROOF000: database ledger check failed for scenario_session_id "
                f"{scenario_session_id}: {exc}"
            ),
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
) -> EvidenceCase:
    result = smoke._run_one_case(api_url, scenario_id, scenario_input, timeout)
    if result.error_message is not None:
        return _fail(
            label=label, scenario_id=scenario_id, kind=kind,
            session_id=result.session_id, job_id=None,
            error_code=result.error_code or "PROOF000",
            error_message=result.error_message,
        )
    return _check_ledger(
        engine, label=label, scenario_id=scenario_id, kind=kind,
        scenario_session_id=result.session_id,
    )


def run(api_url: str, database_url: str, timeout: float) -> tuple[list[EvidenceCase], int]:
    engine = _build_engine(database_url)
    cases: list[EvidenceCase] = []

    atom_total = len(ATOM_SMOKE_CASES)
    atom_passed = 0
    # Same degraded-timeout convention as kernel_demo_smoke.run(): a completion timeout
    # usually means platform-worker isn't consuming jobs at all, in which case every
    # remaining case would also time out, but every case still runs (skipping would hide
    # real per-atom regressions) -- only the *cost* of a stuck case is bounded.
    case_timeout = timeout
    for action_type, scenario_id, scenario_input in ATOM_SMOKE_CASES:
        case = _run_case_with_ledger_check(
            api_url, engine, kind="atom", label=action_type, scenario_id=scenario_id,
            scenario_input=scenario_input, timeout=case_timeout,
        )
        cases.append(case)
        if case.status == "pass":
            atom_passed += 1
            print(f"PASS {action_type}: {scenario_id} (session {case.session_id})")
            case_timeout = timeout
        else:
            print(f"FAIL {action_type}: {scenario_id} -> {case.error_message}", file=sys.stderr)
            case_timeout = (
                min(case_timeout, DEGRADED_TIMEOUT_SECONDS)
                if case.error_code == smoke._TIMEOUT_ERROR_CODE
                else timeout
            )
    print(f"{atom_passed}/{atom_total} kernel_demo atoms passed")

    composite_total = len(COMPOSITE_SMOKE_CASES)
    composite_passed = 0
    for workflow_id, scenario_id, scenario_input in COMPOSITE_SMOKE_CASES:
        case = _run_case_with_ledger_check(
            api_url, engine, kind="composite", label=workflow_id, scenario_id=scenario_id,
            scenario_input=scenario_input, timeout=timeout,
        )
        cases.append(case)
        if case.status == "pass":
            composite_passed += 1
            print(f"PASS {workflow_id}: {scenario_id} (session {case.session_id})")
        else:
            print(f"FAIL {workflow_id}: {scenario_id} -> {case.error_message}", file=sys.stderr)
    print(f"{composite_passed}/{composite_total} kernel_demo composite workflows passed")

    engine.dispose()

    coverage_error = smoke._atom_coverage_error(ATOM_SMOKE_CASES)
    if coverage_error is not None:
        print(coverage_error, file=sys.stderr)

    exit_code = 0
    if atom_passed != atom_total or composite_passed != composite_total:
        exit_code = 1
    if coverage_error is not None:
        exit_code = 1
    return cases, exit_code


def write_evidence_report(cases: list[EvidenceCase], *, output_root: Path | None = None) -> Path:
    target_root = output_root or REPO_ROOT / ".agent" / "atoms-proof"
    target_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    target = target_root / f"evidence-{timestamp}.json"
    passed = [case for case in cases if case.status == "pass"]
    atom_cases = [case for case in cases if case.kind == "atom"]
    composite_cases = [case for case in cases if case.kind == "composite"]
    payload = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "atoms_passed": sum(1 for case in atom_cases if case.status == "pass"),
        "atoms_total": len(atom_cases),
        "composite_passed": sum(1 for case in composite_cases if case.status == "pass"),
        "composite_total": len(composite_cases),
        "all_passed": len(passed) == len(cases),
        "cases": [asdict(case) for case in cases],
    }
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def _default_timeout() -> float:
    raw = os.environ.get("ANYTOOLAI_SMOKE_TIMEOUT")
    if raw is None:
        return DEFAULT_TIMEOUT_SECONDS
    return float(raw)


def main() -> int:
    if _MODULE_LOAD_ERROR is not None:
        print(_MODULE_LOAD_ERROR, file=sys.stderr)
        return 1

    try:
        default_timeout = _default_timeout()
    except ValueError as exc:
        print(f"PROOF007: ANYTOOLAI_SMOKE_TIMEOUT must be a number: {exc}", file=sys.stderr)
        return 2

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "api_url", help="Base URL of a live platform-api, e.g. http://127.0.0.1:8000"
    )
    parser.add_argument(
        "database_url", help="PostgreSQL URL for the same stack's database, e.g. "
        "postgresql://user:pass@127.0.0.1:5432/anytoolai"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=default_timeout,
        help="Seconds to wait for each scenario to complete (default: %(default)s, "
        "also settable via ANYTOOLAI_SMOKE_TIMEOUT)",
    )
    args = parser.parse_args()

    cases, exit_code = run(args.api_url.rstrip("/"), args.database_url, args.timeout)
    report_path = write_evidence_report(cases)
    print(f"Evidence report: {report_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
