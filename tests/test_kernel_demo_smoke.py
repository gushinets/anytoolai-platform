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


def test_run_one_case_skips_schema_ref_check_for_unknown_scenario(monkeypatch) -> None:
    """A scenario_id absent from _EXPECTED_SCHEMA_REF_BY_SCENARIO (e.g. a synthetic id used by
    other tests in this file) must not trigger the extra /v1/results/ fetch -- confirms the new
    schema_ref cross-check doesn't change behavior for scenarios with no known expectation."""
    smoke = load_smoke_module()
    monkeypatch.setattr(smoke, "_EXPECTED_SCHEMA_REF_BY_SCENARIO", {})
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


def test_run_one_case_succeeds_when_result_schema_ref_matches_expected(monkeypatch) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(
        smoke, "_EXPECTED_SCHEMA_REF_BY_SCENARIO", {"scenario-1": "kernel.schemas.expected_v1"}
    )
    monkeypatch.setattr(
        smoke,
        "_http_json_request",
        _sequenced_request(
            [
                {"guest_id": "guest-1"},
                {"scenario_session_id": "session-1"},
                {"status": "completed", "result_artifact_id": "artifact-1"},
                {"schema_ref": "kernel.schemas.expected_v1"},
            ]
        ),
    )

    result = smoke._run_one_case("http://127.0.0.1:8000", "scenario-1", {}, 5.0)

    assert result.error_code is None
    assert result.error_message is None


def test_run_one_case_reports_smoke009_when_result_schema_ref_mismatches(monkeypatch) -> None:
    """Catches a scenario wired to the wrong workflow/action (e.g. swapped scenario<->workflow
    labels in config): the produced artifact's schema_ref won't match what this scenario_id is
    declared to produce, even though the session completed with SOME artifact."""
    smoke = load_smoke_module()
    monkeypatch.setattr(
        smoke, "_EXPECTED_SCHEMA_REF_BY_SCENARIO", {"scenario-1": "kernel.schemas.expected_v1"}
    )
    monkeypatch.setattr(
        smoke,
        "_http_json_request",
        _sequenced_request(
            [
                {"guest_id": "guest-1"},
                {"scenario_session_id": "session-1"},
                {"status": "completed", "result_artifact_id": "artifact-1"},
                {"schema_ref": "kernel.schemas.wrong_v1"},
            ]
        ),
    )

    result = smoke._run_one_case("http://127.0.0.1:8000", "scenario-1", {}, 5.0)

    assert result.error_code == "SMOKE009"
    assert result.error_message is not None and "schema_ref" in result.error_message


def test_expected_schema_ref_by_scenario_covers_every_real_smoke_case() -> None:
    smoke = load_smoke_module()
    for action_type, scenario_id, _ in smoke.ATOM_SMOKE_CASES:
        assert scenario_id in smoke._EXPECTED_SCHEMA_REF_BY_SCENARIO, action_type


def test_expected_schema_ref_by_scenario_covers_every_composite_smoke_case() -> None:
    smoke = load_smoke_module()
    for workflow_id, scenario_id, _ in smoke.COMPOSITE_SMOKE_CASES:
        assert scenario_id in smoke._EXPECTED_SCHEMA_REF_BY_SCENARIO, workflow_id


def test_run_reports_smoke009_when_a_composite_scenario_produces_the_wrong_schema_ref(
    monkeypatch, capsys
) -> None:
    """Proves SMOKE009 (schema_ref cross-check) fires for a composite scenario wired to the
    wrong workflow, not just the 11 atom cases -- would previously report "ok" because
    composite scenario_ids had no entry in _EXPECTED_SCHEMA_REF_BY_SCENARIO."""
    smoke = load_smoke_module()
    monkeypatch.setattr(smoke, "ATOM_SMOKE_CASES", (("atom.one", "scenario-one", {}),))
    monkeypatch.setattr(
        smoke,
        "COMPOSITE_SMOKE_CASES",
        (("workflow.one", "kernel_demo.composite_analyze_and_clarify_smoke_v1", {}),),
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
                {"status": "completed", "result_artifact_id": "artifact-2"},
                {"schema_ref": "kernel.schemas.wrong_v1"},
            ]
        ),
    )

    assert smoke.run("http://127.0.0.1:8000", timeout=5.0) == 1
    out, err = capsys.readouterr()
    assert "1/1 kernel_demo atoms passed" in out
    assert "0/1 kernel_demo composite workflows passed" in out
    assert "SMOKE009" in err and "schema_ref" in err


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
    monkeypatch.setattr(smoke, "COMPOSITE_SMOKE_CASES", ())
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


def test_composite_smoke_cases_cover_the_required_composite_workflows() -> None:
    smoke = load_smoke_module()
    assert smoke._composite_coverage_error(smoke.COMPOSITE_SMOKE_CASES) is None
    assert len(smoke.COMPOSITE_SMOKE_CASES) == len(smoke._required_composite_workflow_ids())


def test_required_composite_workflow_ids_are_derived_from_workflows_config() -> None:
    smoke = load_smoke_module()
    required = smoke._required_composite_workflow_ids()
    assert required == {workflow_id for workflow_id, _, _ in smoke.COMPOSITE_SMOKE_CASES}
    assert "kernel_demo.composite_analyze_and_clarify_v1" in required


def test_required_composite_workflow_id_by_scenario_id_matches_real_config() -> None:
    smoke = load_smoke_module()
    binding = smoke._required_composite_workflow_id_by_scenario_id()
    assert binding == {
        scenario_id: workflow_id for workflow_id, scenario_id, _ in smoke.COMPOSITE_SMOKE_CASES
    }


def test_expected_schema_ref_by_scenario_matches_real_composite_config() -> None:
    smoke = load_smoke_module()
    expected = {
        "kernel_demo.composite_analyze_and_clarify_smoke_v1": (
            "kernel.schemas.generate_document_output_v1"
        ),
        "kernel_demo.composite_evaluate_match_smoke_v1": "kernel.schemas.score_multidim_output_v1",
        "kernel_demo.composite_shape_and_write_smoke_v1": "kernel.schemas.compose_reply_output_v1",
    }
    for scenario_id, schema_ref in expected.items():
        assert smoke._EXPECTED_SCHEMA_REF_BY_SCENARIO[scenario_id] == schema_ref


def test_composite_coverage_error_reports_missing_workflow() -> None:
    smoke = load_smoke_module()
    cases = (("workflow.one", "scenario-one", {}),)

    error = smoke._composite_coverage_error(cases)

    assert error is not None and "SMOKE010" in error


def test_composite_coverage_error_reports_missing_config_file_distinctly(monkeypatch) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(smoke, "WORKFLOWS_CONFIG_PATH", Path("/no/such/file.yaml"))

    error = smoke._composite_coverage_error(smoke.COMPOSITE_SMOKE_CASES)

    assert error is not None and "SMOKE010" in error and "not found" in error


def test_composite_coverage_error_reports_missing_scenarios_config_file_distinctly(
    monkeypatch,
) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(smoke, "SCENARIOS_CONFIG_PATH", Path("/no/such/scenarios.yaml"))

    error = smoke._composite_coverage_error(smoke.COMPOSITE_SMOKE_CASES)

    assert error is not None and "SMOKE010" in error and "not found" in error


def test_composite_coverage_error_reports_duplicate_scenario_id() -> None:
    """A reused scenario_id under a second workflow label silently drops the workflow whose real
    scenario got displaced -- each workflow_id and scenario_id can still individually be unique
    per-field, so this must be checked as its own condition, not inferred from the workflow_id
    duplicate check."""
    smoke = load_smoke_module()
    cases = (
        (
            "kernel_demo.composite_analyze_and_clarify_v1",
            "kernel_demo.composite_analyze_and_clarify_smoke_v1",
            {},
        ),
        (
            "kernel_demo.composite_evaluate_match_v1",
            "kernel_demo.composite_analyze_and_clarify_smoke_v1",
            {},
        ),
        (
            "kernel_demo.composite_shape_and_write_v1",
            "kernel_demo.composite_shape_and_write_smoke_v1",
            {},
        ),
    )

    error = smoke._composite_coverage_error(cases)

    assert error is not None and "SMOKE010" in error and "duplicate scenario_id" in error


def test_composite_coverage_error_reports_scenario_workflow_mismatch() -> None:
    """Two entries with scenario_ids swapped between workflow labels: workflow_id and
    scenario_id sets are each still exactly the required 3, so only a real config-bound binding
    check (not a duplicate check on either field) catches the mismatch."""
    smoke = load_smoke_module()
    cases = (
        (
            "kernel_demo.composite_analyze_and_clarify_v1",
            "kernel_demo.composite_analyze_and_clarify_smoke_v1",
            {},
        ),
        (
            "kernel_demo.composite_evaluate_match_v1",
            "kernel_demo.composite_shape_and_write_smoke_v1",
            {},
        ),
        (
            "kernel_demo.composite_shape_and_write_v1",
            "kernel_demo.composite_evaluate_match_smoke_v1",
            {},
        ),
    )

    error = smoke._composite_coverage_error(cases)

    assert error is not None and "SMOKE010" in error and "mismatch" in error


def test_composite_coverage_error_reports_malformed_workflows_config_cleanly(
    tmp_path, monkeypatch
) -> None:
    """A workflows.yaml that parses to something other than a mapping (e.g. a bare list) must
    produce a clean SMOKE010 message, not an unhandled AttributeError/YAMLError traceback."""
    smoke = load_smoke_module()
    bad_path = tmp_path / "workflows.yaml"
    bad_path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    monkeypatch.setattr(smoke, "WORKFLOWS_CONFIG_PATH", bad_path)

    error = smoke._composite_coverage_error(smoke.COMPOSITE_SMOKE_CASES)

    assert error is not None and "SMOKE010" in error


def test_composite_coverage_error_reports_missing_output_schema_ref(tmp_path, monkeypatch) -> None:
    """A required composite workflow with no (or non-string) output_schema_ref must fail
    SMOKE010 loudly -- previously it was silently dropped from
    _EXPECTED_SCHEMA_REF_BY_SCENARIO, so a composite scenario bound to the wrong workflow would
    pass SMOKE009's schema_ref check by omission instead of by actually matching."""
    smoke = load_smoke_module()
    bad_path = tmp_path / "workflows.yaml"
    bad_path.write_text(
        "workflows:\n"
        "  - workflow_id: kernel_demo.composite_analyze_and_clarify_v1\n"
        "  - workflow_id: kernel_demo.composite_evaluate_match_v1\n"
        "    output_schema_ref: kernel.schemas.score_multidim_output_v1\n"
        "  - workflow_id: kernel_demo.composite_shape_and_write_v1\n"
        "    output_schema_ref: kernel.schemas.compose_reply_output_v1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(smoke, "WORKFLOWS_CONFIG_PATH", bad_path)

    error = smoke._composite_coverage_error(smoke.COMPOSITE_SMOKE_CASES)

    assert (
        error is not None
        and "SMOKE010" in error
        and "kernel_demo.composite_analyze_and_clarify_v1" in error
    )


def test_composite_coverage_error_reports_partial_loss_not_just_empty() -> None:
    """A partial regression (2 of 3 composite entries survive) must be caught the same way full
    emptiness is -- this is the exact gap a bare `len(cases) == 0` check would miss."""
    smoke = load_smoke_module()
    partial_cases = smoke.COMPOSITE_SMOKE_CASES[:-1]

    error = smoke._composite_coverage_error(partial_cases)

    assert error is not None and "SMOKE010" in error


def test_main_fails_on_composite_coverage_mismatch(monkeypatch, capsys) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(smoke, "COMPOSITE_SMOKE_CASES", smoke.COMPOSITE_SMOKE_CASES[:-1])
    monkeypatch.setattr(sys, "argv", ["kernel_demo_smoke.py", "http://127.0.0.1:8000"])

    assert smoke.main() == 1
    assert "SMOKE010" in capsys.readouterr().err


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
    monkeypatch.setattr(smoke, "COMPOSITE_SMOKE_CASES", ())
    seen_timeouts = []

    def fake_run_one_case(api_url, scenario_id, scenario_input, timeout):
        seen_timeouts.append(timeout)
        # only case one times out; case two succeeds, which must reset the budget for case three
        return _fake_case_result(smoke, scenario_id, timed_out=(scenario_id == "scenario-one"))

    monkeypatch.setattr(smoke, "_run_one_case", fake_run_one_case)

    smoke.run("http://127.0.0.1:8000", timeout=30.0)

    assert seen_timeouts == [30.0, smoke.DEGRADED_TIMEOUT_SECONDS, 30.0]


def test_run_chains_degraded_timeout_from_atom_batch_into_composite_batch(monkeypatch) -> None:
    """A worker outage detected during the atom batch must keep the composite batch cheap too --
    case_timeout carries over between batches instead of resetting to the full budget for the
    composite batch."""
    smoke = load_smoke_module()
    monkeypatch.setattr(smoke, "ATOM_SMOKE_CASES", (("atom.one", "scenario-one", {}),))
    monkeypatch.setattr(
        smoke, "COMPOSITE_SMOKE_CASES", (("workflow.one", "scenario-composite", {}),)
    )
    seen_timeouts = []

    def fake_run_one_case(api_url, scenario_id, scenario_input, timeout):
        seen_timeouts.append(timeout)
        return _fake_case_result(smoke, scenario_id, timed_out=(scenario_id == "scenario-one"))

    monkeypatch.setattr(smoke, "_run_one_case", fake_run_one_case)

    smoke.run("http://127.0.0.1:8000", timeout=30.0)

    assert seen_timeouts == [30.0, smoke.DEGRADED_TIMEOUT_SECONDS]


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
    monkeypatch.setattr(smoke, "COMPOSITE_SMOKE_CASES", ())
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
        "COMPOSITE_SMOKE_CASES",
        (("workflow.one", "scenario-composite", {}),),
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
                {"status": "completed", "result_artifact_id": "artifact-2"},
            ]
        ),
    )

    assert smoke.run("http://127.0.0.1:8000", timeout=5.0) == 0
    out = capsys.readouterr().out
    assert "1/1 kernel_demo atoms passed" in out
    assert "atom.one: scenario-one -> ok (session session-1)" in out
    assert "1/1 kernel_demo composite workflows passed" in out


def test_run_fails_instead_of_vacuous_success_on_empty_composite_case_list(
    monkeypatch, capsys
) -> None:
    """Mirrors test_run_fails_instead_of_vacuous_success_on_empty_case_list for the composite
    side -- an empty COMPOSITE_SMOKE_CASES must fail the run even when every atom case passes,
    not silently report 0/0 composite workflows as a vacuous success (exactly the class of
    regression a merge accidentally emptying COMPOSITE_SMOKE_CASES would otherwise hide)."""
    smoke = load_smoke_module()
    monkeypatch.setattr(
        smoke,
        "ATOM_SMOKE_CASES",
        (("atom.one", "scenario-one", {}),),
    )
    monkeypatch.setattr(smoke, "COMPOSITE_SMOKE_CASES", ())
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

    assert smoke.run("http://127.0.0.1:8000", timeout=5.0) == 1
    out, err = capsys.readouterr()
    assert "1/1 kernel_demo atoms passed" in out
    assert "SMOKE010" in err and "COMPOSITE_SMOKE_CASES" in err


def test_run_reports_smoke001_with_no_session_id_available(monkeypatch, capsys) -> None:
    """SMOKE001 (guest/start call itself failed) is the only case where session_id is None --
    exercised through run() itself, not just _run_one_case() directly, so a future change to
    run()'s per-case print formatting that mis-handles a None session_id is caught here."""
    smoke = load_smoke_module()
    monkeypatch.setattr(smoke, "ATOM_SMOKE_CASES", (("atom.one", "scenario-one", {}),))
    monkeypatch.setattr(smoke, "COMPOSITE_SMOKE_CASES", ())
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


def test_run_fails_when_atoms_pass_but_a_composite_workflow_fails(monkeypatch, capsys) -> None:
    smoke = load_smoke_module()
    monkeypatch.setattr(
        smoke,
        "ATOM_SMOKE_CASES",
        (("atom.one", "scenario-one", {}),),
    )
    monkeypatch.setattr(
        smoke,
        "COMPOSITE_SMOKE_CASES",
        (("workflow.one", "scenario-composite", {}),),
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
    assert "1/1 kernel_demo atoms passed" in out
    assert "0/1 kernel_demo composite workflows passed" in out
    assert "workflow.one: scenario-composite -> failed" in err
