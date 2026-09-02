#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.error
import urllib.request
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
QUICK_CHECK_VENV = ROOT / ".quick-check-venv"
TMP_ROOT = ROOT / ".quick-check-tmp"
PYTEST_BASETEMP_ROOT = TMP_ROOT / "pytest-runs"
COMPOSE_FILE = ROOT / "infra" / "compose" / "docker-compose.yml"
COMPOSE_OVERRIDE_FILE = ROOT / "infra" / "compose" / "docker-compose.override.yml"
COMPOSE_PROD_FILE = ROOT / "infra" / "compose" / "docker-compose.prod.yml"
# Optional, gitignored (see .gitignore's `.env.*` rule) -- a local convenience so credentials
# don't have to be re-exported in every shell. Never auto-loaded for dev; only prod commands
# pass it to `docker compose` via --env-file, and only if it actually exists on disk.
PROD_ENV_FILE = ROOT / "infra" / "compose" / ".env.prod"
PROD_COMPOSE_PROJECT = "anytoolai-prod"
DEV_DEFAULT_POSTGRES_USER = "anytoolai"
DEV_DEFAULT_POSTGRES_PASSWORD = "anytoolai"
DEV_DEFAULT_POSTGRES_DB = "anytoolai"

# Bounds `docker compose ps`/`down` calls, which should never legitimately take this long, so a
# wedged Docker daemon fails fast instead of hanging. Deliberately NOT applied to `up`/`--build`
# calls (dev_up/prod_up) -- those legitimately take minutes on a cold image build, and a short
# timeout there would turn a slow-but-healthy build into a false failure.
COMPOSE_QUERY_TIMEOUT_SECONDS = 60


def resolve_postgres_db() -> str:
    return os.environ.get("ANYTOOLAI_POSTGRES_DB", DEV_DEFAULT_POSTGRES_DB)

FREELANCER_SUITE_ROOT = ROOT / "packages" / "backend" / "product-platforms" / "freelancer-suite"
POSTGRESQL_PYTEST_MARK_EXPRESSION = "postgresql"
POSTGRESQL_TEST_DATABASE_URL_ENV = "ANYTOOLAI_POSTGRES_TEST_DATABASE_URL"
POSTGRESQL_PYTEST_TARGETS = [
    "packages/backend/platform-core/tests",
    "packages/backend/platform-actions/tests",
    "apps/platform-api/tests",
    "apps/platform-worker/tests",
]
REQUIRED_MODULES = ["pytest", "yaml", "pydantic"]
# `node`/`npm`: required, not optional, since round 45 — tests/architecture (part of every
# quick-check run) shells out to scripts/agent/js_scope_resolver.mjs for real JS/TS parsing, and
# self-installs that script's own `typescript` dependency via `npm install` on first use.
REQUIRED_TOOLS = ["uv", "node", "npm"]
OPTIONAL_TOOLS = ["pnpm", "docker"]
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
    for path in (tmp_dir, uv_cache_dir, pip_cache_dir, pytest_tmp_dir, PYTEST_BASETEMP_ROOT):
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


def quick_check_venv_python() -> Path:
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    python_name = "python.exe" if os.name == "nt" else "python"
    return QUICK_CHECK_VENV / scripts_dir / python_name


def quick_check_python() -> str:
    candidate = quick_check_venv_python()
    return str(candidate) if candidate.exists() else sys.executable


# Must stay in sync with quick_check.py's EDITABLE_PROJECTS/DEPENDENCY_FINGERPRINT_INPUTS: this
# is the same duplication-across-standalone-scripts pattern already used for ROOT/baseline_env()
# in both files (neither script imports the other).
QUICK_CHECK_DEPENDENCY_FINGERPRINT_INPUTS = [
    ROOT / "uv.lock",
    ROOT / "packages" / "backend" / "platform-sdk" / "pyproject.toml",
    ROOT / "packages" / "backend" / "platform-core" / "pyproject.toml",
    ROOT / "packages" / "backend" / "platform-actions" / "pyproject.toml",
    ROOT / "apps" / "platform-api" / "pyproject.toml",
    ROOT / "apps" / "platform-worker" / "pyproject.toml",
]


def quick_check_dependency_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in QUICK_CHECK_DEPENDENCY_FINGERPRINT_INPUTS:
        digest.update(path.read_bytes() if path.exists() else b"")
        digest.update(b"\0")
    return digest.hexdigest()


def quick_check_venv_ready(venv_python: Path) -> bool:
    # Marker written by quick_check.py's bootstrap() only after every editable install succeeds,
    # containing a fingerprint of uv.lock + each editable project's pyproject.toml (ANY-390):
    # venv_python.exists() alone can't tell a fully bootstrapped, up-to-date venv apart from one
    # left behind by an interrupted bootstrap, or one that's gone stale because .quick-check-venv
    # is gitignored and survives a pull/branch-switch that changed dependency inputs underneath it.
    marker = venv_python.parent / ".bootstrap-complete"
    if not venv_python.exists() or not marker.exists():
        return False
    try:
        stored_fingerprint = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    return stored_fingerprint == quick_check_dependency_fingerprint()


def run(command: Sequence[str], *, timeout: float | None = None) -> int:
    print_command(command)
    try:
        completed = subprocess.run(
            list(command),
            cwd=ROOT,
            env=runner_env(),
            shell=False,
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        print(f"Command not found: {exc.filename}", file=sys.stderr)
        return 127
    except subprocess.TimeoutExpired:
        print(f"Command timed out after {timeout:g}s: {' '.join(command)}", file=sys.stderr)
        return 124
    return completed.returncode


def run_with_env(command: Sequence[str], env: dict[str, str], *, timeout: float | None = None) -> int:
    print_command(command)
    try:
        completed = subprocess.run(
            list(command),
            cwd=ROOT,
            env=env,
            shell=False,
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        print(f"Command not found: {exc.filename}", file=sys.stderr)
        return 127
    except subprocess.TimeoutExpired:
        print(f"Command timed out after {timeout:g}s: {' '.join(command)}", file=sys.stderr)
        return 124
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


def quick_check(*, bootstrap_only: bool = False) -> int:
    command = [sys.executable, "scripts/agent/quick_check.py"]
    if bootstrap_only:
        command.append("--bootstrap-only")
    return run_with_env(command, baseline_env())


def postgresql_pytest_command() -> list[str]:
    return [
        sys.executable,
        "-m",
        "pytest",
        "-m",
        POSTGRESQL_PYTEST_MARK_EXPRESSION,
        "--basetemp",
        str(PYTEST_BASETEMP_ROOT / f"postgresql-{os.getpid()}"),
        *POSTGRESQL_PYTEST_TARGETS,
        "-q",
    ]


def postgresql_check() -> int:
    if not os.environ.get(POSTGRESQL_TEST_DATABASE_URL_ENV, "").strip():
        print(
            "PGTEST001: postgresql-check requires "
            f"{POSTGRESQL_TEST_DATABASE_URL_ENV} to point to a PostgreSQL maintenance database.",
            file=sys.stderr,
        )
        return 2
    return run(postgresql_pytest_command())


def frontend_check() -> int:
    return run_sequence(
        [
            ["pnpm", "install", "--frozen-lockfile"],
            ["pnpm", "-r", "typecheck"],
            ["pnpm", "-r", "test"],
            ["pnpm", "-r", "--if-present", "generate-api-types:check"],
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


def collect_context(
    *,
    failure_file: Path | None = None,
    log_lines: int = 100,
) -> int:
    script_dir = str(Path(__file__).resolve().parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from collect_context import write_bundle

    try:
        target = write_bundle(failure_file=failure_file, log_lines=log_lines)
    except OSError as exc:
        print(f"DIAG001: unable to write context bundle: {exc}", file=sys.stderr)
        return 1
    print(f"Sanitized context written to {target}")
    return 0


def generate_docs(*, check: bool = False) -> int:
    script_dir = str(Path(__file__).resolve().parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from docs_generation import GENERATED_SOURCES, write_documents

    generated_dir = ROOT / "docs" / "generated"
    if not check:
        write_documents(generated_dir)
        print("Generated docs refreshed")
        return 0

    with tempfile.TemporaryDirectory(prefix="anytoolai-generated-docs-") as temporary:
        temporary_dir = Path(temporary)
        write_documents(temporary_dir)
        drift: list[str] = []
        for name in sorted(GENERATED_SOURCES):
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
        # Intentionally not masked: this is the one documented, copy-pasteable connection
        # string agents/developers are told to use (see docs/agent/worktree-runtime.md).
        # Masking it (tried once) broke that without eliminating the underlying exposure —
        # an operator who exported real prod credentials into this shell already has them
        # in their own environment/history regardless of what this prints.
        # Built by hand with quote(..., safe="") on every component, not via
        # sqlalchemy.engine.URL.create(): URL.create()'s own render_as_string() already
        # percent-encodes username/password internally (confirmed against every RFC 3986
        # sub-delim except a literal space, which it passes through unencoded -- eighteenth
        # code review pass finding, invalid per RFC 3986 and can break stricter external
        # parsers like psql), so quote()-ing username/password ourselves *and* handing them to
        # URL.create() double-encodes (e.g. a literal "%" from our own quote() gets re-escaped
        # to "%25" by URL.create()'s encoder). One explicit quote() pass here, with no second
        # encoding pass downstream, avoids that. URL.create() does NOT encode the database path
        # segment at all (verified: a raw "?" placed there round-trips through
        # render_as_string() unescaped), and make_url() does NOT decode that segment back on
        # parse either -- so an un-encoded reserved character there (#, ?, ...) is misread as a
        # URL delimiter by any later make_url() call, letting ANYTOOLAI_POSTGRES_DB inject
        # query-string connect_args (seventeenth code review pass finding, "?"; sixteenth found
        # "#" the same way). quote()-ing the database segment here closes that gap the same way.
        # make_url() percent-decodes userinfo automatically on parse (username/password need no
        # further help), but not the database path segment -- atoms_proof.py's _build_engine(),
        # the sole real consumer, is told via --database-url-is-percent-encoded to unquote just
        # that segment back after make_url().
        user = os.environ.get("ANYTOOLAI_POSTGRES_USER", DEV_DEFAULT_POSTGRES_USER)
        password = os.environ.get("ANYTOOLAI_POSTGRES_PASSWORD", DEV_DEFAULT_POSTGRES_PASSWORD)
        db = resolve_postgres_db()
        return (
            f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}"
            f"@127.0.0.1:{self.postgres_port}/{quote(db, safe='')}"
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


def _docker_compose_command(
    project_name: str,
    compose_files: Sequence[Path],
    *args: str,
    env_file: Path | None = None,
) -> list[str]:
    command = ["docker", "compose", "--project-name", project_name]
    if env_file is not None:
        command.extend(["--env-file", str(env_file)])
    for compose_file in compose_files:
        command.extend(["-f", str(compose_file)])
    command.extend(args)
    return command


def _compose_command(identity: RuntimeIdentity, *args: str) -> list[str]:
    return _docker_compose_command(
        identity.compose_project, (COMPOSE_FILE, COMPOSE_OVERRIDE_FILE), *args
    )


def print_runtime_endpoints(identity: RuntimeIdentity) -> None:
    print(f"Compose project: {identity.compose_project}")
    print(f"API: {identity.api_url}")
    print(f"Database: {identity.database_url}")


def _check_ports_available(
    error_prefix: str, ports: Sequence[tuple[str, int, str, str | None]]
) -> bool:
    occupied = [
        (name, port, variable, cli_flag)
        for name, port, variable, cli_flag in ports
        if not port_available(port)
    ]
    for name, port, variable, cli_flag in occupied:
        message = f"{error_prefix}: {name} port {port} is occupied. Override with {variable}"
        if cli_flag:
            message += f" or {cli_flag}"
        print(f"{message}.", file=sys.stderr)
    return not occupied


def dev_up() -> int:
    try:
        identity = runtime_identity()
    except ValueError as exc:
        print(f"DEV001: {exc}", file=sys.stderr)
        return 2
    if not _check_ports_available(
        "DEV002",
        [
            ("API", identity.api_port, "ANYTOOLAI_API_PORT", "--api-port"),
            ("PostgreSQL", identity.postgres_port, "ANYTOOLAI_POSTGRES_PORT", "--postgres-port"),
        ],
    ):
        return 1
    print_runtime_endpoints(identity)
    # No timeout: a cold image build can legitimately take minutes.
    exit_code = run_with_env(
        _compose_command(identity, "up", "-d", "--remove-orphans"),
        _compose_env(identity),
    )
    return dev_ready() if exit_code == 0 else exit_code


def _wait_for_http_ok(url: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.5)
    return False


def dev_ready() -> int:
    try:
        identity = runtime_identity()
        timeout = float(os.environ.get("ANYTOOLAI_READY_TIMEOUT", "90"))
    except ValueError as exc:
        print(f"DEV001: {exc}", file=sys.stderr)
        return 2
    health_url = f"{identity.api_url}/health"
    if _wait_for_http_ok(health_url, timeout):
        print_runtime_endpoints(identity)
        print("Development environment is ready")
        return 0
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
        timeout=COMPOSE_QUERY_TIMEOUT_SECONDS,
    )


def dev_down() -> int:
    identity = runtime_identity()
    print_runtime_endpoints(identity)
    return run_with_env(
        _compose_command(identity, "down", "--remove-orphans"),
        _compose_env(identity),
        timeout=COMPOSE_QUERY_TIMEOUT_SECONDS,
    )


def dev_smoke() -> int:
    try:
        identity = runtime_identity()
    except ValueError as exc:
        print(f"DEV001: {exc}", file=sys.stderr)
        return 2
    return run([sys.executable, "scripts/agent/kernel_demo_smoke.py", identity.api_url])


def _run_proof_script(script_path: str, database_url_env: str) -> int:
    """Shared by atoms_proof() and live_canary(): both invoke a sibling scripts/agent/*.py script
    (atoms_proof.py / live_canary.py) with the same identity/DSN-passing contract -- resolve
    runtime_identity(), then pass its database_url through the environment (never argv, since it
    can embed a real ANYTOOLAI_POSTGRES_PASSWORD override that a process-listing/`ps` would
    otherwise expose) alongside --database-url-is-percent-encoded, since RuntimeIdentity.database_url
    always percent-encodes its database-name path segment. One shared implementation instead of
    two hand-copies: --database-url-is-percent-encoded already drifted between them once (missing
    entirely from live_canary()) and was only caught on review, precisely because they were
    written separately instead of sharing this contract.

    Launches the child with .quick-check-venv's python, not sys.executable: the script imports
    anytoolai_platform_core, which pulls in platform-actions' markdown-it-py, a dependency that
    only exists in the managed venv, never in a bare system Python (ANY-390). Unlike
    quick_check_python(), this does not silently fall back to sys.executable when the venv is
    missing, incomplete (an interrupted bootstrap can leave the interpreter in place without every
    editable package installed), or stale (.quick-check-venv is gitignored and survives a pull or
    branch switch that changed uv.lock/dependency inputs underneath it) -- any of those would just
    reproduce the bug on a checkout whose venv doesn't actually match what quick-check would
    install today -- it fails fast instead."""
    venv_python = quick_check_venv_python()
    if not quick_check_venv_ready(venv_python):
        print(
            "ENV001: .quick-check-venv not found, incomplete, or out of date -- run `python "
            "scripts/agent/runner.py quick-check` once to (re)bootstrap the managed environment, "
            "then retry.",
            file=sys.stderr,
        )
        return 2
    try:
        identity = runtime_identity()
    except ValueError as exc:
        print(f"DEV001: {exc}", file=sys.stderr)
        return 2
    env = runner_env()
    env[database_url_env] = identity.database_url
    return run_with_env(
        [
            str(venv_python), script_path, identity.api_url,
            "--database-url-env", database_url_env,
            "--database-url-is-percent-encoded",
        ],
        env,
    )


def atoms_proof() -> int:
    return _run_proof_script("scripts/agent/atoms_proof.py", "ANYTOOLAI_ATOMS_PROOF_DATABASE_URL")


def live_canary() -> int:
    # Fail fast, before touching Docker/DB -- same precedent as postgresql_check(): a clear code
    # is better than a live_canary.py subprocess failing deep inside ProviderGateway/LiteLLM once
    # OPENAI_API_KEY turns out to be unset.
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        print(
            "LIVE000: live-canary requires OPENAI_API_KEY to be set (it costs real money and "
            "calls a real provider -- never part of quick-check/full-check/postgresql-check).",
            file=sys.stderr,
        )
        return 2
    # Same reasoning as OPENAI_API_KEY above: the 14 live scenario_ids are config-flagged
    # internal_only (code review finding), so platform-api rejects a start request for them
    # without a token matching its own ANYTOOLAI_LIVE_CANARY_TOKEN -- every case would otherwise
    # fail LIVE-layer 404s one by one instead of failing clearly up front.
    if not os.environ.get("ANYTOOLAI_LIVE_CANARY_TOKEN", "").strip():
        print(
            "LIVE011: live-canary requires ANYTOOLAI_LIVE_CANARY_TOKEN to be set (the live "
            "scenario_ids are internal_only -- platform-api rejects every case without a "
            "matching token).",
            file=sys.stderr,
        )
        return 2
    return _run_proof_script("scripts/agent/live_canary.py", "ANYTOOLAI_LIVE_CANARY_DATABASE_URL")


CLIENT_HANDOFF_SMOKE_WEB_MIRROR_PORT_ENV = "ANYTOOLAI_CLIENT_HANDOFF_SMOKE_WEB_MIRROR_PORT"
CLIENT_HANDOFF_SMOKE_EVIDENCE_ROOT = ROOT / ".agent" / "client-handoff-smoke"
CLIENT_HANDOFF_SMOKE_REPORT_PATH = (
    ROOT / "tests" / "e2e" / "client-handoff-smoke" / "playwright-report.json"
)


def _client_handoff_smoke_web_mirror_port() -> int:
    return _port_override(CLIENT_HANDOFF_SMOKE_WEB_MIRROR_PORT_ENV, 3000)


def _terminate_process_group(process: subprocess.Popen) -> None:
    """Pairs with start_new_session=True: signals the whole process group, not just `process`'s
    own pid, since some wrappers (pnpm's `exec`) don't forward signals to the child they spawn.
    Called from a `finally` cleanup block, so an uncaught ProcessLookupError here (the group can
    exit on its own between the getpgid() check and a killpg() call) would otherwise replace --
    and mask -- whatever smoke-test result was about to be returned."""
    try:
        pgid = os.getpgid(process.pid)
    except ProcessLookupError:
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            return
        process.wait()


def _write_client_handoff_smoke_evidence(exit_code: int) -> Path:
    """Mirrors atoms_proof.py's write_evidence_report() shape (generated_at/all_passed plus the
    raw detail) -- the raw detail here is Playwright's own JSON reporter output, not a hand-rolled
    case list, since the smoke's actual pass/fail granularity already lives in that report."""
    from collect_context import write_timestamped_json_bundle

    report = None
    if CLIENT_HANDOFF_SMOKE_REPORT_PATH.is_file():
        try:
            report = json.loads(CLIENT_HANDOFF_SMOKE_REPORT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report = None
    payload = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "all_passed": exit_code == 0,
        "playwright_report": report,
    }
    return write_timestamped_json_bundle(CLIENT_HANDOFF_SMOKE_EVIDENCE_ROOT, "evidence", payload)


def client_handoff_smoke() -> int:
    """ANY-224: builds web-mirror and the kernel-demo-ce extension against the running dev-up
    platform-api, serves web-mirror, then runs the Playwright browser-evidence smoke
    (tests/e2e/client-handoff-smoke) that proves the client handoff journey -- source CE scenario
    run -> handoff creation -> web consent -> accept/decline -> backend-created target session --
    end to end in a real Chromium loading the built extension.

    Requires `dev-up` already running first (same precedent as atoms-proof/live-canary: this
    command only resolves runtime_identity() for the API URL, it never starts Docker itself) and
    Playwright's Chromium already installed (`pnpm --filter @anytoolai/client-handoff-smoke exec
    playwright install chromium`). MV3 extensions require non-headless Chromium, so this also
    needs a display -- `xvfb-run` in CI, an existing DISPLAY/WAYLAND_DISPLAY locally.

    web-mirror's next.config.ts rewrites() destination is baked in at `next build` time (Next
    serializes it into .next/routes-manifest.json; `next start` never re-invokes rewrites()), so
    PLATFORM_API_BASE_URL must be set for that build step, not just for the later `next start`.
    """
    try:
        identity = runtime_identity()
    except ValueError as exc:
        print(f"DEV001: {exc}", file=sys.stderr)
        return 2

    web_mirror_port = _client_handoff_smoke_web_mirror_port()
    if not _check_ports_available(
        "CHS001",
        [
            (
                "web-mirror",
                web_mirror_port,
                CLIENT_HANDOFF_SMOKE_WEB_MIRROR_PORT_ENV,
                None,
            )
        ],
    ):
        return 1
    web_mirror_url = f"http://localhost:{web_mirror_port}"

    env = runner_env()
    env["PLATFORM_API_BASE_URL"] = identity.api_url
    extension_env = dict(env)
    extension_env["WXT_PLATFORM_API_BASE_URL"] = identity.api_url
    extension_env["WXT_WEB_CONSENT_BASE_URL"] = web_mirror_url

    # web-mirror's build and the extension's build don't depend on each other -- wxt build's only
    # "dependency" on web-mirror is web_mirror_url, a static string derived from the port above,
    # not web-mirror's actual build output -- so run them concurrently instead of paying the sum of
    # both build times.
    web_mirror_build_command = ["pnpm", "--filter", "@anytoolai/web-mirror", "build"]
    extension_build_command = ["pnpm", "--filter", "@anytoolai/kernel-demo-ce", "exec", "wxt", "build"]
    print_command(web_mirror_build_command)
    print_command(extension_build_command)
    web_mirror_build = subprocess.Popen(web_mirror_build_command, cwd=ROOT, env=env)
    extension_build = subprocess.Popen(extension_build_command, cwd=ROOT, env=extension_env)
    web_mirror_build_exit = web_mirror_build.wait()
    extension_build_exit = extension_build.wait()
    if web_mirror_build_exit != 0:
        return web_mirror_build_exit
    if extension_build_exit != 0:
        return extension_build_exit

    # start_new_session=True so this lands in its own process group -- `pnpm exec next start`
    # spawns `next-server` as a child that does NOT receive a plain terminate() sent to just the
    # pnpm wrapper pid (pnpm doesn't forward signals to its child), which otherwise leaks a live
    # next-server bound to web_mirror_port past this command's exit (found by running this live).
    web_mirror_process = subprocess.Popen(
        ["pnpm", "--filter", "@anytoolai/web-mirror", "exec", "next", "start", "-p", str(web_mirror_port)],
        cwd=ROOT,
        env=env,
        start_new_session=True,
    )
    try:
        if not _wait_for_http_ok(web_mirror_url, 30.0):
            print("CHS002: web-mirror did not become ready in time.", file=sys.stderr)
            return 1

        smoke_env = dict(env)
        smoke_env["WEB_CONSENT_BASE_URL"] = web_mirror_url
        # runner_env()'s workspace-local TMPDIR is wrong for this one subprocess: the spec's
        # mkdtemp(join(tmpdir(), ...)) feeds that path straight into Chromium's
        # launchPersistentContext user-data-dir, and on a long checkout path (e.g. GitHub Actions'
        # /home/runner/work/<repo>/<repo>) the resulting profile-relative singleton-socket path
        # exceeds Linux's ~108-byte AF_UNIX limit -- Chrome then FATALs in
        # process_singleton_posix.cc before the browser ever opens a page. Falling back to the
        # real system temp dir (always short, e.g. /tmp) keeps the profile path short regardless
        # of checkout location.
        for key in ("TMPDIR", "TMP", "TEMP"):
            smoke_env.pop(key, None)
        CLIENT_HANDOFF_SMOKE_REPORT_PATH.unlink(missing_ok=True)
        exit_code = run_with_env(
            ["pnpm", "--filter", "@anytoolai/client-handoff-smoke", "run", "smoke"], smoke_env
        )
        _write_client_handoff_smoke_evidence(exit_code)
        return exit_code
    finally:
        _terminate_process_group(web_mirror_process)


def _prod_compose_command(*args: str) -> list[str]:
    env_file = PROD_ENV_FILE if PROD_ENV_FILE.is_file() else None
    return _docker_compose_command(
        PROD_COMPOSE_PROJECT, (COMPOSE_FILE, COMPOSE_PROD_FILE), *args, env_file=env_file
    )


def _prod_stack_running() -> bool:
    # Bounded so a wedged Docker daemon fails this preflight check quickly instead of
    # hanging prod_up() indefinitely before it ever reaches the normal error path.
    result = subprocess.run(
        _prod_compose_command("ps", "-q"),
        cwd=ROOT,
        env=runner_env(),
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    return bool(result.stdout.strip())


def prod_up() -> int:
    # Deliberately its own variable, not ANYTOOLAI_API_PORT (dev's per-worktree derived
    # port) — a leftover dev override in the operator's shell must not silently redirect
    # which host port prod binds to or preflight-checks. Postgres isn't published in prod
    # at all (see docker-compose.prod.yml), so there's no Postgres port to check here.
    try:
        api_port = _port_override("ANYTOOLAI_PROD_API_PORT", 8000)
    except ValueError as exc:
        print(f"PROD001: {exc}", file=sys.stderr)
        return 2
    try:
        stack_running = _prod_stack_running()
    except FileNotFoundError as exc:
        print(f"Command not found: {exc.filename}", file=sys.stderr)
        return 127
    except subprocess.TimeoutExpired:
        print(
            "PROD003: docker compose ps did not respond within 10s — "
            "is the Docker daemon running and responsive?",
            file=sys.stderr,
        )
        return 1
    # Skip the port preflight when the anytoolai-prod stack is already up: this is an
    # in-place redeploy (`docker compose up -d --build` recreates its own containers,
    # freeing/rebinding their ports itself), not a fresh start racing against something
    # else. Checking raw socket availability here would otherwise always "detect" the
    # stack's own already-running containers as an occupied port and block redeploys.
    if not stack_running and not _check_ports_available(
        "PROD002",
        [("API", api_port, "ANYTOOLAI_PROD_API_PORT", None)],
    ):
        return 1
    # No timeout: `--build` can legitimately take minutes on a cold image build.
    exit_code = run_with_env(
        _prod_compose_command("up", "-d", "--build", "--remove-orphans"),
        runner_env(),
    )
    return prod_ready() if exit_code == 0 else exit_code


def prod_ready() -> int:
    try:
        api_port = _port_override("ANYTOOLAI_PROD_API_PORT", 8000)
        timeout = float(os.environ.get("ANYTOOLAI_READY_TIMEOUT", "90"))
    except ValueError as exc:
        print(f"PROD001: {exc}", file=sys.stderr)
        return 2
    health_url = f"http://127.0.0.1:{api_port}/health"
    if _wait_for_http_ok(health_url, timeout):
        print(f"API: http://127.0.0.1:{api_port}")
        print("Production environment is ready")
        return 0
    print(
        f"PROD004: readiness timed out after {timeout:g}s for {health_url}. "
        "Rerun: python scripts/agent/runner.py prod-status",
        file=sys.stderr,
    )
    return 1


def prod_status() -> int:
    return run_with_env(
        _prod_compose_command("ps"), runner_env(), timeout=COMPOSE_QUERY_TIMEOUT_SECONDS
    )


def prod_down() -> int:
    return run_with_env(
        _prod_compose_command("down", "--remove-orphans"),
        runner_env(),
        timeout=COMPOSE_QUERY_TIMEOUT_SECONDS,
    )


def prod_smoke() -> int:
    try:
        api_port = _port_override("ANYTOOLAI_PROD_API_PORT", 8000)
    except ValueError as exc:
        print(f"PROD001: {exc}", file=sys.stderr)
        return 2
    api_url = f"http://127.0.0.1:{api_port}"
    return run([sys.executable, "scripts/agent/kernel_demo_smoke.py", api_url])


COMMANDS = {
    "doctor": doctor,
    "validate-configs": validate_configs,
    "validate-architecture": validate_architecture,
    "validate-docs": validate_docs,
    "quick-check": quick_check,
    "postgresql-check": postgresql_check,
    "frontend-check": frontend_check,
    "full-check": full_check,
    "collect-context": collect_context,
    "generate-docs": generate_docs,
    "dev-up": dev_up,
    "dev-ready": dev_ready,
    "dev-status": dev_status,
    "dev-down": dev_down,
    "dev-smoke": dev_smoke,
    "atoms-proof": atoms_proof,
    "live-canary": live_canary,
    "client-handoff-smoke": client_handoff_smoke,
    "prod-up": prod_up,
    "prod-ready": prod_ready,
    "prod-status": prod_status,
    "prod-down": prod_down,
    "prod-smoke": prod_smoke,
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
    parser.add_argument(
        "--failure-file",
        type=Path,
        help="Optional command-output file to sanitize into collect-context.",
    )
    parser.add_argument(
        "--log-lines",
        type=int,
        default=100,
        help="Recent API/worker log lines to collect (1-1000).",
    )
    parser.add_argument(
        "--bootstrap-only",
        action="store_true",
        help="With quick-check: only bootstrap .quick-check-venv, skip validate/pytest.",
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
    if args.failure_file is not None or args.log_lines != 100:
        if args.command != "collect-context":
            print("--failure-file and --log-lines are only valid with collect-context", file=sys.stderr)
            return 2
        return collect_context(failure_file=args.failure_file, log_lines=args.log_lines)
    if args.bootstrap_only:
        if args.command != "quick-check":
            print("--bootstrap-only is only valid with quick-check", file=sys.stderr)
            return 2
        return quick_check(bootstrap_only=True)
    return COMMANDS[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
