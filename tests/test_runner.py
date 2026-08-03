from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml


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


def test_postgresql_check_uses_marker_driven_backend_roots(monkeypatch) -> None:
    runner = load_runner_module()
    commands: list[list[str]] = []
    monkeypatch.setenv(
        runner.POSTGRESQL_TEST_DATABASE_URL_ENV,
        "postgresql+psycopg://anytoolai:anytoolai@127.0.0.1:5432/postgres",
    )
    monkeypatch.setattr(runner.sys, "executable", "/tmp/repo/.venv/bin/python")
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
