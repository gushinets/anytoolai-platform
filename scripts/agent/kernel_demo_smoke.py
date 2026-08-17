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

FRONTEND_ID = "kernel_demo_ce"

# One (action_type, scenario_id, start_input) tuple per generic action type -- the same 11
# cases ATOM_MATRIX in apps/platform-api/tests/test_atom_runtime_matrix.py exercises over
# pytest's in-process ASGI transport. Bounded duplication of these literals across that
# pytest file and this stdlib-only script is deliberate: this script has no backend-package
# imports so it can run against a container that only has the image's runtime dependencies,
# not the test suite's.
ATOM_SMOKE_CASES = (
    (
        "text.extract_structured_fields",
        "kernel_demo.single_action_smoke_v1",
        {
            "source_text": "deadline budget deliverables",
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
        "text.detect_issues_by_taxonomy",
        "kernel_demo.single_action_detect_issues_smoke_v1",
        {"source_text": "We need this soon."},
    ),
    (
        "document.generate_from_template",
        "kernel_demo.single_action_generate_report_smoke_v1",
        {"source_text": "The project is on track."},
    ),
    (
        "text.compose_reply",
        "kernel_demo.single_action_compose_reply_smoke_v1",
        {"source_text": "Sorry about the delay, can you send an update?"},
    ),
    (
        "text.generate_clarifying_questions",
        "kernel_demo.single_action_generate_clarifying_questions_smoke_v1",
        {"source_text": "We need this done soon, no date given."},
    ),
    (
        "text.synthesize_angle",
        "kernel_demo.single_action_synthesize_angle_smoke_v1",
        {"source_text": "unused by this workflow, kept for input-shape parity"},
    ),
    (
        "text.compose_persuasive_text",
        "kernel_demo.single_action_compose_persuasive_text_smoke_v1",
        {"source_text": "unused by this workflow, kept for input-shape parity"},
    ),
    (
        "text.generate_gap_rewrites",
        "kernel_demo.single_action_generate_gap_rewrites_smoke_v1",
        {"source_text": "The proposal does not state a delivery date."},
    ),
    (
        "text.compare_and_classify",
        "kernel_demo.single_action_compare_and_classify_smoke_v1",
        {"source_text": "Subject text for comparison."},
    ),
    (
        "text.score_match_by_rubric",
        "kernel_demo.single_action_score_match_by_rubric_smoke_v1",
        {"source_text": "Reference text A for scoring."},
    ),
    (
        "text.score_multidimensional_axes",
        "kernel_demo.single_action_score_multidimensional_axes_smoke_v1",
        {"source_text": "The proposal states its point directly."},
    ),
)
POLL_INTERVAL_SECONDS = 0.5
DEFAULT_TIMEOUT_SECONDS = 30.0


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


def _run_one_case(
    api_url: str, scenario_id: str, scenario_input: dict, timeout: float
) -> str | None:
    """Runs one scenario to completion under its own fresh guest identity (kernel_demo's
    guest quota is a shared per-guest lifetime budget across scenarios, smaller than the
    number of atoms in the matrix, so every case needs its own guest). Returns None on
    success, else a SMOKE0xx error line."""
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
        return f"SMOKE001: could not start scenario {scenario_id} against {api_url}: {exc}"

    session_url = f"{api_url}/v1/scenario-sessions/{session_id}"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            session = _http_json_request(session_url, timeout=5.0)
            status = session.get("status")
        except (OSError, urllib.error.URLError, ValueError, TypeError, AttributeError) as exc:
            return (
                f"SMOKE002: lost contact with {session_url} while polling for completion: {exc}"
            )
        if status == "completed":
            if not session.get("result_artifact_id"):
                return (
                    f"SMOKE003: kernel_demo session {session_id} completed without a "
                    "result artifact"
                )
            return None
        if status == "failed":
            return f"SMOKE004: kernel_demo session {session_id} failed: {session}"
        time.sleep(POLL_INTERVAL_SECONDS)

    return (
        f"SMOKE005: kernel_demo smoke check timed out after {timeout:g}s waiting for session "
        f"{session_id} (scenario {scenario_id}) to complete. Is platform-worker running and "
        "healthy? Rerun with a longer --timeout/ANYTOOLAI_SMOKE_TIMEOUT if needed."
    )


def run(api_url: str, timeout: float) -> int:
    passed = 0
    for action_type, scenario_id, scenario_input in ATOM_SMOKE_CASES:
        error = _run_one_case(api_url, scenario_id, scenario_input, timeout)
        if error is None:
            passed += 1
            print(f"{action_type}: {scenario_id} -> ok")
        else:
            print(f"{action_type}: {scenario_id} -> failed ({error})", file=sys.stderr)

    total = len(ATOM_SMOKE_CASES)
    print(f"{passed}/{total} kernel_demo atoms passed")
    return 0 if passed == total else 1


def _default_timeout() -> float:
    raw = os.environ.get("ANYTOOLAI_SMOKE_TIMEOUT")
    if raw is None:
        return DEFAULT_TIMEOUT_SECONDS
    return float(raw)


def main() -> int:
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
    return run(args.api_url.rstrip("/"), args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
