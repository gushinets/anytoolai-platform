from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tests.module_loading import load_cached_module
from tests.test_kernel_demo_smoke import _fake_case_result, assert_main_fails_on_coverage_mismatch


def load_atoms_proof_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "agent" / "atoms_proof.py"
    return load_cached_module("atoms_proof_module", module_path)


def test_load_atoms_proof_module_returns_the_same_cached_module_on_repeat_calls() -> None:
    assert load_atoms_proof_module() is load_atoms_proof_module()


EXPECTED_EVENT_TYPES = frozenset(
    {
        "scenario.started",
        "workflow.started",
        "action.started",
        "provider.request_started",
        "provider.request_succeeded",
        "artifact.created",
        "action.succeeded",
        "workflow.succeeded",
        "scenario.checkpoint_reached",
        "scenario.completed",
    }
)


def _all_expected_events(*, action_run_count: int) -> list[dict]:
    events = [{"event_type": event_type} for event_type in EXPECTED_EVENT_TYPES]
    events += [{"event_type": "action.started"} for _ in range(action_run_count - 1)]
    events += [{"event_type": "action.succeeded"} for _ in range(action_run_count - 1)]
    return events


def _one_step_row(**overrides) -> dict:
    row = {
        "id": "run-1",
        "step_id": "extract",
        "action_type": "text.extract_structured_fields",
        "action_config_id": "kernel_demo.extract_structured_fields_v1",
        "output_artifact_id": "artifact-step-1",
    }
    row.update(overrides)
    return row


def test_classify_ledger_passes_with_full_correlation() -> None:
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="text.extract_structured_fields",
        scenario_id="scenario-1",
        kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[{"action_run_id": "run-1"}],
        artifacts=[{"id": "artifact-step-1"}, {"id": "artifact-result"}],
        events=_all_expected_events(action_run_count=1),
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "pass"
    assert case.error_code is None
    assert case.job_id == "job-1"
    assert case.session_id == "session-1"
    assert case.steps == (
        module.StepEvidence(
            step_id="extract",
            action_type="text.extract_structured_fields",
            action_config_id="kernel_demo.extract_structured_fields_v1",
        ),
    )


def test_classify_ledger_reports_proof001_when_no_job_row() -> None:
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1", job_row=None,
        action_runs=[], provider_calls=[], artifacts=[], events=[],
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF001"
    assert case.job_id is None


def test_classify_ledger_reports_proof002_when_no_action_runs() -> None:
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[], provider_calls=[], artifacts=[], events=[],
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF002"
    assert case.job_id == "job-1"


def test_classify_ledger_reports_proof003_when_provider_call_count_is_wrong() -> None:
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[],
        artifacts=[{"id": "artifact-step-1"}, {"id": "artifact-result"}],
        events=_all_expected_events(action_run_count=1),
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF003"


def test_classify_ledger_reports_proof003_when_provider_call_is_duplicated() -> None:
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[{"action_run_id": "run-1"}, {"action_run_id": "run-1"}],
        artifacts=[{"id": "artifact-step-1"}, {"id": "artifact-result"}],
        events=_all_expected_events(action_run_count=1),
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF003"


def test_classify_ledger_reports_proof004_when_step_artifact_missing() -> None:
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[{"action_run_id": "run-1"}],
        artifacts=[{"id": "artifact-result"}],
        events=_all_expected_events(action_run_count=1),
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF004"


def test_classify_ledger_reports_proof004_when_result_artifact_missing() -> None:
    """The job's result_artifact_id must be its own artifacts_table row, separate from any
    step's own output_artifact_id (see the module docstring on _classify_ledger)."""
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[{"action_run_id": "run-1"}],
        artifacts=[{"id": "artifact-step-1"}],
        events=_all_expected_events(action_run_count=1),
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF004"
    assert "result_artifact_id" in case.error_message


def test_classify_ledger_reports_proof005_when_event_type_missing() -> None:
    module = load_atoms_proof_module()

    events = [
        event
        for event in _all_expected_events(action_run_count=1)
        if event["event_type"] != "scenario.completed"
    ]
    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[{"action_run_id": "run-1"}],
        artifacts=[{"id": "artifact-step-1"}, {"id": "artifact-result"}],
        events=events,
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF005"
    assert "scenario.completed" in case.error_message


def test_classify_ledger_reports_proof006_when_action_event_count_is_wrong() -> None:
    module = load_atoms_proof_module()

    events = list(EXPECTED_EVENT_TYPES)
    events = [{"event_type": event_type} for event_type in events]
    # Only one action.started/action.succeeded pair total is already present via
    # EXPECTED_EVENT_TYPES; two action_runs requires two of each -- deliberately not adding the
    # second pair here to trigger PROOF006.
    case = module._classify_ledger(
        label="workflow.one", scenario_id="scenario-composite", kind="composite",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row(), _one_step_row(id="run-2", step_id="detect_issues")],
        provider_calls=[{"action_run_id": "run-1"}, {"action_run_id": "run-2"}],
        artifacts=[
            {"id": "artifact-step-1"},
            {"id": "artifact-step-2"},
            {"id": "artifact-result"},
        ],
        events=events,
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF006"


def test_classify_ledger_passes_for_multi_step_composite_workflow() -> None:
    module = load_atoms_proof_module()

    action_runs = [
        _one_step_row(),
        _one_step_row(id="run-2", step_id="detect_issues", output_artifact_id="artifact-step-2"),
    ]
    case = module._classify_ledger(
        label="workflow.one", scenario_id="scenario-composite", kind="composite",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=action_runs,
        provider_calls=[{"action_run_id": "run-1"}, {"action_run_id": "run-2"}],
        artifacts=[
            {"id": "artifact-step-1"},
            {"id": "artifact-step-2"},
            {"id": "artifact-result"},
        ],
        events=_all_expected_events(action_run_count=2),
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "pass"
    assert len(case.steps) == 2


def test_run_case_with_ledger_check_reports_http_failure_without_touching_db(monkeypatch) -> None:
    """A case that fails during the HTTP/poll phase must short-circuit before any DB
    connection is attempted -- exercised by never providing a real engine here."""
    module = load_atoms_proof_module()
    monkeypatch.setattr(
        module.smoke,
        "_run_one_case",
        lambda api_url, scenario_id, scenario_input, timeout: module.smoke.CaseResult(
            session_id=None, error_code="SMOKE001", error_message="SMOKE001: boom"
        ),
    )

    case = module._run_case_with_ledger_check(
        "http://127.0.0.1:8000", engine=None, kind="atom", label="atom.one",
        scenario_id="scenario-1", scenario_input={}, timeout=5.0,
    )

    assert case.status == "fail"
    assert case.error_code == "SMOKE001"


def test_check_ledger_reports_proof000_without_leaking_raw_exception_text() -> None:
    """Fourteenth-round finding: database_url isn't guaranteed to be the fixed dev-only default
    (ANYTOOLAI_POSTGRES_PASSWORD is overridable), so a driver exception's free-form message must
    not flow into the persisted evidence report -- only PROOF000 plus the exception class name,
    which is still enough to tell e.g. an auth/connection failure from a bad-query error."""
    module = load_atoms_proof_module()

    class _FailingEngine:
        def connect(self):
            raise module.sa.exc.SQLAlchemyError("connection string had secret-looking-detail")

    case = module._check_ledger(
        _FailingEngine(), label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF000"
    assert "SQLAlchemyError" in case.error_message
    assert "secret-looking-detail" not in case.error_message


def test_write_evidence_report_is_privacy_safe_and_shaped_correctly(tmp_path) -> None:
    module = load_atoms_proof_module()

    passing = module.EvidenceCase(
        label="text.extract_structured_fields", scenario_id="scenario-1", kind="atom",
        status="pass", session_id="session-1", job_id="job-1", error_code=None,
        error_message=None,
        steps=(
            module.StepEvidence(
                step_id="extract", action_type="text.extract_structured_fields",
                action_config_id="kernel_demo.extract_structured_fields_v1",
            ),
        ),
    )
    failing = module.EvidenceCase(
        label="workflow.one", scenario_id="scenario-composite", kind="composite",
        status="fail", session_id="session-2", job_id=None, error_code="PROOF005",
        error_message="PROOF005: missing event types ['scenario.completed']", steps=(),
    )

    report_path = module.write_evidence_report([passing, failing], 1, output_root=tmp_path)

    assert report_path.parent == tmp_path
    assert report_path.name.startswith("evidence-") and report_path.name.endswith(".json")

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["atoms_passed"] == 1
    assert payload["atoms_total"] == 1
    assert payload["composite_passed"] == 0
    assert payload["composite_total"] == 1
    assert payload["all_passed"] is False
    assert len(payload["cases"]) == 2
    assert payload["cases"][0]["steps"][0]["action_config_id"] == (
        "kernel_demo.extract_structured_fields_v1"
    )

    # Privacy-safe: only ids/labels/booleans/strings from our own error messages -- no fixture
    # payload bodies, no prompts, no raw provider/user content.
    serialized = json.dumps(payload)
    assert "source_text" not in serialized
    assert "prompt" not in serialized


def test_write_evidence_report_all_passed_reflects_exit_code_not_vacuous_case_count(
    tmp_path,
) -> None:
    """Fifth code review pass finding: all_passed must come from run()'s own exit_code, not be
    re-derived as len(passed) == len(cases) -- an empty cases list (PROOF008/PROOF009's
    empty-case guards) would otherwise read as vacuous 0-of-0 "success" even on a non-zero
    exit_code."""
    module = load_atoms_proof_module()

    report_path = module.write_evidence_report([], 1, output_root=tmp_path)

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["all_passed"] is False


def test_write_evidence_report_rejects_exit_code_zero_with_a_failing_case(tmp_path) -> None:
    """Twelfth code review pass finding: nothing previously caught a caller passing exit_code=0
    alongside a `cases` list that actually contains a failure, which would make the payload's own
    "all_passed": true contradict its own per-case detail in the same report."""
    module = load_atoms_proof_module()
    failing = module.EvidenceCase(
        label="atom.one", scenario_id="scenario-1", kind="atom", status="fail",
        session_id="session-1", job_id=None, error_code="PROOF001",
        error_message="PROOF001: boom", steps=(),
    )

    with pytest.raises(ValueError, match="exit_code=0"):
        module.write_evidence_report([failing], 0, output_root=tmp_path)


def test_build_engine_coerces_bare_postgresql_scheme_to_psycopg() -> None:
    module = load_atoms_proof_module()

    engine = module._build_engine("postgresql://user:pass@127.0.0.1:5432/anytoolai")

    assert engine.url.drivername == "postgresql+psycopg"


def test_build_engine_leaves_an_explicit_driver_untouched() -> None:
    module = load_atoms_proof_module()

    engine = module._build_engine("postgresql+psycopg://user:pass@127.0.0.1:5432/anytoolai")

    assert engine.url.drivername == "postgresql+psycopg"


def test_module_exposes_eleven_atom_and_three_composite_cases() -> None:
    module = load_atoms_proof_module()

    assert module._MODULE_LOAD_ERROR is None
    assert len(module.ATOM_SMOKE_CASES) == 11
    assert len(module.COMPOSITE_SMOKE_CASES) == 3


def test_loading_does_not_reload_kernel_demo_smoke_a_second_time() -> None:
    """Second code review pass regression coverage: test_atom_runtime_matrix.py's own
    module-level `_SMOKE_MODULE = load_smoke_module()` must resolve to the same object this
    module already loaded as `smoke`, not a second, independently re-parsed module."""
    module = load_atoms_proof_module()

    assert module._atom_runtime_matrix_module._SMOKE_MODULE is module.smoke


_TEST_DATABASE_URL_ENV = "TEST_ATOMS_PROOF_DATABASE_URL"
_TEST_MAIN_ARGV = [
    "atoms_proof.py", "http://127.0.0.1:8000", "--database-url-env", _TEST_DATABASE_URL_ENV,
]


def test_main_fails_on_composite_coverage_mismatch_before_running_any_case(
    monkeypatch, capsys
) -> None:
    module = load_atoms_proof_module()
    monkeypatch.setenv(_TEST_DATABASE_URL_ENV, "postgresql://u:p@127.0.0.1:5432/db")
    assert_main_fails_on_coverage_mismatch(
        module, monkeypatch=monkeypatch, capsys=capsys,
        mismatched_attr="COMPOSITE_SMOKE_CASES",
        argv=_TEST_MAIN_ARGV,
        expected_error_code="SMOKE010",
    )


def test_main_fails_on_atom_coverage_mismatch_before_running_any_case(monkeypatch, capsys) -> None:
    """Fifth code review pass finding: only the composite half of main()'s coverage gate had
    regression coverage; the atom half (checked first, via the shared
    smoke._coverage_gate_error()) had none."""
    module = load_atoms_proof_module()
    monkeypatch.setenv(_TEST_DATABASE_URL_ENV, "postgresql://u:p@127.0.0.1:5432/db")
    assert_main_fails_on_coverage_mismatch(
        module, monkeypatch=monkeypatch, capsys=capsys,
        mismatched_attr="ATOM_SMOKE_CASES",
        argv=_TEST_MAIN_ARGV,
        expected_error_code="SMOKE007",
    )


def test_main_fails_when_database_url_env_is_unset(monkeypatch, capsys) -> None:
    """Fourteenth code review pass finding: database_url now flows through an env var named by
    --database-url-env, not argv, so a caller that names an unset/empty env var must fail
    clearly instead of e.g. crashing on a None database_url later."""
    module = load_atoms_proof_module()
    monkeypatch.delenv(_TEST_DATABASE_URL_ENV, raising=False)
    monkeypatch.setattr(
        module,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("run() must not be called")),
    )
    monkeypatch.setattr(sys, "argv", _TEST_MAIN_ARGV)

    assert module.main() == 2
    assert "PROOF010" in capsys.readouterr().err


def test_main_writes_evidence_report_on_coverage_gate_failure(monkeypatch, capsys) -> None:
    """Eleventh code review pass finding: persisting an evidence report is this script's whole
    point (module docstring), and an incomplete-coverage failure is one of the ticket's required
    non-zero-exit failure categories -- main() must not exit on that path without writing one."""
    module = load_atoms_proof_module()
    monkeypatch.setattr(module, "ATOM_SMOKE_CASES", module.ATOM_SMOKE_CASES[:-1])
    calls = []
    monkeypatch.setattr(
        module,
        "write_evidence_report",
        lambda cases, exit_code, **kwargs: calls.append((cases, exit_code))
        or Path("evidence-fake.json"),
    )
    monkeypatch.setenv(_TEST_DATABASE_URL_ENV, "postgresql://u:p@127.0.0.1:5432/db")
    monkeypatch.setattr(sys, "argv", _TEST_MAIN_ARGV)

    assert module.main() == 1

    assert calls == [([], 1)]
    assert "Evidence report:" in capsys.readouterr().out


def _passing_check_ledger(module):
    def fake(engine, *, label, scenario_id, kind, scenario_session_id):
        return module.EvidenceCase(
            label=label, scenario_id=scenario_id, kind=kind, status="pass",
            session_id=scenario_session_id, job_id="job-1", error_code=None, error_message=None,
            steps=(),
        )

    return fake


def test_run_chains_degraded_timeout_from_atom_batch_into_composite_batch(monkeypatch) -> None:
    """A worker outage detected during the atom batch must keep the composite batch cheap too --
    regression coverage for the second code review pass finding that this fix shipped with no
    test."""
    module = load_atoms_proof_module()
    monkeypatch.setattr(module, "ATOM_SMOKE_CASES", (("atom.one", "scenario-one", {}),))
    monkeypatch.setattr(
        module, "COMPOSITE_SMOKE_CASES", (("workflow.one", "scenario-composite", {}),)
    )
    monkeypatch.setattr(module, "_check_ledger", _passing_check_ledger(module))
    seen_timeouts = []

    def fake_run_one_case(api_url, scenario_id, scenario_input, timeout):
        seen_timeouts.append(timeout)
        return _fake_case_result(
            module.smoke, scenario_id, timed_out=(scenario_id == "scenario-one")
        )

    monkeypatch.setattr(module.smoke, "_run_one_case", fake_run_one_case)

    module.run("http://127.0.0.1:8000", "postgresql://u:p@127.0.0.1:5432/db", timeout=30.0)

    assert seen_timeouts == [30.0, module.smoke.DEGRADED_TIMEOUT_SECONDS]


def test_run_case_group_derives_passed_count_from_results(monkeypatch, capsys) -> None:
    """Eleventh code review pass finding: _run_case_group()'s `passed` count is derived from
    `results` after the loop, not tracked as an independently incremented counter -- exercised
    here with a mixed pass/fail atom batch to prove the derivation is still correct."""
    module = load_atoms_proof_module()
    monkeypatch.setattr(
        module,
        "ATOM_SMOKE_CASES",
        (("atom.one", "scenario-one", {}), ("atom.two", "scenario-two", {})),
    )
    monkeypatch.setattr(module, "COMPOSITE_SMOKE_CASES", ())
    monkeypatch.setattr(module, "_check_ledger", _passing_check_ledger(module))
    monkeypatch.setattr(
        module.smoke,
        "_run_one_case",
        lambda api_url, scenario_id, scenario_input, timeout: (
            module.smoke.CaseResult(session_id="s-one", error_code=None, error_message=None)
            if scenario_id == "scenario-one"
            else module.smoke.CaseResult(
                session_id="s-two", error_code="SMOKE004", error_message="SMOKE004: failed"
            )
        ),
    )

    cases, exit_code = module.run(
        "http://127.0.0.1:8000", "postgresql://u:p@127.0.0.1:5432/db", timeout=5.0
    )

    assert exit_code == 1
    assert len(cases) == 2
    assert "1/2 kernel_demo atoms passed" in capsys.readouterr().out


def test_run_fails_instead_of_vacuous_success_on_empty_atom_case_list(monkeypatch, capsys) -> None:
    module = load_atoms_proof_module()
    monkeypatch.setattr(module, "ATOM_SMOKE_CASES", ())

    cases, exit_code = module.run(
        "http://127.0.0.1:8000", "postgresql://u:p@127.0.0.1:5432/db", timeout=5.0
    )

    assert exit_code == 1
    assert cases == []
    assert "PROOF008" in capsys.readouterr().err


def test_run_fails_instead_of_vacuous_success_on_empty_composite_case_list(
    monkeypatch, capsys
) -> None:
    module = load_atoms_proof_module()
    monkeypatch.setattr(module, "ATOM_SMOKE_CASES", (("atom.one", "scenario-one", {}),))
    monkeypatch.setattr(module, "COMPOSITE_SMOKE_CASES", ())
    monkeypatch.setattr(module, "_check_ledger", _passing_check_ledger(module))
    monkeypatch.setattr(
        module.smoke,
        "_run_one_case",
        lambda api_url, scenario_id, scenario_input, timeout: module.smoke.CaseResult(
            session_id="s1", error_code=None, error_message=None
        ),
    )

    cases, exit_code = module.run(
        "http://127.0.0.1:8000", "postgresql://u:p@127.0.0.1:5432/db", timeout=5.0
    )

    assert exit_code == 1
    assert len(cases) == 1
    assert "PROOF009" in capsys.readouterr().err
