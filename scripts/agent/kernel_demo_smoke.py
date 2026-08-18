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
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

FRONTEND_ID = "kernel_demo_ce"
REPO_ROOT = Path(__file__).resolve().parents[2]
ACTION_DEFINITIONS_ROOT = REPO_ROOT / "configs" / "kernel" / "action_definitions"
ATOM_MATRIX_DATA_PATH = REPO_ROOT / "tests" / "fixtures" / "kernel_demo" / "atom_smoke_matrix.json"


def _load_atom_smoke_cases() -> tuple[tuple[str, str, dict], ...]:
    """Loads the (action_type, scenario_id, start_input) triples from the JSON file that is
    also the source ATOM_MATRIX in apps/platform-api/tests/test_atom_runtime_matrix.py loads
    -- one shared data file instead of two independently hand-maintained Python literals, so
    a scenario_id rename or start_input change can't drift between the two consumers. Reading
    plain JSON (not importing the pytest file) keeps this script's stdlib-only, no
    backend-package-import constraint intact.
    """
    with ATOM_MATRIX_DATA_PATH.open("r", encoding="utf-8") as handle:
        cases = json.load(handle)
    return tuple((case["action_type"], case["scenario_id"], case["start_input"]) for case in cases)


# Loaded once at import time, but guarded: a missing/corrupted data file must still let this
# script run far enough to print a clear SMOKE00x error, not crash with a raw traceback before
# argparse or main() ever runs.
_ATOM_MATRIX_LOAD_ERROR: str | None = None
try:
    ATOM_SMOKE_CASES: tuple[tuple[str, str, dict], ...] = _load_atom_smoke_cases()
except (OSError, ValueError, KeyError, TypeError) as exc:
    ATOM_SMOKE_CASES = ()
    _ATOM_MATRIX_LOAD_ERROR = (
        f"SMOKE008: could not load atom smoke case data from {ATOM_MATRIX_DATA_PATH}: {exc}"
    )


def _required_action_types() -> frozenset[str]:
    """Derives required coverage from configs/kernel/action_definitions/*.yaml -- the source
    of truth for "generic action type" -- instead of a hardcoded list that a newly added atom
    wouldn't move, so this check keeps catching drift as the kernel grows.

    ponytail: a raw filename glob, not the validated ConfigLoader registry the pytest matrix
    uses (this script intentionally has no backend-package imports). A malformed/placeholder
    file here would diverge between the two checks; validate-configs already fails on that
    independently, so upgrade only if this script ever needs to run without a validate-configs
    gate in front of it.
    """
    return frozenset(path.stem for path in ACTION_DEFINITIONS_ROOT.glob("*.yaml"))


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
        missing = sorted(required - covered)
        extra = sorted(covered - required)
        return (
            f"SMOKE007: ATOM_SMOKE_CASES does not cover the required {len(required)} action "
            f"types (missing={missing}, extra={extra})"
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
            if not session.get("result_artifact_id"):
                return CaseResult(
                    session_id=session_id,
                    error_code="SMOKE003",
                    error_message=(
                        f"SMOKE003: kernel_demo session {session_id} completed without a "
                        "result artifact"
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


def run(api_url: str, timeout: float) -> int:
    total = len(ATOM_SMOKE_CASES)
    if total == 0:
        print("SMOKE007: ATOM_SMOKE_CASES is empty -- nothing to smoke-test", file=sys.stderr)
        return 1

    passed = 0
    # A completion timeout usually means platform-worker itself isn't consuming jobs, in which
    # case every remaining case would also time out -- but it could also be a genuine per-atom
    # bug, so every case still runs (skipping would hide real regressions). What's bounded
    # instead is the cost: right after a timeout, the next case gets a short probe timeout
    # rather than the full budget. That degrade is NOT permanent -- any case that doesn't time
    # out (success or a different failure) restores the full timeout for the cases after it, so
    # one slow-but-legitimate atom can't silently cap every atom that follows it.
    case_timeout = timeout
    for action_type, scenario_id, scenario_input in ATOM_SMOKE_CASES:
        result = _run_one_case(api_url, scenario_id, scenario_input, case_timeout)
        if result.error_message is None:
            passed += 1
            print(f"{action_type}: {scenario_id} -> ok (session {result.session_id})")
            case_timeout = timeout
        else:
            print(f"{action_type}: {scenario_id} -> failed ({result.error_message})", file=sys.stderr)
            case_timeout = (
                min(case_timeout, DEGRADED_TIMEOUT_SECONDS)
                if result.error_code == _TIMEOUT_ERROR_CODE
                else timeout
            )

    print(f"{passed}/{total} kernel_demo atoms passed")
    return 0 if passed == total else 1


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

    return run(args.api_url.rstrip("/"), args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
