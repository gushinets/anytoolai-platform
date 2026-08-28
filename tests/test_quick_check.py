from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def load_quick_check_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "agent" / "quick_check.py"
    spec = importlib.util.spec_from_file_location("quick_check_module", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def venv_python_path(venv_root: Path, *, windows: bool) -> Path:
    scripts_dir = "Scripts" if windows else "bin"
    python_name = "python.exe" if windows else "python"
    return venv_root / scripts_dir / python_name


def test_environment_detection_distinguishes_new_and_legacy_venvs(monkeypatch, tmp_path) -> None:
    quick_check = load_quick_check_module()
    repo_root = tmp_path / "repo"
    new_venv = repo_root / ".quick-check-venv"
    legacy_venv = repo_root / ".venv" / "quick-check"

    monkeypatch.setattr(quick_check, "ROOT", repo_root)
    monkeypatch.setattr(quick_check, "VENV_DIR", new_venv)
    monkeypatch.setattr(quick_check, "LEGACY_VENV_DIR", legacy_venv)

    monkeypatch.setattr(quick_check.sys, "prefix", str(new_venv))
    assert quick_check.is_quick_check_environment() is True
    assert quick_check.is_legacy_quick_check_environment() is False

    monkeypatch.setattr(quick_check.sys, "prefix", str(legacy_venv))
    assert quick_check.is_quick_check_environment() is False
    assert quick_check.is_legacy_quick_check_environment() is True


def test_ensure_virtualenv_keeps_active_legacy_environment_until_reexec(
    monkeypatch, tmp_path
) -> None:
    quick_check = load_quick_check_module()
    repo_root = tmp_path / "repo"
    new_venv = repo_root / ".quick-check-venv"
    legacy_venv = repo_root / ".venv" / "quick-check"
    expected_python = venv_python_path(new_venv, windows=quick_check.os.name == "nt")
    legacy_python = venv_python_path(legacy_venv, windows=quick_check.os.name == "nt")
    script_path = Path(quick_check.__file__).resolve()

    new_venv.mkdir(parents=True)
    legacy_venv.mkdir(parents=True)
    expected_python.parent.mkdir(parents=True)
    expected_python.write_text("", encoding="utf-8")

    monkeypatch.setattr(quick_check, "ROOT", repo_root)
    monkeypatch.setattr(quick_check, "VENV_DIR", new_venv)
    monkeypatch.setattr(quick_check, "LEGACY_VENV_DIR", legacy_venv)
    monkeypatch.setattr(quick_check.sys, "prefix", str(legacy_venv))
    monkeypatch.setattr(quick_check.sys, "executable", str(legacy_python))
    monkeypatch.setattr(quick_check.sys, "version_info", (3, 12, 1))
    monkeypatch.setattr(quick_check.sys, "argv", ["scripts/agent/quick_check.py"])

    migrate_calls: list[str] = []
    reexec_calls: list[tuple[list[str], dict[str, str]]] = []

    monkeypatch.setattr(quick_check, "python_version", lambda executable: (3, 12))
    monkeypatch.setattr(quick_check, "run", lambda command: (_ for _ in ()).throw(AssertionError(command)))
    monkeypatch.setattr(
        quick_check,
        "migrate_legacy_virtualenv",
        lambda: migrate_calls.append("migrate"),
    )
    monkeypatch.setattr(
        quick_check,
        "run_with_env",
        lambda command, env: reexec_calls.append((list(command), dict(env))) or 0,
    )
    monkeypatch.delenv("ANYTOOLAI_QUICK_CHECK_BOOTSTRAPPED", raising=False)

    exit_code = quick_check.ensure_virtualenv()

    assert exit_code == 0
    assert migrate_calls == []
    assert len(reexec_calls) == 1
    command, env = reexec_calls[0]
    assert command == [str(expected_python), str(script_path)]
    assert env["ANYTOOLAI_QUICK_CHECK_BOOTSTRAPPED"] == "1"


def test_ensure_virtualenv_reexec_forwards_cli_args(monkeypatch, tmp_path) -> None:
    """ANY-390: live-canary.yml's --bootstrap-only flag must survive the venv-creation re-exec
    (a cold runner never has .quick-check-venv yet) or the re-exec'd child silently falls through
    to main()'s full validate/pytest tail instead of stopping after bootstrap()."""
    quick_check = load_quick_check_module()
    repo_root = tmp_path / "repo"
    new_venv = repo_root / ".quick-check-venv"
    expected_python = venv_python_path(new_venv, windows=quick_check.os.name == "nt")
    script_path = Path(quick_check.__file__).resolve()

    monkeypatch.setattr(quick_check, "ROOT", repo_root)
    monkeypatch.setattr(quick_check, "VENV_DIR", new_venv)
    monkeypatch.setattr(quick_check, "LEGACY_VENV_DIR", repo_root / ".venv" / "quick-check")
    monkeypatch.setattr(quick_check.sys, "prefix", str(repo_root / "system-python"))
    monkeypatch.setattr(quick_check.sys, "version_info", (3, 12, 1))
    monkeypatch.setattr(quick_check.sys, "argv", ["scripts/agent/quick_check.py", "--bootstrap-only"])
    monkeypatch.setattr(quick_check, "run", lambda command: 0)
    monkeypatch.delenv("ANYTOOLAI_QUICK_CHECK_BOOTSTRAPPED", raising=False)

    reexec_calls: list[tuple[list[str], dict[str, str]]] = []
    monkeypatch.setattr(
        quick_check,
        "run_with_env",
        lambda command, env: reexec_calls.append((list(command), dict(env))) or 0,
    )

    exit_code = quick_check.ensure_virtualenv()

    assert exit_code == 0
    assert len(reexec_calls) == 1
    command, _env = reexec_calls[0]
    assert command == [str(expected_python), str(script_path), "--bootstrap-only"]


def test_main_bootstrap_only_skips_validate_and_pytest(monkeypatch) -> None:
    """ANY-390: live-canary.yml only needs .quick-check-venv provisioned, not this repo's full
    DB-free pytest/validate suite gating its weekly credentialed run."""
    quick_check = load_quick_check_module()
    monkeypatch.setattr(quick_check.sys, "argv", ["scripts/agent/quick_check.py", "--bootstrap-only"])
    monkeypatch.setattr(quick_check, "ensure_virtualenv", lambda: None)
    monkeypatch.setattr(quick_check, "bootstrap", lambda: 0)
    monkeypatch.setattr(
        quick_check,
        "run_sequence",
        lambda sequence: pytest.fail("validate/pytest sequence must not run with --bootstrap-only"),
    )

    assert quick_check.main() == 0


def test_ensure_virtualenv_cleans_legacy_environment_once_new_environment_is_active(
    monkeypatch, tmp_path
) -> None:
    quick_check = load_quick_check_module()
    repo_root = tmp_path / "repo"
    new_venv = repo_root / ".quick-check-venv"
    legacy_venv = repo_root / ".venv" / "quick-check"
    expected_python = venv_python_path(new_venv, windows=quick_check.os.name == "nt")

    new_venv.mkdir(parents=True)
    expected_python.parent.mkdir(parents=True)
    expected_python.write_text("", encoding="utf-8")

    monkeypatch.setattr(quick_check, "ROOT", repo_root)
    monkeypatch.setattr(quick_check, "VENV_DIR", new_venv)
    monkeypatch.setattr(quick_check, "LEGACY_VENV_DIR", legacy_venv)
    monkeypatch.setattr(quick_check.sys, "prefix", str(new_venv))
    monkeypatch.setattr(quick_check.sys, "version_info", (3, 12, 1))

    migrate_calls: list[str] = []

    monkeypatch.setattr(quick_check, "python_version", lambda executable: (3, 12))
    monkeypatch.setattr(
        quick_check,
        "migrate_legacy_virtualenv",
        lambda: migrate_calls.append("migrate"),
    )

    exit_code = quick_check.ensure_virtualenv()

    assert exit_code is None
    assert migrate_calls == ["migrate"]


def test_bootstrap_syncs_root_environment_from_locked_uv_state(monkeypatch, tmp_path) -> None:
    quick_check = load_quick_check_module()
    venv_dir = tmp_path / ".quick-check-venv"
    scripts_dir = "Scripts" if quick_check.os.name == "nt" else "bin"
    # ensure_virtualenv() always creates this before main() calls bootstrap() -- mirror that
    # precondition instead of adding defensive mkdir logic to bootstrap() itself.
    (venv_dir / scripts_dir).mkdir(parents=True)
    project_one = tmp_path / "project-one"
    project_two = tmp_path / "project-two"
    commands: list[list[str]] = []

    monkeypatch.setattr(quick_check, "VENV_DIR", venv_dir)
    monkeypatch.setattr(quick_check.sys, "executable", "/tmp/.quick-check-venv/bin/python")
    monkeypatch.setattr(quick_check, "EDITABLE_PROJECTS", [project_one, project_two])
    # Isolate the fingerprint from real repo state -- it's built from EDITABLE_PROJECTS at module
    # load time, before the monkeypatch above, so it must be pointed at tmp_path explicitly too.
    monkeypatch.setattr(quick_check, "DEPENDENCY_FINGERPRINT_INPUTS", [tmp_path / "uv.lock"])
    monkeypatch.setattr(
        quick_check.shutil,
        "which",
        lambda name: "/usr/local/bin/uv" if name == "uv" else None,
    )
    monkeypatch.setattr(
        quick_check,
        "run_sequence",
        lambda sequence: commands.extend(list(command) for command in sequence) or 0,
    )

    exit_code = quick_check.bootstrap()

    assert exit_code == 0
    assert commands == [
        [
            "/usr/local/bin/uv",
            "sync",
            "--python",
            "/tmp/.quick-check-venv/bin/python",
            "--active",
            "--locked",
            "--no-default-groups",
            "--group",
            "dev",
        ],
        [
            "/usr/local/bin/uv",
            "pip",
            "install",
            "--python",
            "/tmp/.quick-check-venv/bin/python",
            "--no-deps",
            "-e",
            str(project_one),
        ],
        [
            "/usr/local/bin/uv",
            "pip",
            "install",
            "--python",
            "/tmp/.quick-check-venv/bin/python",
            "--no-deps",
            "-e",
            str(project_two),
        ],
    ]
    marker = venv_dir / scripts_dir / ".bootstrap-complete"
    assert marker.read_text(encoding="utf-8") == quick_check.dependency_fingerprint()


def test_marker_fingerprint_changes_when_dependency_state_drifts(monkeypatch, tmp_path) -> None:
    """Code-review finding (#me 1): a marker written for one dependency state must not read as
    valid once uv.lock/an editable project's pyproject.toml changes underneath the gitignored,
    pull-surviving .quick-check-venv."""
    quick_check = load_quick_check_module()
    lock_file = tmp_path / "uv.lock"
    lock_file.write_text("original", encoding="utf-8")
    monkeypatch.setattr(quick_check, "DEPENDENCY_FINGERPRINT_INPUTS", [lock_file])

    written = quick_check.dependency_fingerprint()
    lock_file.write_text("changed by a pull/branch switch", encoding="utf-8")
    recomputed = quick_check.dependency_fingerprint()

    assert written != recomputed


def test_bootstrap_leaves_no_marker_on_failure(monkeypatch, tmp_path) -> None:
    """ANY-390: a bootstrap that fails partway through (e.g. one editable install errors) must not
    leave the completion marker behind -- otherwise atoms-proof/live-canary's readiness check
    would treat an incomplete venv as ready. Also covers a re-bootstrap that fails after a prior
    successful run: the stale marker from that earlier success must not survive, or the readiness
    check would treat a now-possibly-broken venv as ready."""
    quick_check = load_quick_check_module()
    venv_dir = tmp_path / ".quick-check-venv"
    scripts_dir = "Scripts" if quick_check.os.name == "nt" else "bin"
    (venv_dir / scripts_dir).mkdir(parents=True)
    stale_marker = venv_dir / scripts_dir / ".bootstrap-complete"
    stale_marker.touch()

    monkeypatch.setattr(quick_check, "VENV_DIR", venv_dir)
    monkeypatch.setattr(quick_check, "run_sequence", lambda sequence: 1)

    assert quick_check.bootstrap() == 1
    assert not stale_marker.exists()


def test_runtime_env_uses_workspace_owned_temp_and_cache_dirs(monkeypatch, tmp_path) -> None:
    quick_check = load_quick_check_module()
    repo_root = tmp_path / "repo"
    tmp_root = repo_root / ".quick-check-tmp"

    monkeypatch.setattr(quick_check, "ROOT", repo_root)
    monkeypatch.setattr(quick_check, "TMP_ROOT", tmp_root)

    env = quick_check.runtime_env({"ANYTOOLAI_QUICK_CHECK_BOOTSTRAPPED": "1"})

    assert env["ANYTOOLAI_QUICK_CHECK_BOOTSTRAPPED"] == "1"
    assert env["TMPDIR"] == str(tmp_root / "tmp")
    assert env["TMP"] == str(tmp_root / "tmp")
    assert env["TEMP"] == str(tmp_root / "tmp")
    assert env["UV_CACHE_DIR"] == str(tmp_root / "uv-cache")
    assert env["PIP_CACHE_DIR"] == str(tmp_root / "pip-cache")
    assert env["PYTEST_DEBUG_TEMPROOT"] == str(tmp_root / "pytest")
    assert (tmp_root / "tmp").is_dir()
    assert (tmp_root / "uv-cache").is_dir()
    assert (tmp_root / "pip-cache").is_dir()
    assert (tmp_root / "pytest").is_dir()


def test_runtime_env_strips_pythonpath_from_direct_invocation(monkeypatch, tmp_path) -> None:
    quick_check = load_quick_check_module()
    repo_root = tmp_path / "repo"
    tmp_root = repo_root / ".quick-check-tmp"

    monkeypatch.setattr(quick_check, "ROOT", repo_root)
    monkeypatch.setattr(quick_check, "TMP_ROOT", tmp_root)
    monkeypatch.setenv("PYTHONPATH", "/some/path")

    env = quick_check.runtime_env()

    assert "PYTHONPATH" not in env


def test_runtime_env_exports_virtualenv_for_managed_quick_check(monkeypatch, tmp_path) -> None:
    quick_check = load_quick_check_module()
    repo_root = tmp_path / "repo"
    tmp_root = repo_root / ".quick-check-tmp"
    managed_venv = repo_root / ".quick-check-venv"

    monkeypatch.setattr(quick_check, "ROOT", repo_root)
    monkeypatch.setattr(quick_check, "TMP_ROOT", tmp_root)
    monkeypatch.setattr(quick_check.sys, "prefix", str(managed_venv))
    monkeypatch.setattr(quick_check.sys, "base_prefix", str(repo_root / ".python-base"))

    env = quick_check.runtime_env()

    assert env["VIRTUAL_ENV"] == str(managed_venv)


def test_pytest_command_uses_repo_managed_basetemp(monkeypatch, tmp_path) -> None:
    quick_check = load_quick_check_module()
    repo_root = tmp_path / "repo"
    tmp_root = repo_root / ".quick-check-tmp"

    monkeypatch.setattr(quick_check, "ROOT", repo_root)
    monkeypatch.setattr(quick_check, "TMP_ROOT", tmp_root)
    monkeypatch.setattr(quick_check, "PYTEST_BASETEMP_ROOT", tmp_root / "pytest-runs")
    monkeypatch.setattr(quick_check.sys, "executable", "/tmp/.quick-check-venv/bin/python")
    monkeypatch.setattr(quick_check.os, "getpid", lambda: 4321)

    command = quick_check.pytest_command()

    assert command == [
        "/tmp/.quick-check-venv/bin/python",
        "-m",
        "pytest",
        "-m",
        "not slow",
        "--basetemp",
        str(tmp_root / "pytest-runs" / "run-4321"),
        *quick_check.PYTEST_TARGETS,
    ]


def test_main_excludes_slow_tests_from_fast_pytest_path(monkeypatch) -> None:
    quick_check = load_quick_check_module()
    commands: list[list[str]] = []

    monkeypatch.setattr(quick_check, "ensure_virtualenv", lambda: None)
    monkeypatch.setattr(quick_check, "bootstrap", lambda: 0)
    monkeypatch.setattr(quick_check.sys, "executable", "/tmp/.quick-check-venv/bin/python")
    monkeypatch.setattr(
        quick_check,
        "pytest_basetemp",
        lambda: Path("/tmp/repo/.quick-check-tmp/pytest-runs/run-1234"),
    )
    monkeypatch.setattr(
        quick_check,
        "run_sequence",
        lambda sequence: commands.extend(list(command) for command in sequence) or 0,
    )

    assert quick_check.main() == 0

    pytest_command = commands[-1]
    assert pytest_command[:7] == [
        "/tmp/.quick-check-venv/bin/python",
        "-m",
        "pytest",
        "-m",
        "not slow",
        "--basetemp",
        str(Path("/tmp/repo/.quick-check-tmp/pytest-runs/run-1234")),
    ]
    assert pytest_command[7:] == quick_check.PYTEST_TARGETS
