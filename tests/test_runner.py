from __future__ import annotations

import importlib.util
import sys
import urllib.parse
from pathlib import Path

import pytest
import yaml

from tests.test_atoms_proof import load_atoms_proof_module


def load_runner_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "agent" / "runner.py"
    spec = importlib.util.spec_from_file_location("runner_module", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_full_check_uses_uv_for_freelancer_suite_install(monkeypatch) -> None:
    runner = load_runner_module()
    quick_check_python = "/tmp/.quick-check-venv/bin/python"
    commands: list[tuple[list[str], dict[str, str] | None]] = []

    monkeypatch.setattr(runner, "quick_check", lambda: 0)
    monkeypatch.setattr(runner, "frontend_check", lambda: 0)
    monkeypatch.setattr(runner, "quick_check_python", lambda: quick_check_python)
    monkeypatch.setattr(
        runner,
        "build_system_requirements",
        lambda project_root: ["setuptools>=68", "wheel"],
    )
    monkeypatch.setattr(runner.shutil, "which", lambda name: "/usr/local/bin/uv" if name == "uv" else None)
    monkeypatch.setattr(
        runner,
        "baseline_env",
        lambda: {
            "TMPDIR": "/tmp/quick-check",
            "TMP": "/tmp/quick-check",
            "TEMP": "/tmp/quick-check",
        },
    )
    monkeypatch.setattr(
        runner,
        "run_with_env",
        lambda command, env: commands.append((list(command), dict(env))) or 0,
    )

    exit_code = runner.full_check()

    assert exit_code == 0
    assert commands[0][0] == [
        "/usr/local/bin/uv",
        "pip",
        "install",
        "--python",
        quick_check_python,
        "setuptools>=68",
        "wheel",
    ]
    assert "PYTHONPATH" not in commands[0][1]
    assert commands[1][0] == [
        "/usr/local/bin/uv",
        "pip",
        "install",
        "--python",
        quick_check_python,
        "--no-build-isolation",
        "--no-deps",
        "-e",
        str(runner.FREELANCER_SUITE_ROOT),
    ]
    assert "PYTHONPATH" not in commands[1][1]
    assert commands[2][0] == [
        quick_check_python,
        "-m",
        "pytest",
        "packages/backend/product-platforms/freelancer-suite/tests",
    ]
    assert "PYTHONPATH" not in commands[2][1]


def test_build_system_requirements_reads_declared_build_dependencies(tmp_path) -> None:
    runner = load_runner_module()
    project_root = tmp_path / "freelancer-suite"
    project_root.mkdir()
    (project_root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[build-system]",
                'requires = ["setuptools>=68", "wheel"]',
                'build-backend = "setuptools.build_meta"',
            ]
        ),
        encoding="utf-8",
    )

    requirements = runner.build_system_requirements(project_root)

    assert requirements == ["setuptools>=68", "wheel"]


def test_runner_env_uses_workspace_owned_temp_and_cache_dirs(monkeypatch, tmp_path) -> None:
    runner = load_runner_module()
    repo_root = tmp_path / "repo"
    tmp_root = repo_root / ".quick-check-tmp"

    monkeypatch.setattr(runner, "ROOT", repo_root)
    monkeypatch.setattr(runner, "TMP_ROOT", tmp_root)
    monkeypatch.setenv("PYTHONPATH", "/existing/path")

    env = runner.runner_env()

    assert env["TMPDIR"] == str(tmp_root / "tmp")
    assert env["TMP"] == str(tmp_root / "tmp")
    assert env["TEMP"] == str(tmp_root / "tmp")
    assert env["UV_CACHE_DIR"] == str(tmp_root / "uv-cache")
    assert env["PIP_CACHE_DIR"] == str(tmp_root / "pip-cache")
    assert env["PYTEST_DEBUG_TEMPROOT"] == str(tmp_root / "pytest")
    assert str(repo_root / "packages" / "backend" / "platform-core" / "src") in env["PYTHONPATH"]
    assert "/existing/path" in env["PYTHONPATH"]


def test_doctor_requires_uv(monkeypatch) -> None:
    runner = load_runner_module()

    monkeypatch.setattr(runner.sys, "version_info", (3, 12, 1))
    monkeypatch.setattr(runner.importlib.util, "find_spec", lambda module: object())
    monkeypatch.setattr(
        runner.shutil,
        "which",
        lambda name: None if name == "uv" else f"/usr/local/bin/{name}",
    )

    exit_code = runner.doctor()

    assert exit_code == 1


def test_doctor_optional_tools_excludes_just(monkeypatch, capsys) -> None:
    runner = load_runner_module()

    assert runner.OPTIONAL_TOOLS == ["node", "pnpm", "docker"]

    probed: list[str] = []

    def fake_probe_tool(name: str) -> tuple[bool, str]:
        probed.append(name)
        return True, f"/usr/local/bin/{name}"

    monkeypatch.setattr(runner.sys, "version_info", (3, 12, 1))
    monkeypatch.setattr(runner.importlib.util, "find_spec", lambda module: object())
    monkeypatch.setattr(runner, "probe_tool", fake_probe_tool)

    exit_code = runner.doctor()

    assert exit_code == 0
    assert "just" not in probed
    assert probed == ["uv", "node", "pnpm", "docker"]

    output = capsys.readouterr().out
    assert "Optional tool node: ok" in output
    assert "Optional tool pnpm: ok" in output
    assert "Optional tool docker: ok" in output
    assert "just" not in output


def test_frontend_check_uses_frozen_install_and_real_checks(monkeypatch) -> None:
    runner = load_runner_module()
    commands: list[list[str]] = []
    monkeypatch.setattr(
        runner,
        "run",
        lambda command: commands.append(list(command)) or 0,
    )

    assert runner.frontend_check() == 0
    assert commands == [
        ["pnpm", "install", "--frozen-lockfile"],
        ["pnpm", "-r", "typecheck"],
        ["pnpm", "-r", "test"],
        ["pnpm", "-r", "--if-present", "generate-api-types:check"],
        ["pnpm", "-r", "build"],
    ]


def test_quick_check_strips_pythonpath_from_subprocess_env(monkeypatch) -> None:
    runner = load_runner_module()
    recorded: dict[str, str] = {}

    monkeypatch.setenv("PYTHONPATH", "/some/path")
    monkeypatch.setattr(
        runner,
        "run_with_env",
        lambda command, env: recorded.update(env) or 0,
    )

    exit_code = runner.quick_check()

    assert exit_code == 0
    assert "PYTHONPATH" not in recorded


def test_quick_check_bootstrap_only_appends_flag_to_subprocess_command(monkeypatch) -> None:
    runner = load_runner_module()
    commands: list[list[str]] = []
    monkeypatch.setattr(
        runner, "run_with_env", lambda command, env: commands.append(list(command)) or 0
    )

    assert runner.quick_check(bootstrap_only=True) == 0

    assert commands == [[runner.sys.executable, "scripts/agent/quick_check.py", "--bootstrap-only"]]


def test_main_forwards_bootstrap_only_to_quick_check(monkeypatch) -> None:
    """ANY-390: `runner.py quick-check --bootstrap-only` must work through the canonical
    `python scripts/agent/runner.py <command>` interface (AGENTS.md) -- live-canary.yml relies on
    this, not on calling quick_check.py directly."""
    runner = load_runner_module()
    calls: list[bool] = []
    monkeypatch.setattr(
        runner, "quick_check", lambda *, bootstrap_only=False: calls.append(bootstrap_only) or 0
    )

    assert runner.main(["quick-check", "--bootstrap-only"]) == 0

    assert calls == [True]


def test_main_rejects_bootstrap_only_for_other_commands(monkeypatch, capsys) -> None:
    runner = load_runner_module()
    monkeypatch.setattr(
        runner, "doctor", lambda: pytest.fail("doctor must not run for a rejected flag combination")
    )

    assert runner.main(["doctor", "--bootstrap-only"]) == 2

    assert "--bootstrap-only is only valid with quick-check" in capsys.readouterr().err


def test_postgresql_check_uses_marker_driven_backend_roots(monkeypatch) -> None:
    runner = load_runner_module()
    commands: list[list[str]] = []
    tmp_root = Path("/tmp/repo/.quick-check-tmp")
    monkeypatch.setenv(
        runner.POSTGRESQL_TEST_DATABASE_URL_ENV,
        "postgresql+psycopg://anytoolai:anytoolai@127.0.0.1:5432/postgres",
    )
    monkeypatch.setattr(runner.sys, "executable", "/tmp/repo/.venv/bin/python")
    monkeypatch.setattr(runner.os, "getpid", lambda: 1234)
    monkeypatch.setattr(runner, "TMP_ROOT", tmp_root)
    monkeypatch.setattr(runner, "PYTEST_BASETEMP_ROOT", tmp_root / "pytest-runs")
    monkeypatch.setattr(
        runner,
        "run",
        lambda command: commands.append(list(command)) or 0,
    )

    assert runner.postgresql_check() == 0
    assert commands == [
        [
            "/tmp/repo/.venv/bin/python",
            "-m",
            "pytest",
            "-m",
            "postgresql",
            "--basetemp",
            str(tmp_root / "pytest-runs" / "postgresql-1234"),
            "packages/backend/platform-core/tests",
            "packages/backend/platform-actions/tests",
            "apps/platform-api/tests",
            "apps/platform-worker/tests",
            "-q",
        ]
    ]


def test_postgresql_check_fails_without_maintenance_database_url(monkeypatch, capsys) -> None:
    runner = load_runner_module()
    monkeypatch.delenv(runner.POSTGRESQL_TEST_DATABASE_URL_ENV, raising=False)
    monkeypatch.setattr(
        runner,
        "run",
        lambda command: pytest.fail(f"pytest must not run without the database URL: {command}"),
    )

    assert runner.postgresql_check() == 2
    assert runner.POSTGRESQL_TEST_DATABASE_URL_ENV in capsys.readouterr().err


def test_required_backend_workflow_runs_canonical_postgresql_check() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load(
        (repo_root / ".github" / "workflows" / "backend.yml").read_text(encoding="utf-8")
    )
    triggers = workflow.get("on", workflow.get(True))
    assert "pull_request" in triggers

    job = workflow["jobs"]["postgresql-quota-concurrency"]
    assert job.get("continue-on-error") is not True
    steps_by_name = {step.get("name"): step for step in job["steps"]}
    postgresql_step = steps_by_name["Run all PostgreSQL production-semantics tests"]
    assert postgresql_step["run"] == (
        "uv run python scripts/agent/runner.py postgresql-check"
    )
    assert postgresql_step["env"]["ANYTOOLAI_POSTGRES_TEST_DATABASE_URL"] == (
        "postgresql+psycopg://anytoolai:anytoolai@127.0.0.1:5432/postgres"
    )


def _compose_stack_check_action() -> dict:
    repo_root = Path(__file__).resolve().parents[1]
    return yaml.safe_load(
        (repo_root / ".github" / "actions" / "compose-stack-check" / "action.yml").read_text(
            encoding="utf-8"
        )
    )


def test_compose_stack_check_action_scopes_secrets_to_exactly_two_steps() -> None:
    """ANY-391 code review round 2: the boot/run/log-dump/teardown/upload sequence used to be
    duplicated verbatim across compose-smoke-dev, live-canary, and atoms-proof -- extracted into
    this composite action. The original `code-review` finding (secrets scoped to exactly the
    dev-up and check-command steps, not job-level, not every other step) now lives here instead of
    in live-canary.yml directly, so it must still hold at the action level."""
    action = _compose_stack_check_action()
    assert action["runs"]["using"] == "composite"
    steps = action["runs"]["steps"]

    secret_needing_runs = {
        "uv run python scripts/agent/runner.py dev-up",
        "uv run python scripts/agent/runner.py ${{ inputs.check-command }}",
    }
    for step in steps:
        step_env = step.get("env", {})
        if step.get("run") in secret_needing_runs:
            assert step_env.get("OPENAI_API_KEY") == "${{ inputs.openai-api-key }}", step
            assert (
                step_env.get("ANYTOOLAI_LIVE_CANARY_TOKEN")
                == "${{ inputs.live-canary-token }}"
            ), step
        else:
            assert "OPENAI_API_KEY" not in step_env, step
            assert "ANYTOOLAI_LIVE_CANARY_TOKEN" not in step_env, step


def test_compose_stack_check_action_shape() -> None:
    """Structural contract: bootstrap is conditional on the input, teardown always runs, the
    evidence upload is conditional and always runs when enabled, and failure log-dump only runs on
    failure. A drift in any of these silently breaks every one of the three call sites."""
    action = _compose_stack_check_action()
    steps = action["runs"]["steps"]
    steps_by_run = {step.get("run"): step for step in steps if step.get("run")}

    bootstrap_step = steps_by_run["uv run python scripts/agent/runner.py quick-check --bootstrap-only"]
    assert bootstrap_step["if"] == "inputs.bootstrap-quick-check == 'true'"

    dump_step = next(s for s in steps if s.get("name") == "Dump Docker Compose logs on failure")
    assert dump_step["if"] == "failure()"

    teardown_step = steps_by_run["uv run python scripts/agent/runner.py dev-down"]
    assert teardown_step["name"] == "Tear down dev stack"
    assert teardown_step["if"] == "always()"

    upload_step = next(s for s in steps if s.get("name") == "Upload evidence report")
    assert upload_step["if"] == "always() && inputs.upload-evidence == 'true'"
    assert upload_step["with"]["name"] == "${{ inputs.evidence-artifact-name }}"
    assert upload_step["with"]["path"] == "${{ inputs.evidence-artifact-path }}"
    assert upload_step["with"]["if-no-files-found"] == "ignore"

    assert action["inputs"]["bootstrap-quick-check"]["default"] == "false"
    assert action["inputs"]["upload-evidence"]["default"] == "false"
    assert action["inputs"]["openai-api-key"]["default"] == ""
    assert action["inputs"]["live-canary-token"]["default"] == ""


def test_live_canary_workflow_delegates_to_compose_stack_check_with_secrets() -> None:
    """`code-review` finding (round 1, preserved through the round-2 composite-action extraction):
    OPENAI_API_KEY/ANYTOOLAI_LIVE_CANARY_TOKEN must not sit at job level (every step would inherit
    them for no reason) and must reach the composite action so its dev-up/check-command steps get
    them -- runner.py's live-canary command reads both directly from its own process env for its
    LIVE000/LIVE011 fail-fast checks, and docker-compose.yml's worker/platform-api services
    interpolate them at container-creation time during dev-up."""
    repo_root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load(
        (repo_root / ".github" / "workflows" / "live-canary.yml").read_text(encoding="utf-8")
    )

    job = workflow["jobs"]["live-canary"]
    assert "OPENAI_API_KEY" not in job.get("env", {})
    assert "ANYTOOLAI_LIVE_CANARY_TOKEN" not in job.get("env", {})
    assert job.get("timeout-minutes") == 30

    # A local action reference (./.github/actions/...) can only be resolved after the repo is
    # checked out, so a job-level checkout step must come first, before the composite-action call.
    assert len(job["steps"]) == 2
    checkout_step, step = job["steps"]
    assert checkout_step["uses"].startswith("actions/checkout@")
    assert step["uses"] == "./.github/actions/compose-stack-check"
    assert step["with"]["bootstrap-quick-check"] == "true"
    assert step["with"]["check-command"] == "live-canary"
    assert step["with"]["openai-api-key"] == "${{ secrets.OPENAI_API_KEY }}"
    assert step["with"]["live-canary-token"] == "${{ secrets.ANYTOOLAI_LIVE_CANARY_TOKEN }}"
    assert step["with"]["upload-evidence"] == "true"
    assert step["with"]["evidence-artifact-path"] == ".agent/live-canary/"


def test_required_backend_workflow_runs_atoms_proof() -> None:
    """ANY-391: atoms-proof must run in CI on every PR/push to main. Without this test, the
    `atoms-proof` job could silently disappear from backend.yml, lose its required managed-`uv`
    bootstrap, or lose its always()-teardown (inherited from the composite action, but the job
    must still wire it up with the right inputs), and nothing else in the suite would catch it."""
    repo_root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load(
        (repo_root / ".github" / "workflows" / "backend.yml").read_text(encoding="utf-8")
    )
    triggers = workflow.get("on", workflow.get(True))
    assert "pull_request" in triggers
    assert "main" in triggers["push"]["branches"]

    job = workflow["jobs"]["atoms-proof"]
    assert job.get("continue-on-error") is not True
    assert job.get("timeout-minutes") == 30

    # A local action reference (./.github/actions/...) can only be resolved after the repo is
    # checked out, so a job-level checkout step must come first, before the composite-action call.
    assert len(job["steps"]) == 2
    checkout_step, step = job["steps"]
    assert checkout_step["uses"].startswith("actions/checkout@")
    assert step["uses"] == "./.github/actions/compose-stack-check"
    assert step["with"]["bootstrap-quick-check"] == "true"
    assert step["with"]["check-command"] == "atoms-proof"
    assert step["with"]["upload-evidence"] == "true"
    assert step["with"]["evidence-artifact-name"] == "atoms-proof-evidence"
    assert step["with"]["evidence-artifact-path"] == ".agent/atoms-proof/"


def test_resolve_postgres_db_falls_back_to_dev_default(monkeypatch) -> None:
    runner = load_runner_module()
    monkeypatch.delenv("ANYTOOLAI_POSTGRES_DB", raising=False)

    assert runner.resolve_postgres_db() == "anytoolai"

    monkeypatch.setenv("ANYTOOLAI_POSTGRES_DB", "myproject")

    assert runner.resolve_postgres_db() == "myproject"


def test_runtime_identity_is_stable_and_worktree_specific(monkeypatch, tmp_path) -> None:
    runner = load_runner_module()
    monkeypatch.delenv("ANYTOOLAI_API_PORT", raising=False)
    monkeypatch.delenv("ANYTOOLAI_POSTGRES_PORT", raising=False)

    first = runner.runtime_identity(tmp_path / "worktree-a")
    repeated = runner.runtime_identity(tmp_path / "worktree-a")
    second = runner.runtime_identity(tmp_path / "worktree-b")

    assert first == repeated
    assert first.compose_project.startswith("anytoolai-")
    assert first.compose_project != second.compose_project
    assert (first.api_port, first.postgres_port) != (second.api_port, second.postgres_port)


def test_runtime_identity_supports_explicit_port_overrides(monkeypatch, tmp_path) -> None:
    runner = load_runner_module()
    monkeypatch.setenv("ANYTOOLAI_API_PORT", "18123")
    monkeypatch.setenv("ANYTOOLAI_POSTGRES_PORT", "15555")

    identity = runner.runtime_identity(tmp_path)

    assert identity.api_port == 18123
    assert identity.postgres_port == 15555


def test_check_ports_available_mentions_cli_flag_when_given(monkeypatch, capsys) -> None:
    runner = load_runner_module()
    monkeypatch.setattr(runner, "port_available", lambda port: False)

    result = runner._check_ports_available(
        "DEV002", [("API", 18123, "ANYTOOLAI_API_PORT", "--api-port")]
    )

    stderr = capsys.readouterr().err
    assert result is False
    assert "DEV002: API port 18123 is occupied." in stderr
    assert "ANYTOOLAI_API_PORT" in stderr
    assert "--api-port" in stderr


def test_check_ports_available_omits_cli_flag_when_none(monkeypatch, capsys) -> None:
    runner = load_runner_module()
    monkeypatch.setattr(runner, "port_available", lambda port: False)

    result = runner._check_ports_available(
        "PROD002", [("PostgreSQL", 5432, "ANYTOOLAI_POSTGRES_PORT", None)]
    )

    assert result is False
    stderr = capsys.readouterr().err
    assert "PROD002: PostgreSQL port 5432 is occupied. Override with ANYTOOLAI_POSTGRES_PORT." == stderr.strip()
    assert "--postgres-port" not in stderr


def test_check_ports_available_uses_the_variable_name_given_by_the_caller(
    monkeypatch, capsys
) -> None:
    runner = load_runner_module()
    monkeypatch.setattr(runner, "port_available", lambda port: False)

    runner._check_ports_available(
        "PROD002", [("API", 8000, "ANYTOOLAI_PROD_API_PORT", None)]
    )

    stderr = capsys.readouterr().err
    assert "Override with ANYTOOLAI_PROD_API_PORT." in stderr
    assert "ANYTOOLAI_API_PORT." not in stderr


def test_check_ports_available_uses_the_cli_flag_given_by_the_caller(
    monkeypatch, capsys
) -> None:
    runner = load_runner_module()
    monkeypatch.setattr(runner, "port_available", lambda port: False)

    runner._check_ports_available(
        "DEV002", [("Redis", 6379, "ANYTOOLAI_REDIS_PORT", "--redis-port")]
    )

    stderr = capsys.readouterr().err
    assert "--redis-port" in stderr


def test_check_ports_available_returns_true_when_all_free(monkeypatch) -> None:
    runner = load_runner_module()
    monkeypatch.setattr(runner, "port_available", lambda port: True)

    assert runner._check_ports_available(
        "DEV002",
        [
            ("API", 18123, "ANYTOOLAI_API_PORT", "--api-port"),
            ("PostgreSQL", 15555, "ANYTOOLAI_POSTGRES_PORT", "--postgres-port"),
        ],
    ) is True


def test_dev_up_fails_before_compose_when_port_is_occupied(monkeypatch) -> None:
    runner = load_runner_module()
    identity = runner.RuntimeIdentity("12345678", "anytoolai-12345678", 15555, 18123)
    monkeypatch.setattr(runner, "runtime_identity", lambda: identity)
    monkeypatch.setattr(runner, "port_available", lambda port: port != identity.api_port)
    monkeypatch.setattr(
        runner,
        "run_with_env",
        lambda command, env: (_ for _ in ()).throw(AssertionError("compose must not run")),
    )

    assert runner.dev_up() == 1


def test_dev_ready_waits_for_health(monkeypatch) -> None:
    runner = load_runner_module()
    identity = runner.RuntimeIdentity("12345678", "anytoolai-12345678", 15555, 18123)

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(runner, "runtime_identity", lambda: identity)
    monkeypatch.setattr(runner.urllib.request, "urlopen", lambda url, timeout: Response())

    assert runner.dev_ready() == 0


class _FakeProcess:
    def __init__(self, pid=4321, wait_effects=None):
        self.pid = pid
        self._wait_effects = list(wait_effects or [])
        self.wait_calls: list[float | None] = []

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        effect = self._wait_effects.pop(0) if self._wait_effects else None
        if isinstance(effect, Exception):
            raise effect
        return effect


# _terminate_process_group() is POSIX-only (os.getpgid()/os.killpg() don't exist on Windows at
# all, matching client_handoff_smoke()'s own Popen(start_new_session=True) and the
# client-handoff-smoke CI job itself, which only runs on ubuntu-latest) -- monkeypatch.setattr()
# on a nonexistent Windows os attribute fails with AttributeError before the test body even runs.
_posix_only = pytest.mark.skipif(
    sys.platform == "win32", reason="_terminate_process_group() uses POSIX-only os.getpgid()/os.killpg()"
)


@_posix_only
def test_terminate_process_group_ignores_a_group_that_exits_between_getpgid_and_sigterm(
    monkeypatch,
) -> None:
    # Race: the process group can exit on its own right after getpgid() succeeds but before
    # killpg() runs. This is called from a `finally` cleanup block, so an uncaught
    # ProcessLookupError here would replace -- and mask -- whatever result was about to be
    # returned, rather than just being a harmless no-op cleanup.
    runner = load_runner_module()
    process = _FakeProcess()
    monkeypatch.setattr(runner.os, "getpgid", lambda pid: 999)

    def _killpg(pgid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(runner.os, "killpg", _killpg)

    runner._terminate_process_group(process)  # must not raise

    assert process.wait_calls == []


@_posix_only
def test_terminate_process_group_escalates_to_sigkill_and_reaps_it(monkeypatch) -> None:
    runner = load_runner_module()
    process = _FakeProcess(wait_effects=[runner.subprocess.TimeoutExpired(cmd="x", timeout=10), None])
    killpg_calls: list[tuple[int, int]] = []
    monkeypatch.setattr(runner.os, "getpgid", lambda pid: 999)
    monkeypatch.setattr(runner.os, "killpg", lambda pgid, sig: killpg_calls.append((pgid, sig)))

    runner._terminate_process_group(process)

    assert killpg_calls == [(999, runner.signal.SIGTERM), (999, runner.signal.SIGKILL)]
    # Reaped after SIGKILL, not just after the first (timed-out) wait.
    assert process.wait_calls == [10, None]


@_posix_only
def test_terminate_process_group_ignores_a_group_that_exits_between_timeout_and_sigkill(
    monkeypatch,
) -> None:
    runner = load_runner_module()
    process = _FakeProcess(wait_effects=[runner.subprocess.TimeoutExpired(cmd="x", timeout=10)])
    monkeypatch.setattr(runner.os, "getpgid", lambda pid: 999)

    def _killpg(pgid, sig):
        if sig == runner.signal.SIGKILL:
            raise ProcessLookupError()

    monkeypatch.setattr(runner.os, "killpg", _killpg)

    runner._terminate_process_group(process)  # must not raise


def test_dev_status_and_down_are_scoped_to_worktree_project(monkeypatch) -> None:
    runner = load_runner_module()
    identity = runner.RuntimeIdentity("12345678", "anytoolai-12345678", 15555, 18123)
    commands: list[list[str]] = []
    timeouts: list[float | None] = []
    monkeypatch.setattr(runner, "runtime_identity", lambda: identity)
    monkeypatch.setattr(
        runner,
        "run_with_env",
        lambda command, env, timeout=None: (
            commands.append(list(command)) or timeouts.append(timeout) or 0
        ),
    )

    assert runner.dev_status() == 0
    assert runner.dev_down() == 0
    assert all(identity.compose_project in command for command in commands)
    assert commands[0][-1] == "ps"
    assert commands[1][-2:] == ["down", "--remove-orphans"]
    assert timeouts == [runner.COMPOSE_QUERY_TIMEOUT_SECONDS, runner.COMPOSE_QUERY_TIMEOUT_SECONDS]


def test_compose_command_passes_base_and_override_files_explicitly(monkeypatch) -> None:
    runner = load_runner_module()
    identity = runner.RuntimeIdentity("12345678", "anytoolai-12345678", 15555, 18123)

    command = runner._compose_command(identity, "ps")

    assert command == [
        "docker",
        "compose",
        "--project-name",
        "anytoolai-12345678",
        "-f",
        str(runner.COMPOSE_FILE),
        "-f",
        str(runner.COMPOSE_OVERRIDE_FILE),
        "ps",
    ]


def test_database_url_is_a_usable_connection_string(monkeypatch) -> None:
    runner = load_runner_module()
    identity = runner.RuntimeIdentity("12345678", "anytoolai-12345678", 15555, 18123)
    monkeypatch.setenv("ANYTOOLAI_POSTGRES_USER", "devuser")
    monkeypatch.setenv("ANYTOOLAI_POSTGRES_PASSWORD", "devpassword")
    monkeypatch.setenv("ANYTOOLAI_POSTGRES_DB", "devdb")

    url = identity.database_url

    assert url == "postgresql://devuser:devpassword@127.0.0.1:15555/devdb"


def test_database_url_falls_back_to_dev_defaults(monkeypatch) -> None:
    runner = load_runner_module()
    identity = runner.RuntimeIdentity("12345678", "anytoolai-12345678", 15555, 18123)
    monkeypatch.delenv("ANYTOOLAI_POSTGRES_USER", raising=False)
    monkeypatch.delenv("ANYTOOLAI_POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("ANYTOOLAI_POSTGRES_DB", raising=False)

    assert identity.database_url == "postgresql://anytoolai:anytoolai@127.0.0.1:15555/anytoolai"


def test_database_url_percent_encodes_reserved_characters_in_credentials(monkeypatch) -> None:
    """Team-lead review finding: a password containing a reserved URL character (@, :, /, %, #)
    must not silently parse into the wrong host/user -- see storage/db.py's
    build_postgres_url_from_env for the same fix applied to the app's own internal DSN."""
    runner = load_runner_module()
    identity = runner.RuntimeIdentity("12345678", "anytoolai-12345678", 15555, 18123)
    monkeypatch.setenv("ANYTOOLAI_POSTGRES_USER", "devuser")
    monkeypatch.setenv("ANYTOOLAI_POSTGRES_PASSWORD", "p@ss:w/rd%20#1")
    monkeypatch.setenv("ANYTOOLAI_POSTGRES_DB", "devdb")

    url = identity.database_url

    # urlsplit() doesn't unquote netloc components -- confirm the raw URL parses into the right
    # host/user/db (proving the reserved chars didn't corrupt netloc parsing), then unquote the
    # password back to its original value to confirm nothing was lost or mangled.
    parsed = urllib.parse.urlsplit(url)
    assert parsed.hostname == "127.0.0.1"
    assert parsed.port == 15555
    assert parsed.username == "devuser"
    assert urllib.parse.unquote(parsed.password) == "p@ss:w/rd%20#1"
    assert parsed.path == "/devdb"


def test_database_url_survives_the_real_sqlalchemy_consumer_path_for_reserved_db_name_chars(
    monkeypatch,
) -> None:
    """Seventeenth code review pass finding: an un-encoded reserved character in the db name
    (e.g. "?") is parsed by sqlalchemy's make_url() as the start of a query string, not part of
    the path -- letting ANYTOOLAI_POSTGRES_DB inject arbitrary extra psycopg connect_args (not
    just truncate the name, as the sixteenth round's "#" case did). The fix spans both files:
    RuntimeIdentity.database_url (runner.py) percent-encodes the db-name path segment -- the one
    DSN component make_url() does not auto-decode, unlike userinfo -- and atoms_proof.py's real
    _build_engine() decodes it back after make_url() before handing it to psycopg (as of the
    eighteenth round, only when told to via decode_database_name=True -- see _build_engine()'s
    own docstring for why this is no longer an unconditional guess). Exercise both halves
    together through the real consumer (not string parsing): sixteenth round's "#" case plus
    every other previously-fixed reserved credential character, and this round's "?" case,
    asserting no extra connect_args got injected. Also covers the eighteenth round's own
    password-space finding (finding 3): a literal space in ANYTOOLAI_POSTGRES_PASSWORD must
    survive the real consumer path unmangled."""
    atoms_proof = load_atoms_proof_module()

    runner = load_runner_module()
    identity = runner.RuntimeIdentity("12345678", "anytoolai-12345678", 15555, 18123)
    monkeypatch.setenv("ANYTOOLAI_POSTGRES_USER", "devuser")

    reserved_db_names = [
        "mydb#frag",
        "my db",
        "my@db",
        "my:db",
        "my/db",
        "my%db",
        "mydb?sslmode=disable",
        "plaindb",
    ]
    for password in ("devpassword", "pass word"):
        monkeypatch.setenv("ANYTOOLAI_POSTGRES_PASSWORD", password)
        for db_name in reserved_db_names:
            monkeypatch.setenv("ANYTOOLAI_POSTGRES_DB", db_name)

            engine = atoms_proof._build_engine(identity.database_url, decode_database_name=True)
            connect_args = engine.dialect.create_connect_args(engine.url)[1]

            assert connect_args["dbname"] == db_name, db_name
            assert connect_args["password"] == password, password
            assert connect_args["host"] == "127.0.0.1"
            assert connect_args["port"] == 15555
            assert connect_args["user"] == "devuser"
            non_connection_keys = set(connect_args) - {
                "host", "port", "user", "password", "dbname", "context",
            }
            assert not non_connection_keys, (
                f"{db_name!r} injected extra connect_args: {non_connection_keys}"
            )


def test_prod_compose_command_uses_fixed_project_and_prod_files(monkeypatch, tmp_path) -> None:
    runner = load_runner_module()
    monkeypatch.setattr(runner, "PROD_ENV_FILE", tmp_path / "does-not-exist.env")

    command = runner._prod_compose_command("ps")

    assert command == [
        "docker",
        "compose",
        "--project-name",
        runner.PROD_COMPOSE_PROJECT,
        "-f",
        str(runner.COMPOSE_FILE),
        "-f",
        str(runner.COMPOSE_PROD_FILE),
        "ps",
    ]


def test_prod_compose_command_passes_env_file_when_present(monkeypatch, tmp_path) -> None:
    runner = load_runner_module()
    env_file = tmp_path / ".env.prod"
    env_file.write_text("ANYTOOLAI_POSTGRES_USER=produser\n")
    monkeypatch.setattr(runner, "PROD_ENV_FILE", env_file)

    command = runner._prod_compose_command("ps")

    assert command == [
        "docker",
        "compose",
        "--project-name",
        runner.PROD_COMPOSE_PROJECT,
        "--env-file",
        str(env_file),
        "-f",
        str(runner.COMPOSE_FILE),
        "-f",
        str(runner.COMPOSE_PROD_FILE),
        "ps",
    ]


def test_dev_compose_command_never_passes_prod_env_file(monkeypatch, tmp_path) -> None:
    # Dev must never pick up prod secrets from .env.prod, even if it exists on disk.
    runner = load_runner_module()
    env_file = tmp_path / ".env.prod"
    env_file.write_text("ANYTOOLAI_POSTGRES_USER=produser\n")
    monkeypatch.setattr(runner, "PROD_ENV_FILE", env_file)
    identity = runner.RuntimeIdentity("12345678", "anytoolai-12345678", 15555, 18123)

    command = runner._compose_command(identity, "ps")

    assert "--env-file" not in command


def test_prod_stack_running_reflects_compose_ps_output(monkeypatch) -> None:
    runner = load_runner_module()

    class Result:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    monkeypatch.setattr(
        runner.subprocess, "run", lambda *args, **kwargs: Result("container-id-123\n")
    )
    assert runner._prod_stack_running() is True

    monkeypatch.setattr(runner.subprocess, "run", lambda *args, **kwargs: Result(""))
    assert runner._prod_stack_running() is False


def test_prod_stack_running_propagates_timeout(monkeypatch) -> None:
    runner = load_runner_module()

    def fake_run(*args, **kwargs):
        assert kwargs["timeout"] == 10
        raise runner.subprocess.TimeoutExpired(cmd="docker compose ps -q", timeout=10)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    with pytest.raises(runner.subprocess.TimeoutExpired):
        runner._prod_stack_running()


def test_prod_up_fails_fast_when_docker_daemon_is_wedged(monkeypatch, capsys) -> None:
    runner = load_runner_module()
    monkeypatch.delenv("ANYTOOLAI_PROD_API_PORT", raising=False)

    def fake_prod_stack_running():
        raise runner.subprocess.TimeoutExpired(cmd="docker compose ps -q", timeout=10)

    monkeypatch.setattr(runner, "_prod_stack_running", fake_prod_stack_running)
    monkeypatch.setattr(
        runner,
        "run_with_env",
        lambda command, env: (_ for _ in ()).throw(AssertionError("compose must not run")),
    )

    assert runner.prod_up() == 1
    assert "PROD003" in capsys.readouterr().err


def test_prod_up_fails_before_compose_when_port_is_occupied(monkeypatch) -> None:
    runner = load_runner_module()
    monkeypatch.delenv("ANYTOOLAI_PROD_API_PORT", raising=False)
    monkeypatch.setattr(runner, "_prod_stack_running", lambda: False)
    monkeypatch.setattr(runner, "port_available", lambda port: port != 8000)
    monkeypatch.setattr(
        runner,
        "run_with_env",
        lambda command, env: (_ for _ in ()).throw(AssertionError("compose must not run")),
    )

    assert runner.prod_up() == 1


def test_prod_up_ignores_leftover_dev_port_override(monkeypatch) -> None:
    runner = load_runner_module()
    # A leftover ANYTOOLAI_API_PORT from an earlier `dev-up` in the same shell must not
    # change which port prod checks/binds — prod has its own ANYTOOLAI_PROD_API_PORT.
    monkeypatch.setenv("ANYTOOLAI_API_PORT", "18123")
    monkeypatch.delenv("ANYTOOLAI_PROD_API_PORT", raising=False)
    monkeypatch.setattr(runner, "_prod_stack_running", lambda: False)
    monkeypatch.setattr(runner, "prod_ready", lambda: 0)
    checked_ports: list[int] = []
    monkeypatch.setattr(
        runner,
        "port_available",
        lambda port: checked_ports.append(port) or True,
    )
    monkeypatch.setattr(runner, "run_with_env", lambda command, env: 0)

    assert runner.prod_up() == 0
    assert checked_ports == [8000]


def test_prod_up_skips_port_check_when_stack_already_running(monkeypatch) -> None:
    runner = load_runner_module()
    monkeypatch.delenv("ANYTOOLAI_PROD_API_PORT", raising=False)
    monkeypatch.setattr(runner, "_prod_stack_running", lambda: True)
    monkeypatch.setattr(runner, "prod_ready", lambda: 0)
    monkeypatch.setattr(
        runner,
        "port_available",
        lambda port: (_ for _ in ()).throw(AssertionError("must not check ports on redeploy")),
    )
    commands: list[list[str]] = []
    monkeypatch.setattr(
        runner,
        "run_with_env",
        lambda command, env: commands.append(list(command)) or 0,
    )

    assert runner.prod_up() == 0
    assert commands[0][-4:] == ["up", "-d", "--build", "--remove-orphans"]


def test_prod_status_and_down_use_prod_project(monkeypatch) -> None:
    runner = load_runner_module()
    commands: list[list[str]] = []
    timeouts: list[float | None] = []
    monkeypatch.setattr(
        runner,
        "run_with_env",
        lambda command, env, timeout=None: (
            commands.append(list(command)) or timeouts.append(timeout) or 0
        ),
    )

    assert runner.prod_status() == 0
    assert runner.prod_down() == 0
    assert all(runner.PROD_COMPOSE_PROJECT in command for command in commands)
    assert commands[0][-1] == "ps"
    assert commands[1][-2:] == ["down", "--remove-orphans"]
    assert timeouts == [runner.COMPOSE_QUERY_TIMEOUT_SECONDS, runner.COMPOSE_QUERY_TIMEOUT_SECONDS]


def test_prod_up_builds_and_removes_orphans(monkeypatch) -> None:
    runner = load_runner_module()
    monkeypatch.delenv("ANYTOOLAI_PROD_API_PORT", raising=False)
    monkeypatch.setattr(runner, "_prod_stack_running", lambda: False)
    monkeypatch.setattr(runner, "port_available", lambda port: True)
    monkeypatch.setattr(runner, "prod_ready", lambda: 0)
    commands: list[list[str]] = []
    timeouts: list[float | None] = []
    monkeypatch.setattr(
        runner,
        "run_with_env",
        lambda command, env, timeout=None: (
            commands.append(list(command)) or timeouts.append(timeout) or 0
        ),
    )

    assert runner.prod_up() == 0
    assert commands[0][-4:] == ["up", "-d", "--build", "--remove-orphans"]
    # Deliberately unbounded: --build can legitimately take minutes on a cold build.
    assert timeouts == [None]


def test_prod_up_calls_prod_ready_after_successful_up(monkeypatch) -> None:
    runner = load_runner_module()
    monkeypatch.delenv("ANYTOOLAI_PROD_API_PORT", raising=False)
    monkeypatch.setattr(runner, "_prod_stack_running", lambda: False)
    monkeypatch.setattr(runner, "port_available", lambda port: True)
    monkeypatch.setattr(runner, "run_with_env", lambda command, env: 0)
    calls: list[str] = []
    monkeypatch.setattr(runner, "prod_ready", lambda: calls.append("prod_ready") or 42)

    assert runner.prod_up() == 42
    assert calls == ["prod_ready"]


def test_prod_up_skips_ready_check_when_compose_up_fails(monkeypatch) -> None:
    runner = load_runner_module()
    monkeypatch.delenv("ANYTOOLAI_PROD_API_PORT", raising=False)
    monkeypatch.setattr(runner, "_prod_stack_running", lambda: False)
    monkeypatch.setattr(runner, "port_available", lambda port: True)
    monkeypatch.setattr(runner, "run_with_env", lambda command, env: 1)
    monkeypatch.setattr(
        runner,
        "prod_ready",
        lambda: (_ for _ in ()).throw(AssertionError("must not poll readiness after failed up")),
    )

    assert runner.prod_up() == 1


def test_prod_ready_waits_for_health(monkeypatch) -> None:
    runner = load_runner_module()
    monkeypatch.delenv("ANYTOOLAI_PROD_API_PORT", raising=False)
    monkeypatch.delenv("ANYTOOLAI_READY_TIMEOUT", raising=False)

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    requested_urls: list[str] = []

    def fake_urlopen(url, timeout):
        requested_urls.append(url)
        return Response()

    monkeypatch.setattr(runner.urllib.request, "urlopen", fake_urlopen)

    assert runner.prod_ready() == 0
    assert requested_urls == ["http://127.0.0.1:8000/health"]


def test_prod_ready_uses_prod_port_variable_not_dev_port(monkeypatch) -> None:
    runner = load_runner_module()
    # A leftover ANYTOOLAI_API_PORT from dev work in the same shell must not redirect
    # which port prod-ready polls — prod has its own ANYTOOLAI_PROD_API_PORT.
    monkeypatch.setenv("ANYTOOLAI_API_PORT", "18123")
    monkeypatch.setenv("ANYTOOLAI_PROD_API_PORT", "18900")
    monkeypatch.delenv("ANYTOOLAI_READY_TIMEOUT", raising=False)

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    requested_urls: list[str] = []
    monkeypatch.setattr(
        runner.urllib.request,
        "urlopen",
        lambda url, timeout: requested_urls.append(url) or Response(),
    )

    assert runner.prod_ready() == 0
    assert requested_urls == ["http://127.0.0.1:18900/health"]


def test_prod_ready_times_out_with_prod004(monkeypatch, capsys) -> None:
    runner = load_runner_module()
    monkeypatch.delenv("ANYTOOLAI_PROD_API_PORT", raising=False)
    monkeypatch.setenv("ANYTOOLAI_READY_TIMEOUT", "0")
    monkeypatch.setattr(
        runner.urllib.request,
        "urlopen",
        lambda url, timeout: (_ for _ in ()).throw(OSError("connection refused")),
    )

    assert runner.prod_ready() == 1
    assert "PROD004" in capsys.readouterr().err


def test_prod_ready_reports_prod001_for_invalid_port_override(monkeypatch, capsys) -> None:
    runner = load_runner_module()
    monkeypatch.setenv("ANYTOOLAI_PROD_API_PORT", "not-a-port")

    assert runner.prod_ready() == 2
    assert "PROD001" in capsys.readouterr().err


def test_dev_smoke_invokes_kernel_demo_smoke_against_worktree_api_url(monkeypatch) -> None:
    runner = load_runner_module()
    identity = runner.RuntimeIdentity("12345678", "anytoolai-12345678", 15555, 18123)
    monkeypatch.setattr(runner, "runtime_identity", lambda: identity)
    commands: list[list[str]] = []
    monkeypatch.setattr(
        runner, "run", lambda command: commands.append(list(command)) or 0
    )

    assert runner.dev_smoke() == 0
    assert commands == [
        [runner.sys.executable, "scripts/agent/kernel_demo_smoke.py", identity.api_url]
    ]


def test_dev_smoke_reports_dev001_for_invalid_port_override(monkeypatch, capsys) -> None:
    runner = load_runner_module()

    def fake_runtime_identity():
        raise ValueError("ANYTOOLAI_API_PORT must be an integer port")

    monkeypatch.setattr(runner, "runtime_identity", fake_runtime_identity)

    assert runner.dev_smoke() == 2
    assert "DEV001" in capsys.readouterr().err


def test_quick_check_dependency_fingerprint_changes_when_an_input_file_changes(
    monkeypatch, tmp_path
) -> None:
    """Code-review finding (#me 1): the fingerprint must actually reflect uv.lock/pyproject.toml
    content, not just their existence, or dependency-state drift would go undetected."""
    runner = load_runner_module()
    lock_file = tmp_path / "uv.lock"
    lock_file.write_text("original lock contents", encoding="utf-8")
    monkeypatch.setattr(runner, "QUICK_CHECK_DEPENDENCY_FINGERPRINT_INPUTS", [lock_file])

    before = runner.quick_check_dependency_fingerprint()
    lock_file.write_text("changed lock contents", encoding="utf-8")
    after = runner.quick_check_dependency_fingerprint()

    assert before != after


def test_quick_check_venv_ready_rejects_stale_marker(monkeypatch, tmp_path) -> None:
    """Code-review finding (#me 1): a marker whose stored fingerprint no longer matches the
    current dependency inputs (e.g. after `git pull` changed uv.lock) must not be treated as
    ready -- .quick-check-venv is gitignored and survives such a pull untouched."""
    runner = load_runner_module()
    venv_python = tmp_path / "python"
    venv_python.touch()
    monkeypatch.setattr(runner, "quick_check_dependency_fingerprint", lambda: "current-fingerprint")

    (venv_python.parent / ".bootstrap-complete").write_text("stale-fingerprint", encoding="utf-8")
    assert runner.quick_check_venv_ready(venv_python) is False

    (venv_python.parent / ".bootstrap-complete").write_text("current-fingerprint", encoding="utf-8")
    assert runner.quick_check_venv_ready(venv_python) is True


def test_proof_script_fails_fast_when_quick_check_venv_missing(monkeypatch, tmp_path, capsys) -> None:
    """ANY-390: on a fresh checkout that never ran quick-check, atoms-proof/live-canary must fail
    with a clear setup instruction instead of silently launching sys.executable and reproducing
    the PROOF000 missing-dependency bug -- shared by both commands via _run_proof_script()."""
    runner = load_runner_module()
    missing_venv_python = tmp_path / "does-not-exist" / "python"
    monkeypatch.setattr(runner, "quick_check_venv_python", lambda: missing_venv_python)
    monkeypatch.setattr(
        runner, "run_with_env", lambda command, env: pytest.fail("subprocess must not launch")
    )

    assert runner.atoms_proof() == 2

    err = capsys.readouterr().err
    assert "ENV001" in err
    assert "quick-check" in err


def test_proof_script_fails_fast_when_quick_check_venv_incomplete(monkeypatch, tmp_path, capsys) -> None:
    """ANY-390 round-4 code-review finding: a bootstrap interrupted mid-way can leave
    .quick-check-venv's python in place without every editable package installed -- exists()
    alone would wrongly treat that as ready and let the child fail deep with a raw
    ModuleNotFoundError instead of a clear ENV001."""
    runner = load_runner_module()
    venv_python = tmp_path / "python"
    venv_python.touch()
    monkeypatch.setattr(runner, "quick_check_venv_python", lambda: venv_python)
    monkeypatch.setattr(
        runner, "run_with_env", lambda command, env: pytest.fail("subprocess must not launch")
    )

    assert runner.atoms_proof() == 2

    err = capsys.readouterr().err
    assert "ENV001" in err
    assert "quick-check" in err


def test_proof_script_fails_fast_when_quick_check_venv_dependency_state_is_stale(
    monkeypatch, tmp_path, capsys
) -> None:
    """Code-review finding (#me 1): .quick-check-venv is gitignored and survives pulls/branch
    switches -- a successful bootstrap followed by dependency-state drift (uv.lock or an editable
    project's pyproject.toml changing underneath it) must not be treated as ready, or
    atoms-proof/live-canary would launch a stale interpreter and hit PROOF000 instead of ENV001."""
    runner = load_runner_module()
    venv_python = tmp_path / "python"
    venv_python.touch()
    (venv_python.parent / ".bootstrap-complete").write_text(
        "fingerprint-from-a-past-bootstrap", encoding="utf-8"
    )
    monkeypatch.setattr(runner, "quick_check_venv_python", lambda: venv_python)
    monkeypatch.setattr(
        runner, "quick_check_dependency_fingerprint", lambda: "fingerprint-after-uv-lock-changed"
    )
    monkeypatch.setattr(
        runner, "run_with_env", lambda command, env: pytest.fail("subprocess must not launch")
    )

    assert runner.atoms_proof() == 2

    err = capsys.readouterr().err
    assert "ENV001" in err
    assert "quick-check" in err


def test_atoms_proof_reports_dev001_for_invalid_port_override(monkeypatch, tmp_path, capsys) -> None:
    runner = load_runner_module()
    venv_python = tmp_path / "python"
    venv_python.touch()
    (venv_python.parent / ".bootstrap-complete").write_text("test-fingerprint", encoding="utf-8")
    monkeypatch.setattr(runner, "quick_check_dependency_fingerprint", lambda: "test-fingerprint")
    monkeypatch.setattr(runner, "quick_check_venv_python", lambda: venv_python)

    def fake_runtime_identity():
        raise ValueError("ANYTOOLAI_API_PORT must be an integer port")

    monkeypatch.setattr(runner, "runtime_identity", fake_runtime_identity)

    assert runner.atoms_proof() == 2
    assert "DEV001" in capsys.readouterr().err


def test_atoms_proof_passes_database_url_via_env_not_argv(monkeypatch, tmp_path) -> None:
    """Fourteenth code review pass finding: identity.database_url can embed a real
    ANYTOOLAI_POSTGRES_PASSWORD override, so it must reach atoms_proof.py through the
    subprocess's environment (invisible to `ps`/process listings), not as a literal argv value
    -- the child only ever sees the *name* of the env var on its own command line."""
    runner = load_runner_module()
    venv_python = tmp_path / "python"
    venv_python.touch()
    (venv_python.parent / ".bootstrap-complete").write_text("test-fingerprint", encoding="utf-8")
    monkeypatch.setattr(runner, "quick_check_dependency_fingerprint", lambda: "test-fingerprint")
    monkeypatch.setattr(runner, "quick_check_venv_python", lambda: venv_python)
    identity = runner.RuntimeIdentity("12345678", "anytoolai-12345678", 15555, 18123)
    monkeypatch.setattr(runner, "runtime_identity", lambda: identity)
    calls: list[tuple[list[str], dict[str, str]]] = []
    monkeypatch.setattr(
        runner,
        "run_with_env",
        lambda command, env: calls.append((list(command), dict(env))) or 0,
    )

    assert runner.atoms_proof() == 0

    assert len(calls) == 1
    command, env = calls[0]
    assert identity.database_url not in command
    env_var_name = command[4]
    # Full argv, not just the database-url-env prefix: deleting --database-url-is-percent-
    # encoded would silently leave a reserved-character database name encoded on the wire, and
    # would have stayed green under the prior prefix-only assertion.
    assert command == [
        str(venv_python), "scripts/agent/atoms_proof.py", identity.api_url,
        "--database-url-env", env_var_name,
        "--database-url-is-percent-encoded",
    ]
    assert env[env_var_name] == identity.database_url


def test_atoms_proof_is_registered_in_commands() -> None:
    """Cheap regression against COMMANDS["atoms-proof"] silently pointing
    at the wrong function."""
    runner = load_runner_module()

    assert runner.COMMANDS["atoms-proof"] is runner.atoms_proof


def test_proof_script_uses_managed_venv_python_not_sys_executable(monkeypatch, tmp_path) -> None:
    """ANY-390 regression: atoms_proof()/live_canary() must launch their sibling script with
    .quick-check-venv's python, not sys.executable -- a bare system Python lacks platform-actions'
    markdown-it-py and fails with PROOF000 before any proof logic runs."""
    runner = load_runner_module()
    venv_python = tmp_path / "python"
    venv_python.touch()
    (venv_python.parent / ".bootstrap-complete").write_text("test-fingerprint", encoding="utf-8")
    monkeypatch.setattr(runner, "quick_check_dependency_fingerprint", lambda: "test-fingerprint")
    monkeypatch.setattr(runner, "quick_check_venv_python", lambda: venv_python)
    monkeypatch.setattr(runner.sys, "executable", "/usr/bin/python3")
    identity = runner.RuntimeIdentity("12345678", "anytoolai-12345678", 15555, 18123)
    monkeypatch.setattr(runner, "runtime_identity", lambda: identity)
    calls: list[list[str]] = []
    monkeypatch.setattr(
        runner, "run_with_env", lambda command, env: calls.append(list(command)) or 0
    )

    assert runner.atoms_proof() == 0

    assert calls[0][0] == str(venv_python)
    assert calls[0][0] != runner.sys.executable


def test_live_canary_fails_without_openai_api_key(monkeypatch, capsys) -> None:
    runner = load_runner_module()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        runner,
        "runtime_identity",
        lambda: pytest.fail("live_canary must not touch Docker/DB without OPENAI_API_KEY"),
    )

    assert runner.live_canary() == 2
    assert "LIVE000" in capsys.readouterr().err


def test_live_canary_fails_without_live_canary_token(monkeypatch, capsys) -> None:
    """Code-review finding: the 14 live scenario_ids are config-flagged internal_only, so
    platform-api rejects every case without a token matching its own
    ANYTOOLAI_LIVE_CANARY_TOKEN -- fail clearly up front instead of letting every case fail
    LIVE-layer 404s one by one."""
    runner = load_runner_module()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("ANYTOOLAI_LIVE_CANARY_TOKEN", raising=False)
    monkeypatch.setattr(
        runner,
        "runtime_identity",
        lambda: pytest.fail("live_canary must not touch Docker/DB without a live-canary token"),
    )

    assert runner.live_canary() == 2
    assert "LIVE011" in capsys.readouterr().err


def test_live_canary_reports_dev001_for_invalid_port_override(monkeypatch, tmp_path, capsys) -> None:
    runner = load_runner_module()
    venv_python = tmp_path / "python"
    venv_python.touch()
    (venv_python.parent / ".bootstrap-complete").write_text("test-fingerprint", encoding="utf-8")
    monkeypatch.setattr(runner, "quick_check_dependency_fingerprint", lambda: "test-fingerprint")
    monkeypatch.setattr(runner, "quick_check_venv_python", lambda: venv_python)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ANYTOOLAI_LIVE_CANARY_TOKEN", "sekret")

    def fake_runtime_identity():
        raise ValueError("ANYTOOLAI_API_PORT must be an integer port")

    monkeypatch.setattr(runner, "runtime_identity", fake_runtime_identity)

    assert runner.live_canary() == 2
    assert "DEV001" in capsys.readouterr().err


def test_live_canary_passes_database_url_via_env_not_argv(monkeypatch, tmp_path) -> None:
    runner = load_runner_module()
    venv_python = tmp_path / "python"
    venv_python.touch()
    (venv_python.parent / ".bootstrap-complete").write_text("test-fingerprint", encoding="utf-8")
    monkeypatch.setattr(runner, "quick_check_dependency_fingerprint", lambda: "test-fingerprint")
    monkeypatch.setattr(runner, "quick_check_venv_python", lambda: venv_python)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ANYTOOLAI_LIVE_CANARY_TOKEN", "sekret")
    identity = runner.RuntimeIdentity("12345678", "anytoolai-12345678", 15555, 18123)
    monkeypatch.setattr(runner, "runtime_identity", lambda: identity)
    calls: list[tuple[list[str], dict[str, str]]] = []
    monkeypatch.setattr(
        runner,
        "run_with_env",
        lambda command, env: calls.append((list(command), dict(env))) or 0,
    )

    assert runner.live_canary() == 0

    assert len(calls) == 1
    command, env = calls[0]
    assert identity.database_url not in command
    env_var_name = command[4]
    # Full argv, not just the database-url-env prefix: atoms_proof() passes
    # --database-url-is-percent-encoded for the same identity.database_url; live_canary() must
    # too, or a reserved-character ANYTOOLAI_POSTGRES_PASSWORD/_DB connects fine via atoms-proof
    # but silently fails to connect via live-canary on the same stack.
    assert command == [
        str(venv_python), "scripts/agent/live_canary.py", identity.api_url,
        "--database-url-env", env_var_name,
        "--database-url-is-percent-encoded",
    ]
    assert env[env_var_name] == identity.database_url
    # `code-review` nitpick: _run_proof_script()'s env comes from runner_env()
    # (os.environ.copy() plus a few extras), so the subprocess that actually makes the request
    # must inherit ANYTOOLAI_LIVE_CANARY_TOKEN from this test's own monkeypatched os.environ, not
    # just have it checked by live_canary()'s own upfront LIVE011 fail-fast.
    assert env["ANYTOOLAI_LIVE_CANARY_TOKEN"] == "sekret"


def test_prod_smoke_invokes_kernel_demo_smoke_against_prod_port(monkeypatch) -> None:
    runner = load_runner_module()
    monkeypatch.setenv("ANYTOOLAI_PROD_API_PORT", "18900")
    commands: list[list[str]] = []
    monkeypatch.setattr(
        runner, "run", lambda command: commands.append(list(command)) or 0
    )

    assert runner.prod_smoke() == 0
    assert commands == [
        [runner.sys.executable, "scripts/agent/kernel_demo_smoke.py", "http://127.0.0.1:18900"]
    ]


def test_prod_smoke_reports_prod001_for_invalid_port_override(monkeypatch, capsys) -> None:
    runner = load_runner_module()
    monkeypatch.setenv("ANYTOOLAI_PROD_API_PORT", "not-a-port")

    assert runner.prod_smoke() == 2
    assert "PROD001" in capsys.readouterr().err


def test_dev_up_does_not_bound_the_build(monkeypatch) -> None:
    runner = load_runner_module()
    identity = runner.RuntimeIdentity("12345678", "anytoolai-12345678", 15555, 18123)
    monkeypatch.setattr(runner, "runtime_identity", lambda: identity)
    monkeypatch.setattr(runner, "port_available", lambda port: True)
    monkeypatch.setattr(runner, "dev_ready", lambda: 0)
    timeouts: list[float | None] = []
    monkeypatch.setattr(
        runner,
        "run_with_env",
        lambda command, env, timeout=None: timeouts.append(timeout) or 0,
    )

    assert runner.dev_up() == 0
    # Deliberately unbounded: a cold image build can legitimately take minutes.
    assert timeouts == [None]


def test_run_with_env_reports_timeout_and_returns_124(monkeypatch, capsys) -> None:
    runner = load_runner_module()

    def fake_subprocess_run(*args, **kwargs):
        assert kwargs["timeout"] == 5
        raise runner.subprocess.TimeoutExpired(cmd=args[0], timeout=5)

    monkeypatch.setattr(runner.subprocess, "run", fake_subprocess_run)

    exit_code = runner.run_with_env(["docker", "compose", "ps"], {}, timeout=5)

    assert exit_code == 124
    assert "timed out after 5s" in capsys.readouterr().err


def test_run_with_env_has_no_timeout_by_default(monkeypatch) -> None:
    runner = load_runner_module()
    captured_kwargs = {}

    class Result:
        returncode = 0

    def fake_subprocess_run(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return Result()

    monkeypatch.setattr(runner.subprocess, "run", fake_subprocess_run)

    assert runner.run_with_env(["docker", "compose", "ps"], {}) == 0
    assert captured_kwargs["timeout"] is None
