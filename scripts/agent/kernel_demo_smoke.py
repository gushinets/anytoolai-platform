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

SCENARIO_ID = "kernel_demo.single_action_smoke_v1"
FRONTEND_ID = "kernel_demo_ce"
SCENARIO_INPUT = {
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
}
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


def run(api_url: str, timeout: float) -> int:
    try:
        guest = _http_json_request(f"{api_url}/v1/identity/guest", method="POST")
        guest_id = guest["guest_id"]
        start = _http_json_request(
            f"{api_url}/v1/products/kernel_demo/scenarios/{SCENARIO_ID}/start",
            method="POST",
            payload={
                "frontend_id": FRONTEND_ID,
                "guest_id": guest_id,
                "input": SCENARIO_INPUT,
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
        print(
            f"SMOKE001: could not start the kernel_demo smoke scenario against {api_url}: {exc}",
            file=sys.stderr,
        )
        return 1

    session_url = f"{api_url}/v1/scenario-sessions/{session_id}"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            session = _http_json_request(session_url, timeout=5.0)
            status = session.get("status")
        except (OSError, urllib.error.URLError, ValueError, TypeError, AttributeError) as exc:
            print(
                f"SMOKE002: lost contact with {session_url} while polling for completion: {exc}",
                file=sys.stderr,
            )
            return 1
        if status == "completed":
            if not session.get("result_artifact_id"):
                print(
                    f"SMOKE003: kernel_demo session {session_id} completed without a "
                    "result artifact",
                    file=sys.stderr,
                )
                return 1
            print(f"kernel_demo smoke check passed against {api_url} (session {session_id})")
            return 0
        if status == "failed":
            print(
                f"SMOKE004: kernel_demo session {session_id} failed: {session}", file=sys.stderr
            )
            return 1
        time.sleep(POLL_INTERVAL_SECONDS)

    print(
        f"SMOKE005: kernel_demo smoke check timed out after {timeout:g}s waiting for session "
        f"{session_id} to complete. Is platform-worker running and healthy? Rerun with a longer "
        "--timeout/ANYTOOLAI_SMOKE_TIMEOUT if needed.",
        file=sys.stderr,
    )
    return 1


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
