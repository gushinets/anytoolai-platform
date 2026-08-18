from __future__ import annotations

import importlib.util
import sys
import urllib.error
from pathlib import Path

import pytest


def load_smoke_module():
    module_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "agent" / "kernel_demo_smoke.py"
    )
    spec = importlib.util.spec_from_file_location("kernel_demo_smoke_module", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # kernel_demo_smoke.py defines a @dataclass under `from __future__ import annotations`,
    # which needs to resolve its string annotations via sys.modules[cls.__module__] at class
    # definition time -- without registering the module here first, that lookup returns None
    # and dataclass field resolution raises AttributeError.
    sys.modules[spec.name] = module
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


SMOKE_CODE_CASES = (
    pytest.param([OSError("connection refused")], "SMOKE001", id="guest_call_fails"),
    pytest.param([None], "SMOKE001", id="malformed_guest_response"),
    pytest.param(
        [{"guest_id": "guest-1"}, ["not", "a", "dict"]],
        "SMOKE001",
        id="malformed_start_response",
    ),
    pytest.param(
        [
            {"guest_id": "guest-1"},
            {"scenario_session_id": "session-1"},
            urllib.error.URLError("boom"),
        ],
        "SMOKE002",
        id="polling_call_fails",
    ),
    pytest.param(
        [{"guest_id": "guest-1"}, {"scenario_session_id": "session-1"}, "not-a-dict"],
        "SMOKE002",
        id="malformed_session_response",
    ),
    pytest.param(
        [
            {"guest_id": "guest-1"},
            {"scenario_session_id": "session-1"},
            {"status": "completed", "result_artifact_id": None},
        ],
        "SMOKE003",
        id="completed_without_artifact",
    ),
    pytest.param(
        [
            {"guest_id": "guest-1"},
            {"scenario_session_id": "session-1"},
            {"status": "failed", "error": "provider blew up"},
        ],
        "SMOKE004",
        id="session_failed",
    ),
)


@pytest.mark.parametrize("responses, expected_code", SMOKE_CODE_CASES)
def test_run_one_case_reports_expected_error_code(monkeypatch, responses, expected_code) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(smoke, "_http_json_request", _sequenced_request(responses))

    result = smoke._run_one_case("http://127.0.0.1:8000", "scenario-1", {}, 5.0)

    assert result.error_code == expected_code
    assert result.error_message is not None and expected_code in result.error_message


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

    result = smoke._run_one_case("http://127.0.0.1:8000", "scenario-1", {}, 5.0)

    assert result.error_code is None
    assert result.error_message is None
    assert result.session_id == "session-1"


def test_run_one_case_reports_smoke005_on_timeout(monkeypatch) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(
        smoke,
        "_http_json_request",
        _sequenced_request([{"guest_id": "guest-1"}, {"scenario_session_id": "session-1"}]),
    )

    # A real generated result, not a hand-written stub -- catches a future reword of the error
    # text or code silently breaking run()'s timeout-degrade detection.
    result = smoke._run_one_case("http://127.0.0.1:8000", "scenario-1", {}, 0.0)

    assert result.error_code == smoke._TIMEOUT_ERROR_CODE
    assert result.error_message is not None and "SMOKE005" in result.error_message
    assert result.session_id == "session-1"


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
    assert "atom.one: scenario-one -> ok (session session-1)" in out
    assert "1/2 kernel_demo atoms passed" in out
    assert "atom.two: scenario-two -> failed" in err


def test_atom_smoke_cases_cover_the_required_eleven_action_types() -> None:
    smoke = load_smoke_module()
    assert smoke._atom_coverage_error(smoke.ATOM_SMOKE_CASES) is None
    assert len(smoke.ATOM_SMOKE_CASES) == len(smoke._required_action_types())


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


def test_run_fails_instead_of_vacuous_success_on_empty_case_list(monkeypatch, capsys) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(smoke, "ATOM_SMOKE_CASES", ())

    assert smoke.run("http://127.0.0.1:8000", timeout=5.0) == 1
    assert "SMOKE007" in capsys.readouterr().err


def _fake_case_result(smoke, scenario_id, *, timed_out):
    if timed_out:
        return smoke.CaseResult(
            session_id=f"s-{scenario_id}",
            error_code=smoke._TIMEOUT_ERROR_CODE,
            error_message=f"{smoke._TIMEOUT_ERROR_CODE}: kernel_demo smoke check timed out",
        )
    return smoke.CaseResult(session_id=f"s-{scenario_id}", error_code=None, error_message=None)


def test_run_never_skips_a_case_even_after_a_real_timeout(monkeypatch, capsys) -> None:
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

    def fake_run_one_case(api_url, scenario_id, scenario_input, timeout):
        return _fake_case_result(smoke, scenario_id, timed_out=(scenario_id == "scenario-one"))

    monkeypatch.setattr(smoke, "_run_one_case", fake_run_one_case)

    assert smoke.run("http://127.0.0.1:8000", timeout=30.0) == 1
    out, _ = capsys.readouterr()
    assert "atom.two: scenario-two -> ok" in out
    assert "atom.three: scenario-three -> ok" in out
    assert "2/3 kernel_demo atoms passed" in out


def test_run_degrades_timeout_after_a_timeout_but_not_permanently(monkeypatch) -> None:
    """A single slow-but-legitimate atom must not permanently cap every atom that follows it
    (round-2 follow-up review bug): the degrade only applies to the case immediately after a
    timeout, and any non-timeout outcome (success here) restores the full budget."""
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
        # only case one times out; case two succeeds, which must reset the budget for case three
        return _fake_case_result(smoke, scenario_id, timed_out=(scenario_id == "scenario-one"))

    monkeypatch.setattr(smoke, "_run_one_case", fake_run_one_case)

    smoke.run("http://127.0.0.1:8000", timeout=30.0)

    assert seen_timeouts == [30.0, smoke.DEGRADED_TIMEOUT_SECONDS, 30.0]


def test_run_timeout_degrade_is_driven_by_error_code_not_message_text(monkeypatch) -> None:
    """The degrade decision reads the typed error_code field, not the human-readable message
    -- a SMOKE004 failure whose echoed body happens to contain the literal text "SMOKE005"
    must not be misread as a timeout."""
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
            return smoke.CaseResult(
                session_id="s1",
                error_code="SMOKE004",
                error_message=(
                    "SMOKE004: kernel_demo session s1 failed: "
                    f"{{'error': 'echoed {smoke._TIMEOUT_ERROR_CODE} text'}}"
                ),
            )
        return smoke.CaseResult(session_id="s2", error_code=None, error_message=None)

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
    out = capsys.readouterr().out
    assert "1/1 kernel_demo atoms passed" in out
    assert "atom.one: scenario-one -> ok (session session-1)" in out


def test_run_reports_smoke001_with_no_session_id_available(monkeypatch, capsys) -> None:
    """SMOKE001 (guest/start call itself failed) is the only case where session_id is None --
    exercised through run() itself, not just _run_one_case() directly, so a future change to
    run()'s per-case print formatting that mis-handles a None session_id is caught here."""
    smoke = load_smoke_module()
    monkeypatch.setattr(smoke, "ATOM_SMOKE_CASES", (("atom.one", "scenario-one", {}),))
    monkeypatch.setattr(
        smoke, "_http_json_request", _sequenced_request([OSError("connection refused")])
    )

    assert smoke.run("http://127.0.0.1:8000", timeout=5.0) == 1
    out, err = capsys.readouterr()
    assert "0/1 kernel_demo atoms passed" in out
    assert "atom.one: scenario-one -> failed (SMOKE001" in err


def test_atom_matrix_load_error_reported_by_main_before_argparse(monkeypatch, capsys) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(smoke, "_ATOM_MATRIX_LOAD_ERROR", "SMOKE008: could not load fixture")

    # main() checks _ATOM_MATRIX_LOAD_ERROR and returns before ever calling
    # parser.parse_args(), so no api_url argv needs to be supplied here.
    assert smoke.main() == 1
    assert "SMOKE008" in capsys.readouterr().err
