#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VENV_DIR = ROOT / ".quick-check-venv"
LEGACY_VENV_DIR = ROOT / ".venv" / "quick-check"
MINIMUM_PYTHON = (3, 12)
EDITABLE_PROJECTS = [
    ROOT / "packages" / "backend" / "platform-sdk",
    ROOT / "packages" / "backend" / "platform-core",
    ROOT / "packages" / "backend" / "platform-actions",
    ROOT / "apps" / "platform-api",
    ROOT / "apps" / "platform-worker",
]
PYTEST_TARGETS = [
    "tests/architecture",
    "tests/test_quick_check.py",
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


def uv_executable() -> str:
    candidate = shutil.which("uv")
    return candidate if candidate is not None else "uv"


def uv_install_command(*args: str, python: str) -> list[str]:
    return [uv_executable(), "pip", "install", "--python", python, *args]


def python_version(python_executable: Path) -> tuple[int, int] | None:
    try:
        completed = subprocess.run(
            [str(python_executable), "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"],
            cwd=ROOT,
            shell=False,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if completed.returncode != 0:
        return None
    version_text = completed.stdout.strip()
    try:
        major, minor = version_text.split(".", maxsplit=1)
        return int(major), int(minor)
    except ValueError:
        return None


def recreate_virtualenv() -> None:
    shutil.rmtree(VENV_DIR, ignore_errors=True)


def migrate_legacy_virtualenv() -> None:
    if not LEGACY_VENV_DIR.exists():
        return

    shutil.rmtree(LEGACY_VENV_DIR, ignore_errors=True)

    legacy_parent = LEGACY_VENV_DIR.parent
    try:
        legacy_parent.rmdir()
    except OSError:
        pass


def invoking_python_supported() -> bool:
    return sys.version_info >= MINIMUM_PYTHON


def environment_root() -> Path:
    return Path(sys.prefix).resolve()


def is_quick_check_environment() -> bool:
    try:
        return environment_root() == VENV_DIR.resolve()
    except OSError:
        return False


def is_legacy_quick_check_environment() -> bool:
    try:
        return environment_root() == LEGACY_VENV_DIR.resolve()
    except OSError:
        return False


def ensure_virtualenv() -> int | None:
    expected_python = venv_python()
    active_legacy_environment = is_legacy_quick_check_environment()
    existing_version = python_version(expected_python) if expected_python.exists() else None
    if is_quick_check_environment():
        migrate_legacy_virtualenv()
        minimum_version = ".".join(str(part) for part in MINIMUM_PYTHON)
        if sys.version_info < MINIMUM_PYTHON:
            print(
                f"Active {VENV_DIR} uses Python {sys.version_info[0]}.{sys.version_info[1]}, "
                f"but quick-check requires >= {minimum_version}. Re-run the command with a "
                "supported interpreter to recreate the environment.",
                file=sys.stderr,
            )
            return 1
        return None

    if existing_version is not None and existing_version < MINIMUM_PYTHON:
        recreate_virtualenv()
        expected_python = venv_python()
        existing_version = None
    elif expected_python.exists() and existing_version is None:
        recreate_virtualenv()
        expected_python = venv_python()

    if not invoking_python_supported():
        minimum_version = ".".join(str(part) for part in MINIMUM_PYTHON)
        if existing_version is not None:
            env = os.environ.copy()
            env["ANYTOOLAI_QUICK_CHECK_BOOTSTRAPPED"] = "1"
            return run_with_env([str(expected_python), str(Path(__file__).resolve())], env)
        print(
            f"Quick-check requires Python >= {minimum_version} to create {VENV_DIR}. "
            f"Run it with python{minimum_version} or py -{minimum_version}.",
            file=sys.stderr,
        )
        return 1

    if not expected_python.exists():
        exit_code = run([sys.executable, "-m", "venv", str(VENV_DIR)])
        if exit_code != 0:
            return exit_code

    if is_quick_check_environment():
        migrate_legacy_virtualenv()
        return None
    if os.environ.get("ANYTOOLAI_QUICK_CHECK_BOOTSTRAPPED") == "1":
        print(
            "Quick-check bootstrap expected to re-enter via .quick-check-venv but did not.",
            file=sys.stderr,
        )
        return 1

    if not active_legacy_environment:
        migrate_legacy_virtualenv()

    env = os.environ.copy()
    env["ANYTOOLAI_QUICK_CHECK_BOOTSTRAPPED"] = "1"
    return run_with_env([str(expected_python), str(Path(__file__).resolve())], env)


def bootstrap() -> int:
    commands: list[list[str]] = [
        uv_install_command("setuptools>=68", "wheel", python=sys.executable),
        uv_install_command("--no-build-isolation", "-e", ".[dev]", python=sys.executable),
    ]
    for project in EDITABLE_PROJECTS:
        commands.append(
            uv_install_command(
                "--no-build-isolation",
                "--no-deps",
                "-e",
                str(project),
                python=sys.executable,
            )
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
