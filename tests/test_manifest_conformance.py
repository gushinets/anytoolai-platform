"""Harness safety regressions; real peer/TCP checks use manifest-conformance."""

from __future__ import annotations

import importlib.util
import io
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from tests.test_runner import load_runner_module


def load_harness():
    path = Path(__file__).resolve().parents[1] / "scripts/agent/manifest_conformance.py"
    spec = importlib.util.spec_from_file_location("manifest_harness_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "origin",
    [
        "https://127.0.0.1:8000",
        "http://localhost:8000",
        "http://example.test:8000",
        "http://127.0.0.1",
        "http://127.0.0.1:8000/",
        "http://user:secret@127.0.0.1:8000",
        "http://127.0.0.1:8000?token=secret",
        "http://127.0.0.1:8000#fragment",
        "http://127.0.0.1:bad",
        "http://127.0.0.1:65536",
        " http://127.0.0.1:8000",
        "http://127.0.0.1:80\n00",
    ],
)
def test_probe_rejects_non_loopback_or_non_origin_input(origin: str) -> None:
    with pytest.raises(ValueError):
        load_harness().loopback_origin(origin)


def test_allowlist_excludes_inherited_working_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    names = (
        "DATABASE_URL",
        "ANYTOOLAI_DATABASE_URL",
        "POSTGRES_PASSWORD",
        "OPENAI_API_KEY",
        "ANYTOOLAI_PORTAL_SERVICE_TOKEN",
        "ANY711_CONFORMANCE_TOKEN",
        "LBX_BASE_URL",
        "LBX_SERVER_PASSWORD",
        "SMTP_PASSWORD",
        "SENTRY_DSN",
        "PYTHONPATH",
        "VIRTUAL_ENV",
        "PYTHONHOME",
        "PYTEST_ADDOPTS",
        "HTTP_PROXY",
        "SSL_CERT_FILE",
    )
    for name in names:
        monkeypatch.setenv(name, "synthetic-poison")
    harness = load_harness()
    environment = harness.isolated_environment()
    assert not set(names).intersection(environment)
    assert environment["PATH"] == os.environ["PATH"]
    assert environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"


def test_consumer_requires_peer_environment_without_silent_fallback(tmp_path: Path) -> None:
    harness = load_harness()
    with pytest.raises(ValueError, match="required"):
        harness.peer_paths(None, None)
    with pytest.raises(ValueError, match="sync-api"):
        harness.peer_paths(tmp_path, tmp_path / "absent-python")


def test_peer_interpreter_path_preserves_virtualenv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = load_harness()
    for relative in (
        "apps/api/tests/support/settings.py",
        "apps/api/tests/support/kernel.py",
        "apps/api/app/integrations/kernel/client.py",
    ):
        file = tmp_path / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.touch()
    interpreter = tmp_path / ".venv/bin/python"
    interpreter.parent.mkdir(parents=True)
    interpreter.touch()
    original_resolve = Path.resolve

    def resolve(path, *args, **kwargs):
        # Model a venv symlink without requiring Windows symlink privileges.
        if path == interpreter:
            return original_resolve(Path(sys.executable))
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    root, selected = harness.peer_paths(tmp_path, interpreter)
    assert root == tmp_path
    assert selected == interpreter
    assert selected != interpreter.resolve()


def test_consumer_timeout_is_bounded_and_uses_only_allowlisted_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    harness = load_harness()
    captured = {}

    def expired(command, **kwargs):
        captured.update(kwargs)
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(harness.subprocess, "run", expired)
    monkeypatch.setenv("LBX_SERVER_PASSWORD", "synthetic-poison")
    with pytest.raises(subprocess.TimeoutExpired):
        harness.consumer(
            (tmp_path, Path(sys.executable)), "disposable", url="http://127.0.0.1:8000"
        )
    assert captured["timeout"] == harness.PROCESS_TIMEOUT_SECONDS
    assert "LBX_SERVER_PASSWORD" not in captured["env"]
    assert captured["env"]["ANY711_CONFORMANCE_TOKEN"] == "disposable"
    assert not Path(captured["env"]["TMPDIR"]).exists()


def test_failed_readiness_stops_only_owned_process_and_redacts_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = load_harness()
    token = "disposable-test-only-token"
    process = Mock()
    process.stdout = io.StringIO("")
    process.stdin = io.StringIO()
    process.poll.return_value = 1
    process.returncode = 1
    scratch = []

    def start(command, **kwargs):
        scratch.append(Path(kwargs["env"]["TMPDIR"]))
        kwargs["stderr"].write("failed with " + token)
        kwargs["stderr"].flush()
        return process

    monkeypatch.setattr(harness.subprocess, "Popen", start)
    with pytest.raises(RuntimeError) as error, harness.Producer("ordinary", token):
        pytest.fail("failed producer must not become ready")
    assert token not in str(error.value)
    assert "[REDACTED]" in str(error.value)
    process.terminate.assert_not_called()
    process.kill.assert_not_called()
    assert process.stdout.closed and process.stdin.closed
    assert scratch and not scratch[0].exists()


def test_consumer_failure_output_redacts_disposable_token(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    harness = load_harness()
    token = "disposable-test-only-token"
    monkeypatch.setattr(
        harness.subprocess,
        "run",
        Mock(return_value=subprocess.CompletedProcess([], 1, stdout=token, stderr=token)),
    )
    with pytest.raises(RuntimeError, match="isolated Portal process failed"):
        harness.consumer((tmp_path, Path(sys.executable)), token, url="http://127.0.0.1:8000")
    output = capsys.readouterr()
    assert token not in output.out + output.err
    assert output.out == output.err == "[REDACTED]"


def test_runner_dispatch_preserves_explicit_peer_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = load_runner_module()
    run = Mock(return_value=0)
    monkeypatch.setattr(runner, "run", run)
    monkeypatch.setattr(runner, "quick_check_python", lambda: "managed-python")
    assert (
        runner.main(
            ["manifest-conformance", "--portal-root", "peer", "--portal-python", "peer-python"]
        )
        == 0
    )
    run.assert_called_once_with(
        [
            "managed-python",
            "scripts/agent/manifest_conformance.py",
            "--portal-root",
            "peer",
            "--portal-python",
            "peer-python",
        ]
    )
