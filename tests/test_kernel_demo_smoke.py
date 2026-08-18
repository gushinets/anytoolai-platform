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


def test_run_one_case_reports_smoke001_when_guest_call_fails(monkeypatch) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(
        smoke, "_http_json_request", _sequenced_request([OSError("connection refused")])
    )

    error = smoke._run_one_case("http://127.0.0.1:8000", "scenario-1", {}, 5.0)
    assert error is not None and "SMOKE001" in error


def test_run_one_case_reports_smoke001_for_malformed_guest_response(monkeypatch) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(smoke, "_http_json_request", _sequenced_request([None]))

    error = smoke._run_one_case("http://127.0.0.1:8000", "scenario-1", {}, 5.0)
    assert error is not None and "SMOKE001" in error


def test_run_one_case_reports_smoke001_for_malformed_start_response(monkeypatch) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(
        smoke,
        "_http_json_request",
        _sequenced_request([{"guest_id": "guest-1"}, ["not", "a", "dict"]]),
    )

    error = smoke._run_one_case("http://127.0.0.1:8000", "scenario-1", {}, 5.0)
    assert error is not None and "SMOKE001" in error


def test_run_one_case_reports_smoke002_when_polling_call_fails(monkeypatch) -> None:
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

    error = smoke._run_one_case("http://127.0.0.1:8000", "scenario-1", {}, 5.0)
    assert error is not None and "SMOKE002" in error


def test_run_one_case_reports_smoke002_for_malformed_session_response(monkeypatch) -> None:
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

    error = smoke._run_one_case("http://127.0.0.1:8000", "scenario-1", {}, 5.0)
    assert error is not None and "SMOKE002" in error


def test_run_one_case_reports_smoke003_when_completed_without_artifact(monkeypatch) -> None:
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

    error = smoke._run_one_case("http://127.0.0.1:8000", "scenario-1", {}, 5.0)
    assert error is not None and "SMOKE003" in error


def test_run_one_case_succeeds_when_completed_with_artifact(monkeypatch) -> None:
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

    assert smoke._run_one_case("http://127.0.0.1:8000", "scenario-1", {}, 5.0) is None


def test_run_one_case_reports_smoke004_when_session_failed(monkeypatch) -> None:
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

    error = smoke._run_one_case("http://127.0.0.1:8000", "scenario-1", {}, 5.0)
    assert error is not None and "SMOKE004" in error


def test_run_one_case_reports_smoke005_on_timeout(monkeypatch) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(
        smoke,
        "_http_json_request",
        _sequenced_request([{"guest_id": "guest-1"}, {"scenario_session_id": "session-1"}]),
    )

    error = smoke._run_one_case("http://127.0.0.1:8000", "scenario-1", {}, 0.0)
    assert error is not None and "SMOKE005" in error


def test_run_reports_partial_pass_count_and_nonzero_exit(monkeypatch, capsys) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(
        smoke,
        "ATOM_SMOKE_CASES",
        (
            ("atom.one", "scenario-one", {}),
            ("atom.two", "scenario-two", {}),
        ),
    )
    monkeypatch.setattr(
        smoke,
        "_http_json_request",
        _sequenced_request(
            [
                {"guest_id": "guest-1"},
                {"scenario_session_id": "session-1"},
                {"status": "completed", "result_artifact_id": "artifact-1"},
                {"guest_id": "guest-2"},
                {"scenario_session_id": "session-2"},
                {"status": "failed", "error": "provider blew up"},
            ]
        ),
    )

    assert smoke.run("http://127.0.0.1:8000", timeout=5.0) == 1
    out, err = capsys.readouterr()
    assert "atom.one: scenario-one -> ok" in out
    assert "1/2 kernel_demo atoms passed" in out
    assert "atom.two: scenario-two -> failed" in err


def test_atom_smoke_cases_cover_the_required_eleven_action_types() -> None:
    smoke = load_smoke_module()
    assert smoke._atom_coverage_error(smoke.ATOM_SMOKE_CASES) is None
    assert len(smoke.ATOM_SMOKE_CASES) == 11


def test_required_action_types_are_derived_from_action_definitions_config() -> None:
    smoke = load_smoke_module()
    required = smoke._required_action_types()
    assert required == {action_type for action_type, _, _ in smoke.ATOM_SMOKE_CASES}
    assert "text.extract_structured_fields" in required


def test_atom_coverage_error_reports_missing_action_type() -> None:
    smoke = load_smoke_module()
    cases = (("atom.one", "scenario-one", {}),)

    error = smoke._atom_coverage_error(cases)

    assert error is not None and "SMOKE007" in error


def test_atom_coverage_error_reports_missing_config_directory_distinctly(monkeypatch) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(smoke, "ACTION_DEFINITIONS_ROOT", Path("/no/such/directory"))

    error = smoke._atom_coverage_error(smoke.ATOM_SMOKE_CASES)

    assert error is not None and "not found" in error


def test_run_never_skips_a_case_but_degrades_timeout_after_a_real_timeout(monkeypatch, capsys) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(
        smoke,
        "ATOM_SMOKE_CASES",
        (
            ("atom.one", "scenario-one", {}),
            ("atom.two", "scenario-two", {}),
            ("atom.three", "scenario-three", {}),
        ),
    )
    seen_timeouts = []

    def fake_run_one_case(api_url, scenario_id, scenario_input, timeout):
        seen_timeouts.append(timeout)
        if scenario_id == "scenario-two":
            return None
        return "SMOKE005: kernel_demo smoke check timed out after 30s"

    monkeypatch.setattr(smoke, "_run_one_case", fake_run_one_case)

    assert smoke.run("http://127.0.0.1:8000", timeout=30.0) == 1
    # every case still ran (no skipping) despite the first timing out
    assert seen_timeouts == [30.0, smoke.DEGRADED_TIMEOUT_SECONDS, smoke.DEGRADED_TIMEOUT_SECONDS]
    out, err = capsys.readouterr()
    assert "atom.two: scenario-two -> ok" in out
    assert "1/3 kernel_demo atoms passed" in out


def test_run_does_not_misread_an_embedded_smoke005_substring_as_a_timeout(monkeypatch) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(
        smoke,
        "ATOM_SMOKE_CASES",
        (
            ("atom.one", "scenario-one", {}),
            ("atom.two", "scenario-two", {}),
        ),
    )
    seen_timeouts = []

    def fake_run_one_case(api_url, scenario_id, scenario_input, timeout):
        seen_timeouts.append(timeout)
        if scenario_id == "scenario-one":
            return "SMOKE004: kernel_demo session s1 failed: {'error': 'echoed SMOKE005 text'}"
        return None

    monkeypatch.setattr(smoke, "_run_one_case", fake_run_one_case)

    smoke.run("http://127.0.0.1:8000", timeout=30.0)

    assert seen_timeouts == [30.0, 30.0]


def test_run_reports_full_pass_and_zero_exit(monkeypatch, capsys) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(
        smoke,
        "ATOM_SMOKE_CASES",
        (("atom.one", "scenario-one", {}),),
    )
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
    assert "1/1 kernel_demo atoms passed" in capsys.readouterr().out
