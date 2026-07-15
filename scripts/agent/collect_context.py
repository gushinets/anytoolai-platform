#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[2]
PLATFORM_CORE_SRC = ROOT / "packages" / "backend" / "platform-core" / "src"
SCRIPT_DIR = Path(__file__).resolve().parent
for source_root in (PLATFORM_CORE_SRC, SCRIPT_DIR):
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))

from anytoolai_platform_core.common.logging import sanitize
import runner

MAX_OUTPUT = 20000
SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(password|secret|credential|authorization|cookie|token|api[_-]?key)"
    r"\s*[:=]\s*([^\s,;]+)"
)


def sanitize_text(value: str) -> str:
    generally_sanitized = str(sanitize(value))
    assigned = SECRET_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}=[REDACTED]",
        generally_sanitized,
    )
    return assigned[:MAX_OUTPUT]


def _run(command: Sequence[str], *, env: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            list(command),
            cwd=ROOT,
            env=env,
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        output = (completed.stdout + completed.stderr).strip()
        return {
            "command": list(command),
            "exit_code": completed.returncode,
            "output": sanitize_text(output),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "command": list(command),
            "exit_code": None,
            "output": sanitize_text(f"{type(exc).__name__}: {exc}"),
        }


def _tool_versions() -> dict[str, dict[str, Any]]:
    commands = {
        "python": [sys.executable, "--version"],
        "uv": ["uv", "--version"],
        "git": ["git", "--version"],
        "node": ["node", "--version"],
        "pnpm": ["pnpm", "--version"],
        "docker": ["docker", "version", "--format", "{{.Client.Version}}"],
    }
    return {name: _run(command) for name, command in commands.items()}


def _active_plans() -> list[dict[str, str]]:
    plans: list[dict[str, str]] = []
    for plan in sorted((ROOT / "docs" / "exec-plans" / "active").glob("*.md")):
        text = plan.read_text(encoding="utf-8")
        state = re.search(r"(?m)^- State:\s*(\S+)", text)
        next_action = re.search(r"(?m)^- Next action:\s*(.+)", text)
        plans.append(
            {
                "file": str(plan.relative_to(ROOT)),
                "state": state.group(1) if state else "unknown",
                "next_action": sanitize_text(next_action.group(1)) if next_action else "unknown",
            }
        )
    return plans


def collect(*, failure_file: Path | None = None, log_lines: int = 100) -> dict[str, Any]:
    identity = runner.runtime_identity()
    compose_env = runner._compose_env(identity)
    payload: dict[str, Any] = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "repository": str(ROOT),
        "tools": _tool_versions(),
        "git": {
            "status": _run(["git", "status", "--short"]),
            "diff_summary": _run(["git", "diff", "--stat"]),
        },
        "active_plans": _active_plans(),
        "runtime": {
            "compose_project": identity.compose_project,
            "api_url": identity.api_url,
            "database_endpoint": (
                f"postgresql://127.0.0.1:{identity.postgres_port}/anytoolai"
            ),
            "compose_status": _run(
                runner._compose_command(identity, "ps"),
                env=compose_env,
            ),
            "recent_logs": _run(
                runner._compose_command(
                    identity,
                    "logs",
                    "--no-color",
                    "--tail",
                    str(max(1, min(log_lines, 1000))),
                    "platform-api",
                    "platform-worker",
                ),
                env=compose_env,
            ),
        },
    }
    if failure_file is not None:
        try:
            payload["failure"] = {
                "file": str(failure_file),
                "output": sanitize_text(failure_file.read_text(encoding="utf-8")),
            }
        except OSError as exc:
            payload["failure"] = {
                "file": str(failure_file),
                "output": sanitize_text(f"{type(exc).__name__}: {exc}"),
            }
    return sanitize(payload)


def write_bundle(
    *,
    output_root: Path | None = None,
    failure_file: Path | None = None,
    log_lines: int = 100,
) -> Path:
    target_root = output_root or ROOT / ".agent" / "context"
    target_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    target = target_root / f"context-{timestamp}.json"
    target.write_text(
        json.dumps(
            collect(failure_file=failure_file, log_lines=log_lines),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def main() -> int:
    target = write_bundle()
    print(f"Sanitized context written to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
