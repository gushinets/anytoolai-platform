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
    expected_python = new_venv / "bin" / "python"
    script_path = Path(quick_check.__file__).resolve()

    new_venv.mkdir(parents=True)
    legacy_venv.mkdir(parents=True)
    expected_python.parent.mkdir(parents=True)
    expected_python.write_text("", encoding="utf-8")

    monkeypatch.setattr(quick_check, "ROOT", repo_root)
    monkeypatch.setattr(quick_check, "VENV_DIR", new_venv)
    monkeypatch.setattr(quick_check, "LEGACY_VENV_DIR", legacy_venv)
    monkeypatch.setattr(quick_check.sys, "prefix", str(legacy_venv))
    monkeypatch.setattr(quick_check.sys, "executable", str(legacy_venv / "bin" / "python"))
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
    expected_python = new_venv / "bin" / "python"

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
