#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VENV_DIR = ROOT / ".venv" / "quick-check"
EDITABLE_PROJECTS = [
    ROOT / "packages" / "backend" / "platform-sdk",
    ROOT / "packages" / "backend" / "platform-core",
    ROOT / "packages" / "backend" / "platform-actions",
    ROOT / "apps" / "platform-api",
    ROOT / "apps" / "platform-worker",
]
PYTEST_TARGETS = [
    "tests/architecture",
    "packages/backend/platform-sdk/tests",
    "packages/backend/platform-core/tests",
    "packages/backend/platform-actions/tests",
    "apps/platform-api/tests",
    "apps/platform-worker/tests",
]


def print_command(command: Sequence[str]) -> None:
    print("+ " + " ".join(command), flush=True)


def run(command: Sequence[str]) -> int:
    print_command(command)
    try:
        completed = subprocess.run(
            list(command),
            cwd=ROOT,
            shell=False,
            check=False,
        )
    except FileNotFoundError as exc:
        print(f"Command not found: {exc.filename}", file=sys.stderr)
        return 127
    return completed.returncode


def run_with_env(command: Sequence[str], env: dict[str, str]) -> int:
    print_command(command)
    try:
        completed = subprocess.run(
            list(command),
            cwd=ROOT,
            env=env,
            shell=False,
            check=False,
        )
    except FileNotFoundError as exc:
        print(f"Command not found: {exc.filename}", file=sys.stderr)
        return 127
    return completed.returncode


def run_sequence(commands: Sequence[Sequence[str]]) -> int:
    for command in commands:
        exit_code = run(command)
        if exit_code != 0:
            return exit_code
    return 0


def venv_python() -> Path:
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    python_name = "python.exe" if os.name == "nt" else "python"
    return VENV_DIR / scripts_dir / python_name


def is_quick_check_environment() -> bool:
    try:
        return Path(sys.prefix).resolve() == VENV_DIR.resolve()
    except OSError:
        return False


def ensure_virtualenv() -> int | None:
    expected_python = venv_python()
    if not expected_python.exists():
        exit_code = run([sys.executable, "-m", "venv", str(VENV_DIR)])
        if exit_code != 0:
            return exit_code

    if is_quick_check_environment():
        return None
    if os.environ.get("ANYTOOLAI_QUICK_CHECK_BOOTSTRAPPED") == "1":
        print(
            "Quick-check bootstrap expected to re-enter via .venv/quick-check but did not.",
            file=sys.stderr,
        )
        return 1

    env = os.environ.copy()
    env["ANYTOOLAI_QUICK_CHECK_BOOTSTRAPPED"] = "1"
    return run_with_env([str(expected_python), str(Path(__file__).resolve())], env)


def bootstrap() -> int:
    commands: list[list[str]] = [
        [sys.executable, "-m", "pip", "install", "setuptools>=68", "wheel"],
        [sys.executable, "-m", "pip", "install", "--no-build-isolation", "-e", ".[dev]"],
    ]
    for project in EDITABLE_PROJECTS:
        commands.append(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-build-isolation",
                "--no-deps",
                "-e",
                str(project),
            ]
        )
    return run_sequence(commands)


def main() -> int:
    exit_code = ensure_virtualenv()
    if exit_code is not None:
        return exit_code

    exit_code = bootstrap()
    if exit_code != 0:
        return exit_code

    return run_sequence(
        [
            [sys.executable, "scripts/agent/validate_configs.py"],
            [sys.executable, "scripts/agent/validate_architecture.py"],
            [sys.executable, "-m", "pytest", *PYTEST_TARGETS],
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
