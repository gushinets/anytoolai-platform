from __future__ import annotations

import importlib.util
from pathlib import Path


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
