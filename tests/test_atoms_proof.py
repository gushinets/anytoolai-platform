from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def load_atoms_proof_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "agent" / "atoms_proof.py"
    spec = importlib.util.spec_from_file_location("atoms_proof_module", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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

    report_path = module.write_evidence_report([passing, failing], output_root=tmp_path)

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
