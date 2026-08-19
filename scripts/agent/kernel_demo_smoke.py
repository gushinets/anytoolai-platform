#!/usr/bin/env python3
"""Drives the kernel_demo smoke scenario over HTTP against a live platform-api/platform-worker
stack (dev or prod) and confirms it actually completes.

platform-worker has no Docker healthcheck or HTTP surface of its own (it's a pure DB-polling
loop, see infra/docker/platform-worker.Dockerfile), so its health can't be observed directly the
way platform-api's /health can -- only inferred by actually running a job through it. kernel_demo
is a technical smoke-surface product (see docs/product-specs/kernel-demo.md) whose action configs
all use the fake provider, so this is deterministic, fast, and makes no external calls.

Invoked by scripts/agent/runner.py's dev-smoke/prod-smoke commands (same subprocess pattern as
validate_configs.py/quick_check.py), parameterized only by --api-url.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import yaml

FRONTEND_ID = "kernel_demo_ce"
REPO_ROOT = Path(__file__).resolve().parents[2]
ACTION_DEFINITIONS_ROOT = REPO_ROOT / "configs" / "kernel" / "action_definitions"
ATOM_MATRIX_DATA_PATH = REPO_ROOT / "tests" / "fixtures" / "kernel_demo" / "atom_smoke_matrix.json"
WORKFLOWS_CONFIG_PATH = (
    REPO_ROOT / "configs" / "kernel" / "products" / "kernel_demo" / "workflows.yaml"
)
SCENARIOS_CONFIG_PATH = (
    REPO_ROOT / "configs" / "kernel" / "products" / "kernel_demo" / "scenarios.yaml"
)
_COMPOSITE_WORKFLOW_ID_PREFIX = "kernel_demo.composite_"


def _load_raw_atom_cases() -> list[dict]:
    """Parses tests/fixtures/kernel_demo/atom_smoke_matrix.json once. Exposed as
    _RAW_ATOM_CASES (not just consumed internally) so
    apps/platform-api/tests/test_atom_runtime_matrix.py's ATOM_MATRIX can build its AtomCase
    objects directly from this already-parsed list instead of independently re-opening and
    re-parsing the same file with its own separate field-selection logic -- one parse, two
    consumers, instead of two hand-written parsers that could each drop/rename a key
    differently.
    """
    with ATOM_MATRIX_DATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


# Loaded once at import time, but guarded: a missing/corrupted data file must still let this
# script run far enough to print a clear SMOKE00x error, not crash with a raw traceback before
# argparse or main() ever runs.
_ATOM_MATRIX_LOAD_ERROR: str | None = None
try:
    _RAW_ATOM_CASES: list[dict] = _load_raw_atom_cases()
    ATOM_SMOKE_CASES: tuple[tuple[str, str, dict], ...] = tuple(
        (case["action_type"], case["scenario_id"], case["start_input"]) for case in _RAW_ATOM_CASES
    )
    # scenario_id -> the schema_ref that scenario's produced artifact must have. The API's
    # /v1/results/{id} exposes schema_ref but not action_type/action_config_id (those are
    # internal, not part of the frontend-safe result surface, and this script has no DB access
    # to check them directly) -- schema_ref is a reliable HTTP-visible fingerprint of "did this
    # scenario actually run its own declared action", since every atom has a distinct output
    # schema. Used by _run_one_case to catch a scenario wired to the wrong workflow/action.
    _EXPECTED_SCHEMA_REF_BY_SCENARIO: dict[str, str] = {
        case["scenario_id"]: case["expected_output_schema_ref"] for case in _RAW_ATOM_CASES
    }
except (OSError, ValueError, KeyError, TypeError) as exc:
    _RAW_ATOM_CASES = []
    ATOM_SMOKE_CASES = ()
    _EXPECTED_SCHEMA_REF_BY_SCENARIO = {}
    _ATOM_MATRIX_LOAD_ERROR = (
        f"SMOKE008: could not load atom smoke case data from {ATOM_MATRIX_DATA_PATH}: {exc}"
    )


def _required_action_types() -> frozenset[str]:
    """Derives required coverage from configs/kernel/action_definitions/*.yaml -- the source
    of truth for "generic action type" -- instead of a hardcoded list that a newly added atom
    wouldn't move, so this check keeps catching drift as the kernel grows.

    ponytail: a raw filename glob, not the validated ConfigLoader registry the pytest matrix
    uses (this script intentionally has no backend-package imports). A malformed/placeholder
    file here would diverge between the two checks; validate-configs (the `baseline` CI job)
    independently fails on that same file, but as a sibling job with no `needs:` ordering
    against `compose-smoke-dev`/`compose-smoke-prod` (this script), not a gate strictly in
    front of it -- so a malformed file could in principle fail this script's coverage check
    before/concurrently with baseline's own failure. Upgrade to the validated registry if this
    script ever needs a real ordering guarantee instead of two independent parallel checks.
    """
    return frozenset(path.stem for path in ACTION_DEFINITIONS_ROOT.glob("*.yaml"))


def _required_composite_workflow_ids() -> frozenset[str]:
    """Derives required composite coverage from workflows.yaml's own declared workflow_ids,
    filtered to the kernel_demo.composite_ naming convention -- the composite counterpart of
    _required_action_types() above, adapted because all composite workflows share one YAML file
    instead of one file per atom. Raw YAML parse, not the validated ConfigLoader registry (same
    intentional no-backend-package-imports design as the rest of this script).

    ponytail: shares _required_action_types()'s CI-ordering caveat -- this script and the
    validate-configs baseline job are siblings with no `needs:` ordering, so a malformed
    workflows.yaml could in principle fail this coverage check before/concurrently with
    baseline's own failure, same trade-off documented there."""
    with WORKFLOWS_CONFIG_PATH.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return frozenset(
        entry["workflow_id"]
        for entry in data.get("workflows", [])
        if isinstance(entry, dict)
        and isinstance(entry.get("workflow_id"), str)
        and entry["workflow_id"].startswith(_COMPOSITE_WORKFLOW_ID_PREFIX)
    )


def _required_composite_workflow_id_by_scenario_id() -> dict[str, str]:
    """Derives the real composite scenario_id -> workflow_id binding declared in
    scenarios.yaml, filtered to composite workflows. Used to verify COMPOSITE_SMOKE_CASES'
    (workflow_id, scenario_id) pairs match the actual config binding, not just that both sides
    independently look plausible -- catches a scenario_id swapped between two composite entries,
    which a duplicate-workflow_id or duplicate-scenario_id check alone would miss (each
    workflow_id and scenario_id would still individually be unique, just paired with the wrong
    partner)."""
    with SCENARIOS_CONFIG_PATH.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return {
        entry["scenario_id"]: entry["workflow_id"]
        for entry in data.get("scenarios", [])
        if isinstance(entry, dict)
        and isinstance(entry.get("scenario_id"), str)
        and isinstance(entry.get("workflow_id"), str)
        and entry["workflow_id"].startswith(_COMPOSITE_WORKFLOW_ID_PREFIX)
    }


def _coverage_mismatch_error(
    covered: set[str], required: frozenset[str], *, error_code: str, tuple_name: str, kind: str
) -> str:
    missing = sorted(required - covered)
    extra = sorted(covered - required)
    return (
        f"{error_code}: {tuple_name} does not cover the required {len(required)} {kind} "
        f"(missing={missing}, extra={extra})"
    )


COMPOSITE_SMOKE_CASES: tuple[tuple[str, str, dict], ...] = (
    (
        "kernel_demo.composite_analyze_and_clarify_v1",
        "kernel_demo.composite_analyze_and_clarify_smoke_v1",
        {
            "source_text": "We need this soon.",
            "fields": [
                {
                    "name": "deadline",
                    "type": "string",
                    "description": "Project deadline mentioned in the text.",
                    "required": True,
                },
                {
                    "name": "budget",
                    "type": "string",
                    "description": "Budget mentioned in the text.",
                    "required": False,
                },
                {
                    "name": "deliverables",
                    "type": "array_of_strings",
                    "description": "Deliverables mentioned in the text.",
                    "required": False,
                },
            ],
            "strict": False,
        },
    ),
    (
        "kernel_demo.composite_evaluate_match_v1",
        "kernel_demo.composite_evaluate_match_smoke_v1",
        {"source_text": "The proposal states its point directly."},
    ),
    (
        "kernel_demo.composite_shape_and_write_v1",
        "kernel_demo.composite_shape_and_write_smoke_v1",
        {"source_text": "The proposal does not state a delivery date."},
    ),
)


def _composite_output_schema_ref_by_workflow_id() -> dict[str, str]:
    """Parses workflows.yaml's own output_schema_ref per composite workflow_id -- shared by
    _composite_coverage_error() (to fail SMOKE010 loudly on a missing/invalid output_schema_ref
    instead of silently dropping the workflow's scenario from schema_ref coverage) and
    _composite_expected_schema_ref_by_scenario_id() below (to build the scenario_id lookup)."""
    with WORKFLOWS_CONFIG_PATH.open("r", encoding="utf-8") as handle:
        workflows_data = yaml.safe_load(handle)
    return {
        entry["workflow_id"]: entry["output_schema_ref"]
        for entry in workflows_data.get("workflows", [])
        if isinstance(entry, dict)
        and isinstance(entry.get("workflow_id"), str)
        and isinstance(entry.get("output_schema_ref"), str)
    }


def _composite_expected_schema_ref_by_scenario_id() -> dict[str, str]:
    """Derives scenario_id -> output_schema_ref for composite scenarios from workflows.yaml's
    own output_schema_ref field, joined through the real scenario_id -> workflow_id binding in
    scenarios.yaml -- avoids 3 hardcoded literal schema refs drifting from workflows.yaml, the
    same risk _required_composite_workflow_ids() above already guards against for coverage."""
    output_schema_ref_by_workflow_id = _composite_output_schema_ref_by_workflow_id()
    return {
        scenario_id: output_schema_ref_by_workflow_id[workflow_id]
        for scenario_id, workflow_id in _required_composite_workflow_id_by_scenario_id().items()
        if workflow_id in output_schema_ref_by_workflow_id
    }


# Extends _EXPECTED_SCHEMA_REF_BY_SCENARIO (built above from the atom fixtures) with the
# composite scenarios' output_schema_ref so SMOKE009 also catches a composite scenario wired to
# the wrong workflow, not just the 11 atom cases. Failures here are swallowed: main() runs
# _composite_coverage_error() (SMOKE010) before run() ever needs this dict, so a malformed
# workflows.yaml/scenarios.yaml is reported there with a clear error instead of an import-time
# traceback.
with contextlib.suppress(OSError, yaml.YAMLError, AttributeError, TypeError, KeyError):
    _EXPECTED_SCHEMA_REF_BY_SCENARIO.update(_composite_expected_schema_ref_by_scenario_id())


POLL_INTERVAL_SECONDS = 0.5
DEFAULT_TIMEOUT_SECONDS = 30.0


def _atom_coverage_error(cases: tuple[tuple[str, str, dict], ...]) -> str | None:
    action_types = [action_type for action_type, _, _ in cases]
    if len(action_types) != len(set(action_types)):
        return "SMOKE007: ATOM_SMOKE_CASES has duplicate action_type entries"
    if not ACTION_DEFINITIONS_ROOT.is_dir():
        return (
            f"SMOKE007: cannot verify required atom coverage -- {ACTION_DEFINITIONS_ROOT} "
            "not found (expected a full repo checkout with configs/kernel/action_definitions/ "
            "two levels above this script)"
        )
    covered = set(action_types)
    required = _required_action_types()
    if covered != required:
        return _coverage_mismatch_error(
            covered,
            required,
            error_code="SMOKE007",
            tuple_name="ATOM_SMOKE_CASES",
            kind="action types",
        )
    return None


def _composite_coverage_error(cases: tuple[tuple[str, str, dict], ...]) -> str | None:
    """Composite counterpart of _atom_coverage_error() -- catches not just an empty
    COMPOSITE_SMOKE_CASES but also a partial one (e.g. a merge drops 1 of 3 entries), a reused
    scenario_id (silently dropping the workflow whose scenario it displaced), and a scenario_id
    swapped onto the wrong workflow_id label (each side would still individually be unique, just
    paired with the wrong partner -- a bare duplicate check on either side alone would miss it)."""
    workflow_ids = [workflow_id for workflow_id, _, _ in cases]
    scenario_ids = [scenario_id for _, scenario_id, _ in cases]
    for field_name, ids in (("workflow_id", workflow_ids), ("scenario_id", scenario_ids)):
        if len(ids) != len(set(ids)):
            return f"SMOKE010: COMPOSITE_SMOKE_CASES has duplicate {field_name} entries"
    for config_path in (WORKFLOWS_CONFIG_PATH, SCENARIOS_CONFIG_PATH):
        if not config_path.is_file():
            return (
                f"SMOKE010: cannot verify required composite coverage -- {config_path} not found"
            )
    try:
        required = _required_composite_workflow_ids()
        workflow_id_by_scenario_id = _required_composite_workflow_id_by_scenario_id()
        output_schema_ref_by_workflow_id = _composite_output_schema_ref_by_workflow_id()
        missing_schema_ref = sorted(required - output_schema_ref_by_workflow_id.keys())
        if missing_schema_ref:
            raise ValueError(
                f"missing/invalid output_schema_ref for workflow(s): {missing_schema_ref}"
            )
    except (OSError, yaml.YAMLError, AttributeError, TypeError, ValueError) as exc:
        return (
            "SMOKE010: could not parse composite workflow/scenario config to verify required "
            f"composite coverage: {exc}"
        )
    covered = set(workflow_ids)
    if covered != required:
        return _coverage_mismatch_error(
            covered,
            required,
            error_code="SMOKE010",
            tuple_name="COMPOSITE_SMOKE_CASES",
            kind="composite workflows",
        )
    for workflow_id, scenario_id in zip(workflow_ids, scenario_ids, strict=True):
        expected_workflow_id = workflow_id_by_scenario_id.get(scenario_id)
        if expected_workflow_id != workflow_id:
            return (
                f"SMOKE010: COMPOSITE_SMOKE_CASES pairs scenario {scenario_id!r} with workflow "
                f"{workflow_id!r}, but scenarios.yaml binds that scenario to "
                f"{expected_workflow_id!r} -- scenario/workflow mismatch"
            )
    return None


def _http_json_request(
    url: str, *, method: str = "GET", payload: dict | None = None, timeout: float = 5.0
) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


_TIMEOUT_ERROR_CODE = "SMOKE005"


@dataclass(frozen=True)
class CaseResult:
    """session_id is populated as soon as it's known (even for a later-stage failure, so a
    failing case can still be correlated back to its DB rows); error_code/error_message are
    both None on success. error_code is a plain SMOKE0xx string compared by equality --
    run()'s timeout-degrade decision checks this typed field, not a substring/prefix sniff on
    error_message."""

    session_id: str | None
    error_code: str | None
    error_message: str | None


def _run_one_case(api_url: str, scenario_id: str, scenario_input: dict, timeout: float) -> CaseResult:
    """Runs one scenario to completion under its own fresh guest identity (kernel_demo's
    guest quota is a shared per-guest lifetime budget across scenarios, smaller than the
    number of atoms in the matrix, so every case needs its own guest)."""
    try:
        guest = _http_json_request(f"{api_url}/v1/identity/guest", method="POST")
        guest_id = guest["guest_id"]
        start = _http_json_request(
            f"{api_url}/v1/products/kernel_demo/scenarios/{scenario_id}/start",
            method="POST",
            payload={
                "frontend_id": FRONTEND_ID,
                "guest_id": guest_id,
                "input": scenario_input,
            },
        )
        session_id = start["scenario_session_id"]
    except (
        OSError,
        urllib.error.URLError,
        KeyError,
        ValueError,
        TypeError,
        AttributeError,
    ) as exc:
        return CaseResult(
            session_id=None,
            error_code="SMOKE001",
            error_message=f"SMOKE001: could not start scenario {scenario_id} against {api_url}: {exc}",
        )

    session_url = f"{api_url}/v1/scenario-sessions/{session_id}"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            session = _http_json_request(session_url, timeout=5.0)
            status = session.get("status")
        except (OSError, urllib.error.URLError, ValueError, TypeError, AttributeError) as exc:
            return CaseResult(
                session_id=session_id,
                error_code="SMOKE002",
                error_message=(
                    f"SMOKE002: lost contact with {session_url} while polling for "
                    f"completion: {exc}"
                ),
            )
        if status == "completed":
            result_artifact_id = session.get("result_artifact_id")
            if not result_artifact_id:
                return CaseResult(
                    session_id=session_id,
                    error_code="SMOKE003",
                    error_message=(
                        f"SMOKE003: kernel_demo session {session_id} completed without a "
                        "result artifact"
                    ),
                )
            expected_schema_ref = _EXPECTED_SCHEMA_REF_BY_SCENARIO.get(scenario_id)
            if expected_schema_ref is not None:
                try:
                    result = _http_json_request(
                        f"{api_url}/v1/results/{result_artifact_id}", timeout=5.0
                    )
                    actual_schema_ref = result.get("schema_ref")
                except (
                    OSError,
                    urllib.error.URLError,
                    ValueError,
                    TypeError,
                    AttributeError,
                ) as exc:
                    return CaseResult(
                        session_id=session_id,
                        error_code="SMOKE009",
                        error_message=(
                            f"SMOKE009: could not fetch result artifact {result_artifact_id} "
                            f"to verify its schema_ref: {exc}"
                        ),
                    )
                if actual_schema_ref != expected_schema_ref:
                    return CaseResult(
                        session_id=session_id,
                        error_code="SMOKE009",
                        error_message=(
                            f"SMOKE009: kernel_demo session {session_id} (scenario "
                            f"{scenario_id}) produced schema_ref {actual_schema_ref!r}, "
                            f"expected {expected_schema_ref!r} -- scenario may be wired to "
                            "the wrong workflow/action"
                        ),
                    )
            return CaseResult(session_id=session_id, error_code=None, error_message=None)
        if status == "failed":
            return CaseResult(
                session_id=session_id,
                error_code="SMOKE004",
                error_message=f"SMOKE004: kernel_demo session {session_id} failed: {session}",
            )
        time.sleep(POLL_INTERVAL_SECONDS)

    return CaseResult(
        session_id=session_id,
        error_code=_TIMEOUT_ERROR_CODE,
        error_message=(
            f"{_TIMEOUT_ERROR_CODE}: kernel_demo smoke check timed out after {timeout:g}s "
            f"waiting for session {session_id} (scenario {scenario_id}) to complete. Is "
            "platform-worker running and healthy? Rerun with a longer "
            "--timeout/ANYTOOLAI_SMOKE_TIMEOUT if needed."
        ),
    )


DEGRADED_TIMEOUT_SECONDS = 5.0


def _run_case_batch(
    api_url: str,
    cases: tuple[tuple[str, str, dict], ...],
    timeout: float,
    case_timeout: float,
) -> tuple[int, float]:
    """Runs every case in cases sequentially, printing a pass/fail line per case, and returns
    (passed_count, case_timeout). A completion timeout usually means platform-worker itself
    isn't consuming jobs, in which case every remaining case would also time out -- but it could
    also be a genuine per-case bug, so every case still runs (skipping would hide real
    regressions). What's bounded instead is the cost: right after a timeout, the next case gets
    a short probe timeout (DEGRADED_TIMEOUT_SECONDS) rather than the full budget. That degrade is
    NOT permanent -- any case that doesn't time out (success or a different failure) restores the
    full timeout for the cases after it, so one slow-but-legitimate case can't silently cap every
    case that follows it. Callers chain the returned case_timeout into the next batch (atoms then
    composites) so a worker outage detected during the atom batch keeps the composite batch cheap
    too, instead of resetting to the full budget for it."""
    passed = 0
    for label, scenario_id, scenario_input in cases:
        result = _run_one_case(api_url, scenario_id, scenario_input, case_timeout)
        if result.error_message is None:
            passed += 1
            print(f"{label}: {scenario_id} -> ok (session {result.session_id})")
            case_timeout = timeout
        else:
            print(f"{label}: {scenario_id} -> failed ({result.error_message})", file=sys.stderr)
            case_timeout = (
                min(case_timeout, DEGRADED_TIMEOUT_SECONDS)
                if result.error_code == _TIMEOUT_ERROR_CODE
                else timeout
            )
    return passed, case_timeout


def run(api_url: str, timeout: float) -> int:
    total = len(ATOM_SMOKE_CASES)
    if not ATOM_SMOKE_CASES:
        print("SMOKE007: ATOM_SMOKE_CASES is empty -- nothing to smoke-test", file=sys.stderr)
        return 1

    passed, case_timeout = _run_case_batch(api_url, ATOM_SMOKE_CASES, timeout, timeout)
    print(f"{passed}/{total} kernel_demo atoms passed")

    composite_total = len(COMPOSITE_SMOKE_CASES)
    if not COMPOSITE_SMOKE_CASES:
        print(
            "SMOKE010: COMPOSITE_SMOKE_CASES is empty -- nothing to smoke-test", file=sys.stderr
        )
        return 1

    composite_passed, _case_timeout = _run_case_batch(
        api_url, COMPOSITE_SMOKE_CASES, timeout, case_timeout
    )
    print(f"{composite_passed}/{composite_total} kernel_demo composite workflows passed")
    return 0 if passed == total and composite_passed == composite_total else 1


def _default_timeout() -> float:
    raw = os.environ.get("ANYTOOLAI_SMOKE_TIMEOUT")
    if raw is None:
        return DEFAULT_TIMEOUT_SECONDS
    return float(raw)


def main() -> int:
    if _ATOM_MATRIX_LOAD_ERROR is not None:
        print(_ATOM_MATRIX_LOAD_ERROR, file=sys.stderr)
        return 1

    try:
        default_timeout = _default_timeout()
    except ValueError as exc:
        print(f"SMOKE006: ANYTOOLAI_SMOKE_TIMEOUT must be a number: {exc}", file=sys.stderr)
        return 2

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "api_url", help="Base URL of a live platform-api, e.g. http://127.0.0.1:8000"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=default_timeout,
        help="Seconds to wait for the scenario to complete (default: %(default)s, "
        "also settable via ANYTOOLAI_SMOKE_TIMEOUT)",
    )
    args = parser.parse_args()

    coverage_error = _atom_coverage_error(ATOM_SMOKE_CASES)
    if coverage_error is not None:
        print(coverage_error, file=sys.stderr)
        return 1

    composite_coverage_error = _composite_coverage_error(COMPOSITE_SMOKE_CASES)
    if composite_coverage_error is not None:
        print(composite_coverage_error, file=sys.stderr)
        return 1

    return run(args.api_url.rstrip("/"), args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
