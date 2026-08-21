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


_SESSION_SCOPED_EVENT_TYPES = EXPECTED_EVENT_TYPES - {
    "action.started",
    "action.succeeded",
    "provider.request_started",
    "provider.request_succeeded",
}


def _all_expected_events(
    *,
    action_run_ids: tuple[str, ...] = ("run-1",),
    provider_call_ids: tuple[str, ...] = ("call-1",),
    artifact_ids: tuple[str, ...] = ("artifact-step-1", "artifact-result"),
) -> list[dict]:
    """One event per session-scoped expected type, plus one artifact.created row per
    artifact_id, one action.started/action.succeeded pair per action_run_id, and one
    provider.request_started/succeeded pair per provider_call_id -- matching the per-row
    artifact_id/action_run_id/provider_call_id correlation _classify_ledger requires. Defaults
    match _one_step_row()'s "run-1", _one_provider_call()'s "call-1", and
    _one_step_artifact()/_one_result_artifact()'s ids."""
    events = [
        {"event_type": event_type}
        for event_type in _SESSION_SCOPED_EVENT_TYPES - {"artifact.created"}
    ]
    for artifact_id in artifact_ids:
        events.append({"event_type": "artifact.created", "artifact_id": artifact_id})
    for run_id in action_run_ids:
        events.append({"event_type": "action.started", "action_run_id": run_id})
        events.append({"event_type": "action.succeeded", "action_run_id": run_id})
    for call_id in provider_call_ids:
        events.append({"event_type": "provider.request_started", "provider_call_id": call_id})
        events.append({"event_type": "provider.request_succeeded", "provider_call_id": call_id})
    return events


def _one_step_row(**overrides) -> dict:
    row = {
        "id": "run-1",
        "job_id": "job-1",
        "step_id": "extract",
        "action_type": "text.extract_structured_fields",
        "action_config_id": "kernel_demo.extract_structured_fields_v1",
        "output_artifact_id": "artifact-step-1",
    }
    row.update(overrides)
    return row


def _one_provider_call(**overrides) -> dict:
    row = {"id": "call-1", "action_run_id": "run-1", "job_id": "job-1"}
    row.update(overrides)
    return row


def _one_step_artifact(**overrides) -> dict:
    row = {"id": "artifact-step-1", "job_id": "job-1", "action_run_id": "run-1"}
    row.update(overrides)
    return row


def _one_result_artifact(**overrides) -> dict:
    row = {"id": "artifact-result", "job_id": "job-1", "action_run_id": None}
    row.update(overrides)
    return row


def _one_provider_call(**overrides) -> dict:
    row = {
        "action_run_id": "run-1",
        "latency_ms": 123,
        "input_tokens": 10,
        "output_tokens": 20,
        "total_tokens": 30,
        "estimated_cost": 0.001,
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
        provider_calls=[_one_provider_call()],
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=_all_expected_events(),
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
            latency_ms=123,
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            estimated_cost=0.001,
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
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=_all_expected_events(),
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
        provider_calls=[
            _one_provider_call(id="call-1", action_run_id="run-1"),
            _one_provider_call(id="call-2", action_run_id="run-1"),
        ],
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=_all_expected_events(),
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
        provider_calls=[_one_provider_call()],
        artifacts=[_one_result_artifact()],
        events=_all_expected_events(),
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
        provider_calls=[_one_provider_call()],
        artifacts=[_one_step_artifact()],
        events=_all_expected_events(),
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF004"
    assert "result_artifact_id" in case.error_message


def test_classify_ledger_reports_proof017_when_step_artifact_lineage_mismatches() -> None:
    """An artifacts_table row can exist under the step's
    output_artifact_id (so PROOF004's membership check passes) while belonging to a different
    job/action_run -- e.g. a copy-pasted artifact id from another session."""
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[_one_provider_call()],
        artifacts=[_one_step_artifact(action_run_id="run-other"), _one_result_artifact()],
        events=_all_expected_events(),
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF017"


def test_classify_ledger_reports_proof018_when_result_artifact_lineage_mismatches() -> None:
    """Mirrors PROOF017 for the job's own result_artifact_id: must belong to this job and carry
    no action_run_id (workflows/runner.py's _create_final_artifact always creates it that way)."""
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[_one_provider_call()],
        artifacts=[_one_step_artifact(), _one_result_artifact(job_id="job-other")],
        events=_all_expected_events(),
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF018"


def test_classify_ledger_reports_proof005_when_event_type_missing() -> None:
    module = load_atoms_proof_module()

    events = [
        event
        for event in _all_expected_events()
        if event["event_type"] != "scenario.completed"
    ]
    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[_one_provider_call()],
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=events,
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF005"
    assert "scenario.completed" in case.error_message


def test_classify_ledger_reports_proof019_when_event_job_id_mismatches() -> None:
    """job_id is nullable on event_log (some session-scoped events are
    emitted before a job exists), but a *non-null* mismatch must still fail -- e.g. a row
    misattributed to another job in the same scenario_session_id."""
    module = load_atoms_proof_module()

    events = [
        *_all_expected_events(),
        {"event_type": "scenario.checkpoint_reached", "job_id": "job-other"},
    ]
    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[_one_provider_call()],
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=events,
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF019"


def test_classify_ledger_reports_proof020_when_artifact_created_event_is_missing() -> None:
    """PROOF005 only checks the artifact.created *type* is present
    somewhere in the session, so a composite workflow with 2 artifacts could pass with only 1
    artifact.created row. Correlate by artifact_id."""
    module = load_atoms_proof_module()

    events = [
        event
        for event in _all_expected_events(
            artifact_ids=("artifact-step-1", "artifact-step-2", "artifact-result")
        )
        if not (
            event["event_type"] == "artifact.created"
            and event["artifact_id"] == "artifact-step-2"
        )
    ]
    action_runs = [
        _one_step_row(),
        _one_step_row(id="run-2", step_id="detect_issues", output_artifact_id="artifact-step-2"),
    ]
    case = module._classify_ledger(
        label="workflow.one", scenario_id="scenario-composite", kind="composite",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=action_runs,
        provider_calls=[
            _one_provider_call(id="call-1", action_run_id="run-1"),
            _one_provider_call(id="call-2", action_run_id="run-2"),
        ],
        artifacts=[
            _one_step_artifact(),
            _one_step_artifact(id="artifact-step-2", action_run_id="run-2"),
            _one_result_artifact(),
        ],
        events=[
            *events,
            {"event_type": "action.started", "action_run_id": "run-2"},
            {"event_type": "action.succeeded", "action_run_id": "run-2"},
        ],
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF020"


def test_classify_ledger_reports_proof021_when_artifact_created_event_is_orphaned() -> None:
    module = load_atoms_proof_module()

    events = [
        *_all_expected_events(),
        {"event_type": "artifact.created", "artifact_id": "artifact-bogus"},
    ]
    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[_one_provider_call()],
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=events,
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF021"


def test_classify_ledger_reports_proof006_when_action_event_count_is_wrong() -> None:
    module = load_atoms_proof_module()

    # Only run-1 gets an action.started/action.succeeded pair; run-2 gets none -- deliberately
    # not adding it to trigger PROOF006. Both provider calls get their event pair so this
    # doesn't also (incidentally) trigger PROOF013.
    events = _all_expected_events(
        action_run_ids=("run-1",),
        provider_call_ids=("call-1", "call-2"),
        artifact_ids=("artifact-step-1", "artifact-step-2", "artifact-result"),
    )
    case = module._classify_ledger(
        label="workflow.one", scenario_id="scenario-composite", kind="composite",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[
            _one_step_row(),
            _one_step_row(id="run-2", step_id="detect_issues", output_artifact_id="artifact-step-2"),
        ],
        provider_calls=[
            _one_provider_call(id="call-1", action_run_id="run-1"),
            _one_provider_call(id="call-2", action_run_id="run-2"),
        ],
        artifacts=[
            _one_step_artifact(),
            _one_step_artifact(id="artifact-step-2", action_run_id="run-2"),
            _one_result_artifact(),
        ],
        events=events,
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF006"


def test_classify_ledger_reports_proof011_when_action_run_job_id_mismatches() -> None:
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row(job_id="job-other")],
        provider_calls=[_one_provider_call()],
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=_all_expected_events(),
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF011"


def test_classify_ledger_reports_proof012_when_provider_call_is_orphaned() -> None:
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[
            _one_provider_call(),
            _one_provider_call(id="call-orphan", action_run_id="run-does-not-exist"),
        ],
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=_all_expected_events(),
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF012"


def test_classify_ledger_reports_proof016_when_provider_call_job_id_mismatches() -> None:
    """A provider_calls row can carry the right action_run_id (so PROOF012
    passes) while its own job_id column is mislinked to a different job -- action_run_id
    membership alone can't catch that."""
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[_one_provider_call(job_id="job-other")],
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=_all_expected_events(),
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF016"


def test_classify_ledger_reports_proof013_when_provider_event_count_is_wrong() -> None:
    module = load_atoms_proof_module()

    # provider.request_started/succeeded are present in the session-wide type set (satisfies
    # PROOF005) but tagged with a provider_call_id that doesn't match call-1, so PROOF013 must
    # still catch it.
    events = [
        event for event in _all_expected_events() if event.get("provider_call_id") != "call-1"
    ] + [
        {"event_type": "provider.request_started", "provider_call_id": "call-other"},
        {"event_type": "provider.request_succeeded", "provider_call_id": "call-other"},
    ]
    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[_one_provider_call()],
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=events,
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF013"


def test_classify_ledger_reports_proof014_when_action_event_is_orphaned() -> None:
    module = load_atoms_proof_module()

    # run-1 gets its normal, correctly-counted started/succeeded pair (so the per-run PROOF006
    # loop passes) plus one extra action.started row misattributed to a run_id that doesn't
    # belong to this session's action_runs -- must not be silently invisible.
    events = [
        *_all_expected_events(),
        {"event_type": "action.started", "action_run_id": "run-bogus"},
    ]
    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[_one_provider_call()],
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=events,
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF014"


def test_classify_ledger_reports_proof015_when_provider_event_is_orphaned() -> None:
    module = load_atoms_proof_module()

    events = [
        *_all_expected_events(),
        {"event_type": "provider.request_started", "provider_call_id": "call-bogus"},
    ]
    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[_one_provider_call()],
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=events,
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF015"


def test_classify_ledger_reports_proof014_when_orphan_action_event_has_null_run_id() -> None:
    """Sixteenth code review pass finding: action_run_id is a nullable event_log column, so an
    orphan action.started row can have action_run_id=None alongside another orphan row with a
    string id -- sorted({None, "run-bogus"}) raises TypeError, so this must still fail cleanly
    with PROOF014 instead of a raw traceback."""
    module = load_atoms_proof_module()

    events = [
        *_all_expected_events(),
        {"event_type": "action.started", "action_run_id": None},
        {"event_type": "action.started", "action_run_id": "run-bogus"},
    ]
    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[_one_provider_call()],
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=events,
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF014"


def test_classify_ledger_reports_proof015_when_orphan_provider_event_has_null_call_id() -> None:
    """Sixteenth code review pass finding: same null-id sort hazard as PROOF014, mirrored for
    provider_call_id."""
    module = load_atoms_proof_module()

    events = [
        *_all_expected_events(),
        {"event_type": "provider.request_started", "provider_call_id": None},
        {"event_type": "provider.request_started", "provider_call_id": "call-bogus"},
    ]
    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[_one_provider_call()],
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=events,
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF015"


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
        provider_calls=[
            _one_provider_call(),
            _one_provider_call(action_run_id="run-2", latency_ms=456, input_tokens=11,
                                output_tokens=21, total_tokens=32, estimated_cost=0.002),
        ],
        artifacts=[
            _one_step_artifact(),
            _one_step_artifact(id="artifact-step-2", action_run_id="run-2"),
            _one_result_artifact(),
        ],
        events=_all_expected_events(
            action_run_ids=("run-1", "run-2"),
            provider_call_ids=("call-1", "call-2"),
            artifact_ids=("artifact-step-1", "artifact-step-2", "artifact-result"),
        ),
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "pass"
    assert len(case.steps) == 2
    assert case.steps[0].latency_ms == 123
    assert case.steps[1].latency_ms == 456


def test_run_case_with_ledger_check_reports_http_failure_without_touching_db(
    monkeypatch, capsys
) -> None:
    """A case that fails during the HTTP/poll phase must short-circuit before any DB
    connection is attempted -- exercised by never providing a real engine here."""
    module = load_atoms_proof_module()
    monkeypatch.setattr(
        module.smoke,
        "_run_one_case",
        lambda api_url, scenario_id, scenario_input, timeout: module.smoke.CaseResult(
            session_id=None, error_code="SMOKE001",
            error_message="SMOKE001: boom (contains raw upstream detail)",
        ),
    )

    case = module._run_case_with_ledger_check(
        "http://127.0.0.1:8000", engine=None, kind="atom", label="atom.one",
        scenario_id="scenario-1", scenario_input={}, timeout=5.0,
    )

    assert case.status == "fail"
    assert case.error_code == "SMOKE001"
    # team-lead review finding: the raw CaseResult.error_message must not flow verbatim into the
    # persisted EvidenceCase -- only the safe, allowlisted error_code/scenario_id. The raw text is
    # still surfaced, but only on stderr for a human, never in the persisted evidence.
    assert "boom" not in case.error_message
    assert "SMOKE001" in case.error_message
    assert "boom (contains raw upstream detail)" in capsys.readouterr().err


def test_run_case_with_ledger_check_dispatches_a_passing_http_result_into_check_ledger(
    monkeypatch,
) -> None:
    """Team-lead review finding: no prior test proved an HTTP-success CaseResult forwards its
    session_id and the same engine into _check_ledger."""
    module = load_atoms_proof_module()
    sentinel_engine = object()
    monkeypatch.setattr(
        module.smoke,
        "_run_one_case",
        lambda api_url, scenario_id, scenario_input, timeout: module.smoke.CaseResult(
            session_id="session-1", error_code=None, error_message=None
        ),
    )
    captured: dict = {}

    def _fake_check_ledger(engine, *, label, scenario_id, kind, scenario_session_id):
        captured.update(
            engine=engine, label=label, scenario_id=scenario_id, kind=kind,
            scenario_session_id=scenario_session_id,
        )
        return module.EvidenceCase(
            label=label, scenario_id=scenario_id, kind=kind, status="pass",
            session_id=scenario_session_id, job_id="job-1", error_code=None,
            error_message=None, steps=(),
        )

    monkeypatch.setattr(module, "_check_ledger", _fake_check_ledger)

    case = module._run_case_with_ledger_check(
        "http://127.0.0.1:8000", sentinel_engine, kind="atom", label="atom.one",
        scenario_id="scenario-1", scenario_input={}, timeout=5.0,
    )

    assert case.status == "pass"
    assert captured == {
        "engine": sentinel_engine,
        "label": "atom.one",
        "scenario_id": "scenario-1",
        "kind": "atom",
        "scenario_session_id": "session-1",
    }


def test_check_ledger_wires_all_five_query_results_into_classify_ledger(monkeypatch) -> None:
    """Team-lead review finding: a focused fake-connection test proving all five DB results
    (job/action_runs/provider_calls/artifacts/events) reach _classify_ledger, along with the
    real module's own _EXPECTED_EVENT_TYPES rather than a test-local stand-in."""
    module = load_atoms_proof_module()

    job_row = {"id": "job-1", "result_artifact_id": "artifact-result"}
    action_runs = [{"id": "run-1", "job_id": "job-1"}]
    provider_calls = [{"id": "call-1", "action_run_id": "run-1"}]
    artifacts = [_one_step_artifact(), _one_result_artifact()]
    events = [{"event_type": "action.started", "action_run_id": "run-1"}]

    class _FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def mappings(self):
            return self

        def __iter__(self):
            return iter(self._rows)

        def one_or_none(self):
            return self._rows[0] if self._rows else None

    class _FakeConnection:
        def __init__(self, results):
            self._results = list(results)

        def execute(self, _stmt):
            return self._results.pop(0)

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

    class _FakeEngine:
        def connect(self):
            return _FakeConnection(
                [
                    _FakeResult([job_row]),
                    _FakeResult(action_runs),
                    _FakeResult(provider_calls),
                    _FakeResult(artifacts),
                    _FakeResult(events),
                ]
            )

    captured: dict = {}

    def _fake_classify_ledger(**kwargs):
        captured.update(kwargs)
        return module.EvidenceCase(
            label=kwargs["label"], scenario_id=kwargs["scenario_id"], kind=kwargs["kind"],
            status="pass", session_id=kwargs["scenario_session_id"], job_id="job-1",
            error_code=None, error_message=None, steps=(),
        )

    monkeypatch.setattr(module, "_classify_ledger", _fake_classify_ledger)

    module._check_ledger(
        _FakeEngine(), label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
    )

    assert captured["job_row"] == job_row
    assert captured["action_runs"] == action_runs
    assert captured["provider_calls"] == provider_calls
    assert captured["artifacts"] == artifacts
    assert captured["events"] == events
    assert captured["expected_event_types"] is module._EXPECTED_EVENT_TYPES


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


def test_build_engine_fails_fast_when_decode_flag_set_on_a_dsn_with_no_database_segment() -> None:
    """Silently skipping the decode left create_engine() to omit the
    database name, so libpq would connect to its own default database (commonly the connecting
    username) instead of failing -- mirrors storage/db.py's create_sync_engine() guard."""
    module = load_atoms_proof_module()

    with pytest.raises(RuntimeError, match="database"):
        module._build_engine(
            "postgresql+psycopg://user:pass@127.0.0.1:5432", decode_database_name=True
        )


def test_build_engine_fails_fast_when_decode_flag_set_on_a_dsn_with_empty_database_segment() -> None:
    """Twentieth code review pass finding: a trailing-slash DSN with nothing after it parses to
    database="" (empty string), not None -- mirrors storage/db.py's create_sync_engine() guard,
    which _build_engine() now delegates to."""
    module = load_atoms_proof_module()

    with pytest.raises(RuntimeError, match="database"):
        module._build_engine(
            "postgresql+psycopg://user:pass@127.0.0.1:5432/", decode_database_name=True
        )


def test_build_engine_labels_its_own_errors_as_atoms_proof_not_runtime_storage() -> None:
    """Twenty-first code review pass finding: _build_engine() delegates to
    create_sync_engine(), whose errors default to a "Runtime storage" label describing
    platform-api/platform-worker's boot path -- misleading for this CLI's own operator-facing
    configuration errors (e.g. a bad --database-url-env DSN). _build_engine() now passes its
    own context."""
    module = load_atoms_proof_module()

    with pytest.raises(RuntimeError, match=r"^atoms-proof:"):
        module._build_engine(
            "postgresql+psycopg://user:pass@127.0.0.1:5432", decode_database_name=True
        )

    with pytest.raises(RuntimeError, match=r"^atoms-proof "):
        module._build_engine("sqlite:///tmp.db")


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


def _run_main_capturing_decode_database_name(module, monkeypatch, argv) -> bool:
    captured = {}

    def fake_run(*args, **kwargs):
        captured["decode_database_name"] = kwargs["decode_database_name"]
        return [], 0

    monkeypatch.setattr(module, "run", fake_run)
    monkeypatch.setattr(
        module,
        "write_evidence_report",
        lambda cases, exit_code, **kwargs: Path("evidence-fake.json"),
    )
    monkeypatch.setattr(sys, "argv", argv)

    assert module.main() == 0
    return captured["decode_database_name"]


def test_main_forwards_database_url_is_percent_encoded_flag_when_set(monkeypatch, capsys) -> None:
    """Nineteenth code review pass finding (inline comments): --database-url-is-percent-encoded
    had no regression coverage proving it actually reaches run()'s decode_database_name -- only
    _build_engine() (further downstream) was tested directly."""
    module = load_atoms_proof_module()
    monkeypatch.setenv(_TEST_DATABASE_URL_ENV, "postgresql://u:p@127.0.0.1:5432/db")

    decode_database_name = _run_main_capturing_decode_database_name(
        module, monkeypatch, [*_TEST_MAIN_ARGV, "--database-url-is-percent-encoded"]
    )

    assert decode_database_name is True


def test_main_forwards_database_url_is_percent_encoded_flag_when_unset(monkeypatch, capsys) -> None:
    """Mirror of the above for the flag's unset (default) case."""
    module = load_atoms_proof_module()
    monkeypatch.setenv(_TEST_DATABASE_URL_ENV, "postgresql://u:p@127.0.0.1:5432/db")

    decode_database_name = _run_main_capturing_decode_database_name(
        module, monkeypatch, _TEST_MAIN_ARGV
    )

    assert decode_database_name is False


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


def test_run_reports_full_success_when_every_case_passes(monkeypatch, capsys) -> None:
    """Existing run() coverage only exercises mixed failure and empty-case
    exits, never proving the primary contract -- that a fully-passing atom and composite batch
    returns exit_code == 0 with every case marked "pass", mirroring
    kernel_demo_smoke.py's own full-pass regression test."""
    module = load_atoms_proof_module()
    monkeypatch.setattr(
        module,
        "ATOM_SMOKE_CASES",
        (("atom.one", "scenario-one", {}), ("atom.two", "scenario-two", {})),
    )
    monkeypatch.setattr(module, "COMPOSITE_SMOKE_CASES", (("workflow.one", "scenario-three", {}),))
    monkeypatch.setattr(module, "_check_ledger", _passing_check_ledger(module))
    monkeypatch.setattr(
        module.smoke,
        "_run_one_case",
        lambda api_url, scenario_id, scenario_input, timeout: module.smoke.CaseResult(
            session_id=scenario_id, error_code=None, error_message=None
        ),
    )

    cases, exit_code = module.run(
        "http://127.0.0.1:8000", "postgresql://u:p@127.0.0.1:5432/db", timeout=5.0
    )

    assert exit_code == 0
    assert len(cases) == 3
    assert all(case.status == "pass" for case in cases)
    out = capsys.readouterr().out
    assert "2/2 kernel_demo atoms passed" in out
    assert "1/1 kernel_demo composite workflows passed" in out


def test_run_reports_proof022_instead_of_a_raw_traceback_on_engine_configuration_error(
    monkeypatch, capsys
) -> None:
    """Twentieth code review pass finding: _build_engine() can raise RuntimeError (a
    caller-declared decode contract with nothing to decode) -- previously uncaught here, so it
    propagated as a raw traceback instead of the PROOF0xx failure category the module docstring
    promises for every failure category, and never reached write_evidence_report()."""
    module = load_atoms_proof_module()
    monkeypatch.setattr(module, "ATOM_SMOKE_CASES", (("atom.one", "scenario-one", {}),))

    cases, exit_code = module.run(
        "http://127.0.0.1:8000",
        "postgresql+psycopg://user:pass@127.0.0.1:5432/",
        timeout=5.0,
        decode_database_name=True,
    )

    assert cases == []
    assert exit_code == 1
    assert "PROOF022" in capsys.readouterr().err


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
