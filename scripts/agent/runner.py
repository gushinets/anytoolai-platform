#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOTS = [
    ROOT / "packages" / "backend" / "platform-core" / "src",
    ROOT / "packages" / "backend" / "platform-actions" / "src",
    ROOT / "packages" / "backend" / "platform-sdk" / "src",
    ROOT / "packages" / "backend" / "product-platforms" / "freelancer-suite" / "src",
    ROOT / "apps" / "platform-api" / "src",
    ROOT / "apps" / "platform-worker" / "src",
]
QUICK_CHECK_VENV = ROOT / ".quick-check-venv"
FREELANCER_SUITE_ROOT = ROOT / "packages" / "backend" / "product-platforms" / "freelancer-suite"
REQUIRED_MODULES = ["pytest", "yaml", "pydantic"]
OPTIONAL_TOOLS = ["node", "pnpm", "just", "docker"]
ACTION_REGISTRY_ROWS = [
    ("A01 `extract_structured`", "`text.extract_structured_fields`"),
    ("A04 `detect_issues`", "`text.detect_issues_by_taxonomy`"),
    ("A07 `generate_reply`", "`text.compose_reply`"),
    ("A09 `generate_angle`", "`text.synthesize_angle`"),
    ("A10 `generate_document`", "`document.generate_from_template`"),
    ("A11 `compare_classify`", "`text.compare_and_classify`"),
    ("A02 `score_match`", "`text.score_match_by_rubric`"),
    ("A06 `generate_proposal`", "`text.compose_persuasive_text`"),
    ("A08 `generate_rewrites`", "`text.generate_gap_rewrites`"),
    ("A03 `score_multidim`", "`text.score_multidimensional_axes`"),
    ("A05 `generate_questions`", "`text.generate_clarifying_questions`"),
]


def _path_key(value: str) -> str:
    try:
        return os.path.normcase(str(Path(value).resolve()))
    except OSError:
        return os.path.normcase(value)


def build_pythonpath() -> str:
    paths: list[str] = [str(path) for path in SOURCE_ROOTS]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        paths.extend(path for path in existing.split(os.pathsep) if path)

    deduped: list[str] = []
    seen: set[str] = set()
    for path in paths:
        key = _path_key(path)
        if key not in seen:
            deduped.append(path)
            seen.add(key)
    return os.pathsep.join(deduped)


def runner_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = build_pythonpath()
    return env


def print_command(command: Sequence[str]) -> None:
    print("+ " + " ".join(command), flush=True)


def quick_check_python() -> str:
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    python_name = "python.exe" if os.name == "nt" else "python"
    candidate = QUICK_CHECK_VENV / scripts_dir / python_name
    if candidate.exists():
        return str(candidate)
    return sys.executable


def run(command: Sequence[str]) -> int:
    print_command(command)
    try:
        completed = subprocess.run(
            list(command),
            cwd=ROOT,
            env=runner_env(),
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


def doctor() -> int:
    print(f"Repo: {ROOT}")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")

    errors: list[str] = []
    if sys.version_info < (3, 12):  # noqa: UP036 - doctor should report the repo requirement.
        errors.append("Python >= 3.12 is required")

    for module in REQUIRED_MODULES:
        found = importlib.util.find_spec(module) is not None
        print(f"Python module {module}: {'ok' if found else 'missing'}")
        if not found:
            errors.append(f"Missing required Python module: {module}")

    for tool in OPTIONAL_TOOLS:
        path = shutil.which(tool)
        print(f"Optional tool {tool}: {path if path else 'not found'}")

    if errors:
        for error in errors:
            print(f"DOCTOR ERROR: {error}", file=sys.stderr)
        return 1

    print("Repo doctor passed")
    return 0


def validate_configs() -> int:
    return run([sys.executable, "scripts/agent/validate_configs.py"])


def validate_architecture() -> int:
    return run([sys.executable, "scripts/agent/validate_architecture.py"])


def quick_check() -> int:
    return run([sys.executable, "scripts/agent/quick_check.py"])


def full_check() -> int:
    exit_code = quick_check()
    if exit_code != 0:
        return exit_code
    exit_code = run(
        [
            quick_check_python(),
            "-m",
            "pip",
            "install",
            "--no-build-isolation",
            "--no-deps",
            "-e",
            str(FREELANCER_SUITE_ROOT),
        ]
    )
    if exit_code != 0:
        return exit_code
    return run(
        [
            quick_check_python(),
            "-m",
            "pytest",
            "tests/e2e",
            "packages/backend/product-platforms/freelancer-suite/tests",
        ]
    )


def kernel_smoke() -> int:
    print("Kernel smoke placeholder: runtime implementation will be added in MVP-A slices.")
    return run([sys.executable, "-m", "pytest", "tests/e2e", "-q"])


def generate_docs() -> int:
    generated_dir = ROOT / "docs" / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    action_registry = generated_dir / "action-registry.md"
    lines = [
        "# Action Registry",
        "",
        "Generated-doc mirror of MVP-A Wave 1 action definitions.",
        "",
        "All action types are product-neutral and should be runnable through the generic action "
        "runner.",
        "",
        "| Old atom | Platform action type |",
        "|---|---|",
        *[f"| {old_atom} | {action_type} |" for old_atom, action_type in ACTION_REGISTRY_ROWS],
        "",
        "`generate_proposal` is not a platform action type.",
        "",
    ]
    action_registry.write_text("\n".join(lines), encoding="utf-8")
    print("Generated docs refreshed")
    return 0


def dev_up() -> int:
    return run(["docker", "compose", "-f", "infra/compose/docker-compose.yml", "up", "-d"])


def dev_down() -> int:
    return run(["docker", "compose", "-f", "infra/compose/docker-compose.yml", "down"])


def reset_db() -> int:
    print("Reset DB placeholder.")
    return 0


COMMANDS = {
    "doctor": doctor,
    "validate-configs": validate_configs,
    "validate-architecture": validate_architecture,
    "quick-check": quick_check,
    "full-check": full_check,
    "kernel-smoke": kernel_smoke,
    "generate-docs": generate_docs,
    "dev-up": dev_up,
    "dev-down": dev_down,
    "reset-db": reset_db,
}


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AnytoolAI agent and dev commands.")
    parser.add_argument("command", choices=COMMANDS)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    return COMMANDS[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
