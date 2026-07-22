from __future__ import annotations

import importlib.util
from pathlib import Path


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
    project_one = tmp_path / "project-one"
    project_two = tmp_path / "project-two"
    commands: list[list[str]] = []

    monkeypatch.setattr(quick_check.sys, "executable", "/tmp/.quick-check-venv/bin/python")
    monkeypatch.setattr(quick_check, "EDITABLE_PROJECTS", [project_one, project_two])
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


def test_main_excludes_slow_tests_from_fast_pytest_path(monkeypatch) -> None:
    quick_check = load_quick_check_module()
    commands: list[list[str]] = []

    monkeypatch.setattr(quick_check, "ensure_virtualenv", lambda: None)
    monkeypatch.setattr(quick_check, "bootstrap", lambda: 0)
    monkeypatch.setattr(quick_check.sys, "executable", "/tmp/.quick-check-venv/bin/python")
    monkeypatch.setattr(
        quick_check,
        "run_sequence",
        lambda sequence: commands.extend(list(command) for command in sequence) or 0,
    )

    assert quick_check.main() == 0

    pytest_command = commands[-1]
    assert pytest_command[:5] == [
        "/tmp/.quick-check-venv/bin/python",
        "-m",
        "pytest",
        "-m",
        "not slow",
    ]
    assert pytest_command[5:] == quick_check.PYTEST_TARGETS
