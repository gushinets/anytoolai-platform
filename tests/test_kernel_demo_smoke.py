from __future__ import annotations

import importlib.util
import urllib.error
from pathlib import Path


def load_smoke_module():
    module_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "agent" / "kernel_demo_smoke.py"
    )
    spec = importlib.util.spec_from_file_location("kernel_demo_smoke_module", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sequenced_request(responses):
    calls = iter(responses)

    def fake(*args, **kwargs):
        value = next(calls)
        if isinstance(value, Exception):
            raise value
        return value

    return fake


def test_run_reports_smoke001_when_guest_call_fails(monkeypatch, capsys) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(
        smoke, "_http_json_request", _sequenced_request([OSError("connection refused")])
    )

    assert smoke.run("http://127.0.0.1:8000", timeout=5.0) == 1
    assert "SMOKE001" in capsys.readouterr().err


def test_run_reports_smoke001_for_malformed_guest_response(monkeypatch, capsys) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(smoke, "_http_json_request", _sequenced_request([None]))

    assert smoke.run("http://127.0.0.1:8000", timeout=5.0) == 1
    assert "SMOKE001" in capsys.readouterr().err


def test_run_reports_smoke001_for_malformed_start_response(monkeypatch, capsys) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(
        smoke,
        "_http_json_request",
        _sequenced_request([{"guest_id": "guest-1"}, ["not", "a", "dict"]]),
    )

    assert smoke.run("http://127.0.0.1:8000", timeout=5.0) == 1
    assert "SMOKE001" in capsys.readouterr().err


def test_run_reports_smoke002_when_polling_call_fails(monkeypatch, capsys) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(
        smoke,
        "_http_json_request",
        _sequenced_request(
            [
                {"guest_id": "guest-1"},
                {"scenario_session_id": "session-1"},
                urllib.error.URLError("boom"),
            ]
        ),
    )

    assert smoke.run("http://127.0.0.1:8000", timeout=5.0) == 1
    assert "SMOKE002" in capsys.readouterr().err


def test_run_reports_smoke002_for_malformed_session_response(monkeypatch, capsys) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(
        smoke,
        "_http_json_request",
        _sequenced_request(
            [
                {"guest_id": "guest-1"},
                {"scenario_session_id": "session-1"},
                "not-a-dict",
            ]
        ),
    )

    assert smoke.run("http://127.0.0.1:8000", timeout=5.0) == 1
    assert "SMOKE002" in capsys.readouterr().err


def test_run_reports_smoke003_when_completed_without_artifact(monkeypatch, capsys) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(
        smoke,
        "_http_json_request",
        _sequenced_request(
            [
                {"guest_id": "guest-1"},
                {"scenario_session_id": "session-1"},
                {"status": "completed", "result_artifact_id": None},
            ]
        ),
    )

    assert smoke.run("http://127.0.0.1:8000", timeout=5.0) == 1
    assert "SMOKE003" in capsys.readouterr().err


def test_run_succeeds_when_completed_with_artifact(monkeypatch, capsys) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(
        smoke,
        "_http_json_request",
        _sequenced_request(
            [
                {"guest_id": "guest-1"},
                {"scenario_session_id": "session-1"},
                {"status": "completed", "result_artifact_id": "artifact-1"},
            ]
        ),
    )

    assert smoke.run("http://127.0.0.1:8000", timeout=5.0) == 0
    assert "session-1" in capsys.readouterr().out


def test_run_reports_smoke004_when_session_failed(monkeypatch, capsys) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(
        smoke,
        "_http_json_request",
        _sequenced_request(
            [
                {"guest_id": "guest-1"},
                {"scenario_session_id": "session-1"},
                {"status": "failed", "error": "provider blew up"},
            ]
        ),
    )

    assert smoke.run("http://127.0.0.1:8000", timeout=5.0) == 1
    assert "SMOKE004" in capsys.readouterr().err


def test_run_reports_smoke005_on_timeout(monkeypatch, capsys) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(
        smoke,
        "_http_json_request",
        _sequenced_request(
            [
                {"guest_id": "guest-1"},
                {"scenario_session_id": "session-1"},
            ]
        ),
    )

    assert smoke.run("http://127.0.0.1:8000", timeout=0.0) == 1
    assert "SMOKE005" in capsys.readouterr().err
