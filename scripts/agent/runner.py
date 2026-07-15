#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.error
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[2]
QUICK_CHECK_VENV = ROOT / ".quick-check-venv"
TMP_ROOT = ROOT / ".quick-check-tmp"
COMPOSE_FILE = ROOT / "infra" / "compose" / "docker-compose.yml"
FREELANCER_SUITE_ROOT = ROOT / "packages" / "backend" / "product-platforms" / "freelancer-suite"
REQUIRED_MODULES = ["pytest", "yaml", "pydantic"]
REQUIRED_TOOLS = ["uv"]
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


def source_roots() -> list[Path]:
    return [
        ROOT / "packages" / "backend" / "platform-core" / "src",
        ROOT / "packages" / "backend" / "platform-actions" / "src",
        ROOT / "packages" / "backend" / "platform-sdk" / "src",
        ROOT / "packages" / "backend" / "product-platforms" / "freelancer-suite" / "src",
        ROOT / "apps" / "platform-api" / "src",
        ROOT / "apps" / "platform-worker" / "src",
    ]


def build_pythonpath() -> str:
    paths: list[str] = [str(path) for path in source_roots()]
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
    tmp_dir = TMP_ROOT / "tmp"
    uv_cache_dir = TMP_ROOT / "uv-cache"
    pip_cache_dir = TMP_ROOT / "pip-cache"
    pytest_tmp_dir = TMP_ROOT / "pytest"
    for path in (tmp_dir, uv_cache_dir, pip_cache_dir, pytest_tmp_dir):
        path.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = build_pythonpath()
    env["TMPDIR"] = str(tmp_dir)
    env["TMP"] = str(tmp_dir)
    env["TEMP"] = str(tmp_dir)
    env["UV_CACHE_DIR"] = str(uv_cache_dir)
    env["PIP_CACHE_DIR"] = str(pip_cache_dir)
    env["PYTEST_DEBUG_TEMPROOT"] = str(pytest_tmp_dir)
    return env


def baseline_env() -> dict[str, str]:
    env = runner_env()
    env.pop("PYTHONPATH", None)
    return env


def print_command(command: Sequence[str]) -> None:
    print("+ " + " ".join(command), flush=True)


def uv_executable() -> str:
    candidate = shutil.which("uv")
    return candidate if candidate is not None else "uv"


def uv_install_command(*args: str, python: str) -> list[str]:
    return [uv_executable(), "pip", "install", "--python", python, *args]


def build_system_requirements(project_root: Path) -> list[str]:
    pyproject_path = project_root / "pyproject.toml"
    try:
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"Unable to read {pyproject_path}: {exc}") from exc

    build_system = pyproject.get("build-system")
    if not isinstance(build_system, dict):
        raise RuntimeError(f"{pyproject_path} is missing [build-system].")

    requires = build_system.get("requires")
    if not isinstance(requires, list) or not requires or not all(
        isinstance(item, str) for item in requires
    ):
        raise RuntimeError(
            f"{pyproject_path} is missing a non-empty string-only build-system.requires list."
        )

    return requires


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
            print(
                "CHECK FAILED. Smallest rerun: " + " ".join(command),
                file=sys.stderr,
            )
            return exit_code
    return 0


def probe_tool(tool: str) -> tuple[bool, str]:
    executable = shutil.which(tool)
    if executable is None:
        return False, "not found"
    command = [executable, "version"] if tool == "docker" else [executable, "--version"]
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=runner_env(),
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"unusable ({exc})"
    output = (completed.stdout or completed.stderr).strip().splitlines()
    detail = output[0] if output else f"exit {completed.returncode}"
    return completed.returncode == 0, f"{executable} ({detail})"


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

    for tool in REQUIRED_TOOLS:
        usable, detail = probe_tool(tool)
        print(f"Required tool {tool}: {detail}")
        if not usable:
            errors.append(f"Required tool is unavailable: {tool}")

    for tool in OPTIONAL_TOOLS:
        usable, detail = probe_tool(tool)
        status = "ok" if usable else "warning"
        print(f"Optional tool {tool}: {status} - {detail}")

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


def validate_docs() -> int:
    return run([sys.executable, "scripts/agent/validate_docs.py"])


def quick_check() -> int:
    return run_with_env([sys.executable, "scripts/agent/quick_check.py"], baseline_env())


def frontend_check() -> int:
    return run_sequence(
        [
            ["pnpm", "install", "--frozen-lockfile"],
            ["pnpm", "-r", "typecheck"],
            ["pnpm", "-r", "build"],
        ]
    )


def full_check() -> int:
    exit_code = quick_check()
    if exit_code != 0:
        return exit_code
    exit_code = frontend_check()
    if exit_code != 0:
        return exit_code
    env = baseline_env()
    try:
        build_requirements = build_system_requirements(FREELANCER_SUITE_ROOT)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    exit_code = run_with_env(
        uv_install_command(
            *build_requirements,
            python=quick_check_python(),
        ),
        env,
    )
    if exit_code != 0:
        return exit_code
    exit_code = run_with_env(
        uv_install_command(
            "--no-build-isolation",
            "--no-deps",
            "-e",
            str(FREELANCER_SUITE_ROOT),
            python=quick_check_python(),
        ),
        env,
    )
    if exit_code != 0:
        return exit_code
    return run_with_env(
        [
            quick_check_python(),
            "-m",
            "pytest",
            "packages/backend/product-platforms/freelancer-suite/tests",
        ],
        env,
    )


def collect_context() -> int:
    print(f"Repository: {ROOT}")
    for command in (
        ["git", "status", "--short"],
        ["git", "diff", "--stat"],
        [sys.executable, "--version"],
        [uv_executable(), "--version"],
    ):
        exit_code = run(command)
        if exit_code != 0:
            print(f"Context section unavailable: {' '.join(command)}", file=sys.stderr)
    return 0


def generate_docs(*, check: bool = False) -> int:
    script_dir = str(Path(__file__).resolve().parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from docs_generation import render_documents, write_documents

    generated_dir = ROOT / "docs" / "generated"
    if not check:
        write_documents(generated_dir)
        print("Generated docs refreshed")
        return 0

    with tempfile.TemporaryDirectory(prefix="anytoolai-generated-docs-") as temporary:
        temporary_dir = Path(temporary)
        write_documents(temporary_dir)
        drift: list[str] = []
        for name in sorted(render_documents()):
            tracked = generated_dir / name
            candidate = temporary_dir / name
            if not tracked.exists() or tracked.read_bytes() != candidate.read_bytes():
                drift.append(name)
    if drift:
        for name in drift:
            print(
                f"[DOCGEN001] docs/generated/{name} is stale. "
                "Run: python scripts/agent/runner.py generate-docs",
                file=sys.stderr,
            )
        return 1
    print("Generated documentation is current")
    return 0


class RuntimeIdentity(NamedTuple):
    worktree_hash: str
    compose_project: str
    postgres_port: int
    api_port: int

    @property
    def api_url(self) -> str:
        return f"http://127.0.0.1:{self.api_port}"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://anytoolai:anytoolai@127.0.0.1:{self.postgres_port}/anytoolai"
        )


def normalized_repo_path(path: Path = ROOT) -> str:
    return os.path.normcase(str(path.resolve())).replace("\\", "/")


def runtime_identity(path: Path = ROOT) -> RuntimeIdentity:
    digest = hashlib.sha256(normalized_repo_path(path).encode("utf-8")).hexdigest()[:8]
    offset = int(digest[:4], 16) % 1000
    return RuntimeIdentity(
        worktree_hash=digest,
        compose_project=f"anytoolai-{digest}",
        postgres_port=_port_override("ANYTOOLAI_POSTGRES_PORT", 15432 + offset),
        api_port=_port_override("ANYTOOLAI_API_PORT", 18000 + offset),
    )


def _port_override(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        port = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer port") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"{name} must be between 1 and 65535")
    return port


def port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            candidate.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _compose_env(identity: RuntimeIdentity) -> dict[str, str]:
    env = runner_env()
    env["ANYTOOLAI_POSTGRES_PORT"] = str(identity.postgres_port)
    env["ANYTOOLAI_API_PORT"] = str(identity.api_port)
    return env


def _compose_command(identity: RuntimeIdentity, *args: str) -> list[str]:
    return [
        "docker",
        "compose",
        "--project-name",
        identity.compose_project,
        "-f",
        str(COMPOSE_FILE),
        *args,
    ]


def print_runtime_endpoints(identity: RuntimeIdentity) -> None:
    print(f"Compose project: {identity.compose_project}")
    print(f"API: {identity.api_url}")
    print(f"Database: {identity.database_url}")


def dev_up() -> int:
    try:
        identity = runtime_identity()
    except ValueError as exc:
        print(f"DEV001: {exc}", file=sys.stderr)
        return 2
    occupied = [
        (name, port)
        for name, port in (
            ("API", identity.api_port),
            ("PostgreSQL", identity.postgres_port),
        )
        if not port_available(port)
    ]
    if occupied:
        for name, port in occupied:
            variable = "ANYTOOLAI_API_PORT" if name == "API" else "ANYTOOLAI_POSTGRES_PORT"
            print(
                f"DEV002: {name} port {port} is occupied. Override with {variable} "
                f"or --{name.lower().replace('postgresql', 'postgres')}-port.",
                file=sys.stderr,
            )
        return 1
    print_runtime_endpoints(identity)
    exit_code = run_with_env(
        _compose_command(identity, "up", "-d", "--remove-orphans"),
        _compose_env(identity),
    )
    return dev_ready() if exit_code == 0 else exit_code


def dev_ready() -> int:
    try:
        identity = runtime_identity()
        timeout = float(os.environ.get("ANYTOOLAI_READY_TIMEOUT", "90"))
    except ValueError as exc:
        print(f"DEV001: {exc}", file=sys.stderr)
        return 2
    deadline = time.monotonic() + timeout
    health_url = f"{identity.api_url}/health"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=2) as response:
                if response.status == 200:
                    print_runtime_endpoints(identity)
                    print("Development environment is ready")
                    return 0
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.5)
    print(
        f"DEV003: readiness timed out after {timeout:g}s for {health_url}. "
        "Rerun: python scripts/agent/runner.py dev-status",
        file=sys.stderr,
    )
    return 1


def dev_status() -> int:
    identity = runtime_identity()
    print_runtime_endpoints(identity)
    return run_with_env(
        _compose_command(identity, "ps"),
        _compose_env(identity),
    )


def dev_down() -> int:
    identity = runtime_identity()
    print_runtime_endpoints(identity)
    return run_with_env(
        _compose_command(identity, "down", "--remove-orphans"),
        _compose_env(identity),
    )


COMMANDS = {
    "doctor": doctor,
    "validate-configs": validate_configs,
    "validate-architecture": validate_architecture,
    "validate-docs": validate_docs,
    "quick-check": quick_check,
    "frontend-check": frontend_check,
    "full-check": full_check,
    "collect-context": collect_context,
    "generate-docs": generate_docs,
    "dev-up": dev_up,
    "dev-ready": dev_ready,
    "dev-status": dev_status,
    "dev-down": dev_down,
}


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AnytoolAI agent and dev commands.")
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check generated documents without modifying tracked files.",
    )
    parser.add_argument("--api-port", type=int, help="Override the worktree API host port.")
    parser.add_argument(
        "--postgres-port",
        type=int,
        help="Override the worktree PostgreSQL host port.",
    )
    parser.add_argument(
        "--ready-timeout",
        type=float,
        help="Override readiness timeout in seconds.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.check:
        if args.command != "generate-docs":
            print("--check is only valid with generate-docs", file=sys.stderr)
            return 2
        return generate_docs(check=True)
    runtime_options = (args.api_port, args.postgres_port, args.ready_timeout)
    if any(value is not None for value in runtime_options):
        if not args.command.startswith("dev-"):
            print("runtime port/timeout overrides are only valid with dev-* commands", file=sys.stderr)
            return 2
        if args.api_port is not None:
            os.environ["ANYTOOLAI_API_PORT"] = str(args.api_port)
        if args.postgres_port is not None:
            os.environ["ANYTOOLAI_POSTGRES_PORT"] = str(args.postgres_port)
        if args.ready_timeout is not None:
            os.environ["ANYTOOLAI_READY_TIMEOUT"] = str(args.ready_timeout)
    return COMMANDS[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
