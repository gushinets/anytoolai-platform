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
    commands: list[list[str]] = []

    monkeypatch.setattr(runner, "quick_check", lambda: 0)
    monkeypatch.setattr(runner, "quick_check_python", lambda: quick_check_python)
    monkeypatch.setattr(runner.shutil, "which", lambda name: "/usr/local/bin/uv" if name == "uv" else None)
    monkeypatch.setattr(runner, "run", lambda command: commands.append(list(command)) or 0)

    exit_code = runner.full_check()

    assert exit_code == 0
    assert commands[0] == [
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
    assert commands[1] == [
        quick_check_python,
        "-m",
        "pytest",
        "tests/e2e",
        "packages/backend/product-platforms/freelancer-suite/tests",
    ]
