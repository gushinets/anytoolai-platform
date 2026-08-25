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
    failed_provider_call_ids: tuple[str, ...] = (),
    artifact_ids: tuple[str, ...] = ("artifact-step-1", "artifact-result"),
) -> list[dict]:
    """One event per session-scoped expected type, plus one artifact.created row per
    artifact_id, one action.started/action.succeeded pair per action_run_id, and one
    provider.request_started/terminal pair per provider_call_id -- matching the per-row
    artifact_id/action_run_id/provider_call_id correlation _classify_ledger requires. Every
    provider_call_id gets a terminal provider.request_succeeded event, except those also listed
    in failed_provider_call_ids (a subset of provider_call_ids), which get provider.request_failed
    instead -- models a retried physical attempt's own first, failed call. Defaults match
    _one_step_row()'s "run-1", _one_provider_call()'s "call-1", and
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
        terminal_event_type = (
            "provider.request_failed"
            if call_id in failed_provider_call_ids
            else "provider.request_succeeded"
        )
        events.append({"event_type": terminal_event_type, "provider_call_id": call_id})
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
    row = {
        "id": "call-1",
        "action_run_id": "run-1",
        "job_id": "job-1",
        "physical_call_index": 0,
        "status": "succeeded",
        "latency_ms": 123,
        "input_tokens": 10,
        "output_tokens": 20,
        "total_tokens": 30,
        "estimated_cost": 0.001,
    }
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
    assert case.result_artifact_id == "artifact-result"
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
            output_artifact_id="artifact-step-1",
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
    # `code-review` (me #6) finding: no job row was ever resolved here, so there is no known
    # result_artifact_id to report -- must stay None, not e.g. crash or default to something else.
    assert case.result_artifact_id is None


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
    # `code-review` (me #6) finding: a case that fails *after* its job row resolved must still
    # carry the real result_artifact_id, not silently drop it just because the case failed.
    assert case.result_artifact_id == "artifact-result"


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


def test_classify_ledger_passes_and_sums_cost_across_retried_provider_calls() -> None:
    """Code-review finding: default_text_generation_v1's retry_policy.hard_limits permits up to 4
    physical provider calls per action (structured-output/transport retries) -- more than one
    provider_calls row for a single action_run is a legitimate outcome for a live case, not a
    correlation defect, as long as it's within max_provider_calls_per_action. The step's evidence
    must sum every physical attempt's cost/tokens/latency, not report just one of them (which
    would silently lose real spend from live_canary.py's cost cap).

    `code-review` finding: this test's own events used to give BOTH provider_calls
    rows a provider.request_succeeded event, which never exercised the actual retry shape (a
    transport retry's first physical attempt ends in provider.request_failed, then a second
    attempt succeeds) -- that shape was rejected as PROOF013 until the fix below. call-1 here is
    the failed first attempt (lower physical_call_index), call-2 is the succeeded retry."""
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="text.extract_structured_fields", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[
            _one_provider_call(
                id="call-1", action_run_id="run-1", physical_call_index=0, status="failed",
            ),
            _one_provider_call(
                id="call-2", action_run_id="run-1", physical_call_index=1, status="succeeded",
            ),
        ],
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=_all_expected_events(
            provider_call_ids=("call-1", "call-2"), failed_provider_call_ids=("call-1",),
        ),
        expected_event_types=EXPECTED_EVENT_TYPES,
        max_provider_calls_per_action=2,
    )

    assert case.status == "pass"
    assert case.error_code is None
    assert len(case.steps) == 1
    step = case.steps[0]
    assert step.latency_ms == 246
    assert step.input_tokens == 20
    assert step.output_tokens == 40
    assert step.total_tokens == 60
    assert step.estimated_cost == pytest.approx(0.002)


def test_classify_ledger_fails_closed_when_retried_provider_calls_cost_nets_out() -> None:
    """`code-review` (me #8) finding: two individually-plausible provider_calls rows can net out
    to an innocuous-looking StepEvidence.estimated_cost via plain summation -- e.g. $0.60 and
    -$0.50 sum to $0.10, which live_canary.py's own post-hoc _safe_step_cost() guard (applied to
    the already-summed StepEvidence.estimated_cost) sees as a perfectly valid, small cost.
    _step_evidence_from_action_run() must poison the sum to math.inf per corrupt raw call
    *before* summing, not validate only the finished total."""
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="text.extract_structured_fields", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[
            _one_provider_call(
                id="call-1", action_run_id="run-1", physical_call_index=0, status="failed",
                estimated_cost=0.6,
            ),
            _one_provider_call(
                id="call-2", action_run_id="run-1", physical_call_index=1, status="succeeded",
                estimated_cost=-0.5,
            ),
        ],
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=_all_expected_events(
            provider_call_ids=("call-1", "call-2"), failed_provider_call_ids=("call-1",),
        ),
        expected_event_types=EXPECTED_EVENT_TYPES,
        max_provider_calls_per_action=2,
    )

    assert case.status == "pass"
    assert len(case.steps) == 1
    assert case.steps[0].estimated_cost == module.math.inf


def test_classify_ledger_fails_closed_on_nan_provider_call_cost() -> None:
    """Same `_safe_raw_cost()` guard as the negative-netting test above, for a NaN raw
    `provider_calls.estimated_cost` -- a single corrupt row is enough here (no second call
    needed to net anything out), since `sum()` of anything containing math.inf is math.inf."""
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="text.extract_structured_fields", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[_one_provider_call(estimated_cost=module.math.nan)],
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=_all_expected_events(),
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "pass"
    assert case.steps[0].estimated_cost == module.math.inf


def test_classify_ledger_reports_proof003_when_retry_count_exceeds_the_configured_cap() -> None:
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[
            _one_provider_call(id="call-1", action_run_id="run-1"),
            _one_provider_call(id="call-2", action_run_id="run-1"),
            _one_provider_call(id="call-3", action_run_id="run-1"),
        ],
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=_all_expected_events(provider_call_ids=("call-1", "call-2", "call-3")),
        expected_event_types=EXPECTED_EVENT_TYPES,
        max_provider_calls_per_action=2,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF003"


def test_classify_ledger_reports_proof024_when_a_provider_call_has_no_terminal_event() -> None:
    """`code-review`: a provider_calls row with only a provider.request_started
    event (no succeeded, no failed -- e.g. the physical attempt is still in flight, or its
    terminal event was lost) must fail, not silently pass now that a bare succeeded==1 check was
    relaxed. Uses a second, fully-normal run-2/call-2 pair alongside the run-1/call-1 pair under
    test purely so provider.request_succeeded still appears somewhere in the session -- otherwise
    stripping call-1's only succeeded event would (correctly, but not usefully for this test)
    trip the session-wide PROOF005 check before PROOF024 ever gets a chance to run."""
    module = load_atoms_proof_module()

    events = [
        event
        for event in _all_expected_events(
            action_run_ids=("run-1", "run-2"),
            provider_call_ids=("call-1", "call-2"),
            artifact_ids=("artifact-step-1", "artifact-step-2", "artifact-result"),
        )
        if not (
            event["event_type"] == "provider.request_succeeded"
            and event.get("provider_call_id") == "call-1"
        )
    ]
    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
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
    assert case.error_code == "PROOF024"


def test_classify_ledger_reports_proof024_when_a_provider_call_has_both_terminal_events() -> None:
    """A provider_calls row with both a provider.request_succeeded and a provider.request_failed
    event is an inconsistent double-terminal state, not a legitimate retry (a retry is two
    *separate* provider_calls rows, one terminal event each)."""
    module = load_atoms_proof_module()

    events = [
        *_all_expected_events(),
        {"event_type": "provider.request_failed", "provider_call_id": "call-1"},
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
    assert case.error_code == "PROOF024"


def test_classify_ledger_reports_proof025_when_succeeded_event_disagrees_with_persisted_status() -> None:
    """The persisted provider_calls.status must agree with whichever terminal event fired -- a
    row with a provider.request_succeeded event but a "failed" status column is an inconsistent
    ledger, not just a missing/duplicate-event defect PROOF024 already covers."""
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[_one_provider_call(status="failed")],
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=_all_expected_events(),
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF025"


def test_classify_ledger_reports_proof025_when_failed_event_disagrees_with_persisted_status() -> None:
    """Same PROOF005-avoidance reasoning as the no-terminal-event test above: call-1 alone
    emitting provider.request_failed (instead of succeeded) would strip the session's only
    provider.request_succeeded event, so a second, fully-normal run-2/call-2 pair keeps that type
    present while call-1 is the one under test."""
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[
            _one_step_row(),
            _one_step_row(id="run-2", step_id="detect_issues", output_artifact_id="artifact-step-2"),
        ],
        provider_calls=[
            _one_provider_call(id="call-1", action_run_id="run-1", status="succeeded"),
            _one_provider_call(id="call-2", action_run_id="run-2"),
        ],
        artifacts=[
            _one_step_artifact(),
            _one_step_artifact(id="artifact-step-2", action_run_id="run-2"),
            _one_result_artifact(),
        ],
        events=_all_expected_events(
            action_run_ids=("run-1", "run-2"),
            provider_call_ids=("call-1", "call-2"),
            failed_provider_call_ids=("call-1",),
            artifact_ids=("artifact-step-1", "artifact-step-2", "artifact-result"),
        ),
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF025"


def test_classify_ledger_accepts_timed_out_status_for_a_failed_terminal_event() -> None:
    """ProviderCallStatus.timed_out also emits provider.request_failed (gateway/events.py), not a
    dedicated event type -- a "timed_out" status must satisfy the failed-terminal-event check,
    not just "failed"."""
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="text.extract_structured_fields", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[
            _one_provider_call(
                id="call-1", action_run_id="run-1", physical_call_index=0, status="timed_out",
            ),
            _one_provider_call(
                id="call-2", action_run_id="run-1", physical_call_index=1, status="succeeded",
            ),
        ],
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=_all_expected_events(
            provider_call_ids=("call-1", "call-2"), failed_provider_call_ids=("call-1",),
        ),
        expected_event_types=EXPECTED_EVENT_TYPES,
        max_provider_calls_per_action=2,
    )

    assert case.status == "pass"
    assert case.error_code is None


def test_classify_ledger_reports_proof015_when_a_failed_event_is_orphaned() -> None:
    """Orphan detection (PROOF015) must also cover provider.request_failed rows, not just
    started/succeeded -- a failed event misattributed to an unknown provider_call_id is just as
    much a correlation defect as an orphaned started/succeeded one."""
    module = load_atoms_proof_module()

    events = [
        *_all_expected_events(),
        {"event_type": "provider.request_failed", "provider_call_id": "call-bogus"},
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


def test_classify_ledger_reports_proof026_when_the_last_physical_attempt_did_not_succeed() -> None:
    """An action_run only reaches _classify_ledger() after the HTTP layer already observed the
    session succeed, so its *last* physical attempt (highest physical_call_index) must be the one
    that succeeded -- a ledger where the highest-index call is still "failed" (e.g. a
    physical_call_index recorded out of actual attempt order) is an inconsistent evidence trail
    even though every individual row passes PROOF013/024/025 on its own."""
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[
            _one_provider_call(
                id="call-1", action_run_id="run-1", physical_call_index=0, status="succeeded",
            ),
            _one_provider_call(
                id="call-2", action_run_id="run-1", physical_call_index=1, status="failed",
            ),
        ],
        artifacts=[_one_step_artifact(), _one_result_artifact()],
        events=_all_expected_events(
            provider_call_ids=("call-1", "call-2"), failed_provider_call_ids=("call-2",),
        ),
        expected_event_types=EXPECTED_EVENT_TYPES,
        max_provider_calls_per_action=2,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF026"


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
    """Mirrors PROOF017 for the job's own result_artifact_id: must carry no action_run_id
    (workflows/runner.py's _create_final_artifact always creates it that way). Team-lead-#5
    review: PROOF023's full ownership scan (strict, no allow_none -- unlike event_log.job_id,
    no ArtifactService caller ever creates a job-less artifact) now runs before this check and
    already guarantees job_id is exactly right for every row, so only the action_run_id lineage
    remains for this check to catch."""
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[_one_provider_call()],
        artifacts=[_one_step_artifact(), _one_result_artifact(action_run_id="run-1")],
        events=_all_expected_events(),
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF018"


def test_classify_ledger_reports_proof023_when_an_extra_unreferenced_artifact_is_misowned() -> None:
    """Team-lead-#3 review: an extra artifacts_table row for a different job -- not referenced
    by any action_run.output_artifact_id or the job's result_artifact_id -- is invisible to
    PROOF017/018 (they only check the rows they reference), and to PROOF020/021 as long as the
    extra row has exactly one matching artifact.created event of its own (which it does here),
    since that correlation only asks "does this id have exactly one creation event", not "does
    this id belong here at all"."""
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[_one_provider_call()],
        artifacts=[
            _one_step_artifact(),
            _one_result_artifact(),
            _one_step_artifact(id="artifact-extra", job_id="job-other", action_run_id=None),
        ],
        events=_all_expected_events(
            artifact_ids=("artifact-step-1", "artifact-result", "artifact-extra")
        ),
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF023"


def test_classify_ledger_reports_proof023_when_an_extra_artifact_has_a_null_job_id() -> None:
    """Team-lead-#5 review: no ArtifactService caller ever creates a job-less artifact (unlike
    event_log.job_id, which PROOF019 legitimately tolerates as null since scenario.started is
    emitted before a job exists), so tolerating job_id=None here would let an unowned extra
    artifact -- with its own job-less artifact.created event, which PROOF019 would also
    tolerate -- pass this entire proof as PASS with an artifact nothing actually claims.
    PROOF023 must reject a null job_id, not just a wrong non-null one."""
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[_one_provider_call()],
        artifacts=[
            _one_step_artifact(),
            _one_result_artifact(),
            _one_step_artifact(id="artifact-extra", job_id=None, action_run_id=None),
        ],
        events=[
            *_all_expected_events(),
            {"event_type": "artifact.created", "artifact_id": "artifact-extra"},
        ],
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF023"


def test_classify_ledger_reports_proof023_when_step_artifact_has_wrong_job_id() -> None:
    """Twenty-third code review pass finding: the only prior PROOF023 regression case used an
    extra, unreferenced artifact -- nothing proved the full scan also catches a wrong, non-null
    job_id on a *referenced* row (action_run.output_artifact_id) now that PROOF023 runs before
    PROOF017. Correct by code inspection, but a future reorder or a _first_job_id_mismatch()
    change that skipped referenced rows would have gone uncaught."""
    module = load_atoms_proof_module()

    case = module._classify_ledger(
        label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
        job_row={"id": "job-1", "result_artifact_id": "artifact-result"},
        action_runs=[_one_step_row()],
        provider_calls=[_one_provider_call()],
        artifacts=[_one_step_artifact(job_id="job-other"), _one_result_artifact()],
        events=_all_expected_events(),
        expected_event_types=EXPECTED_EVENT_TYPES,
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF023"


def test_classify_ledger_reports_proof023_when_result_artifact_has_wrong_job_id() -> None:
    """Mirrors the step-artifact case above for the job's own result_artifact_id."""
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
    assert case.error_code == "PROOF023"


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
    # code review #2 (2026-08-24) finding: both provider_calls rows already carry a real,
    # billed estimated_cost -- a failed case must still report it (live_canary.py's cost cap sums
    # exactly this field), not silently drop it to 0 just because the overall ledger is invalid.
    # The orphan row can't be correlated to a known action_run, so it falls back to its own
    # action_run_id as step_id and "unknown" for the fields only action_runs carries.
    assert len(case.steps) == 2
    matched_step, orphan_step = case.steps
    assert matched_step.step_id == "extract"
    assert matched_step.estimated_cost == 0.001
    assert orphan_step.step_id == "run-does-not-exist"
    assert orphan_step.action_type == "unknown"
    assert orphan_step.action_config_id == "unknown"
    assert orphan_step.estimated_cost == 0.001
    assert sum(step.estimated_cost for step in case.steps) == pytest.approx(0.002)


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
            _one_provider_call(id="call-1", action_run_id="run-1"),
            _one_provider_call(id="call-2", action_run_id="run-2"),
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


def test_run_case_with_ledger_check_reports_http_failure_without_touching_db(
    monkeypatch, capsys
) -> None:
    """A case that fails during the HTTP/poll phase must short-circuit before any DB
    connection is attempted -- exercised by never providing a real engine here."""
    module = load_atoms_proof_module()
    monkeypatch.setattr(
        module.smoke,
        "_run_one_case",
        lambda api_url, scenario_id, scenario_input, timeout, **_kwargs: module.smoke.CaseResult(
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
    assert case.steps == ()


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


def test_run_case_with_ledger_check_recovers_known_cost_on_an_http_layer_failure(
    monkeypatch, capsys
) -> None:
    """code review #3 (2026-08-24) finding: a case can fail at the HTTP/status-polling layer
    *after* a real, billed provider call already happened server-side (e.g. the session completed
    but SMOKE009's schema_ref cross-check then failed) -- this branch never reaches
    _check_ledger()/_classify_ledger(), so without _known_steps_for_session() the spend would
    silently report 0 to live_canary.py's cost cap."""
    module = load_atoms_proof_module()
    monkeypatch.setattr(
        module.smoke,
        "_run_one_case",
        lambda api_url, scenario_id, scenario_input, timeout, **_kwargs: module.smoke.CaseResult(
            session_id="session-1", error_code="SMOKE009",
            error_message="SMOKE009: schema_ref mismatch",
        ),
    )
    action_runs = [_one_step_row()]
    provider_calls = [_one_provider_call()]

    class _FakeEngine:
        def connect(self):
            return _FakeConnection([_FakeResult(action_runs), _FakeResult(provider_calls)])

    case = module._run_case_with_ledger_check(
        "http://127.0.0.1:8000", _FakeEngine(), kind="atom", label="atom.one",
        scenario_id="scenario-1", scenario_input={}, timeout=5.0,
    )

    assert case.status == "fail"
    assert case.error_code == "SMOKE009"
    assert len(case.steps) == 1
    assert case.steps[0].estimated_cost == 0.001
    assert case.cost_unknown is False


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
        lambda api_url, scenario_id, scenario_input, timeout, **_kwargs: module.smoke.CaseResult(
            session_id="session-1", error_code=None, error_message=None
        ),
    )
    captured: dict = {}

    def _fake_check_ledger(engine, *, label, scenario_id, kind, scenario_session_id, **_kwargs):
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
    which is still enough to tell e.g. an auth/connection failure from a bad-query error.

    Every connect() call fails here, so _known_steps_for_session()'s own recovery query fails
    too -- `code-review` finding: this must report cost_unknown=True (steps=() does NOT
    mean $0 was spent), not silently look identical to a case that never got a session at all,
    or live_canary.py's cost cap fails open on a lost DB connection."""
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
    assert case.steps == ()
    assert case.cost_unknown is True


def test_check_ledger_recovers_known_cost_when_its_own_fetch_raises(monkeypatch) -> None:
    """code review #4 (2026-08-24) finding #1: a case can make a real, billed provider call and
    then hit a transient SQLAlchemyError (connection drop, pool exhaustion, statement timeout)
    fetching _check_ledger()'s own 5-table batch -- that spend must not silently report 0 to
    live_canary.py's cost cap just because the *second* connection attempt (this batch's own)
    failed, when a fresh recovery connection can still see the already-committed provider_calls
    row."""
    module = load_atoms_proof_module()
    action_runs = [_one_step_row()]
    provider_calls = [_one_provider_call()]

    class _FailsOnceThenRecoversEngine:
        def __init__(self):
            self._connect_count = 0

        def connect(self):
            self._connect_count += 1
            if self._connect_count == 1:
                raise module.sa.exc.SQLAlchemyError("boom")
            return _FakeConnection([_FakeResult(action_runs), _FakeResult(provider_calls)])

    case = module._check_ledger(
        _FailsOnceThenRecoversEngine(), label="atom.one", scenario_id="scenario-1", kind="atom",
        scenario_session_id="session-1",
    )

    assert case.status == "fail"
    assert case.error_code == "PROOF000"
    assert len(case.steps) == 1
    assert case.steps[0].estimated_cost == 0.001
    assert case.cost_unknown is False


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


def test_write_evidence_report_normalizes_non_finite_cost_to_null(tmp_path) -> None:
    """`code-review` (me #9) finding: `_safe_raw_cost()`/live_canary.py's `_safe_step_cost()`
    deliberately produce math.inf for a corrupt provider_calls.estimated_cost row -- json.dumps()
    would otherwise happily emit the non-standard `Infinity` token (not valid JSON per RFC 8259),
    which a strict or non-Python consumer of this evidence report would fail to parse."""
    module = load_atoms_proof_module()
    case = module.EvidenceCase(
        label="atom.one", scenario_id="scenario-1", kind="atom", status="pass",
        session_id="session-1", job_id="job-1", error_code=None, error_message=None,
        steps=(
            module.StepEvidence(
                step_id="extract", action_type="text.extract_structured_fields",
                action_config_id="kernel_demo.extract_structured_fields_v1",
                estimated_cost=module.math.inf,
            ),
        ),
    )

    report_path = module.write_evidence_report([case], exit_code=1, output_root=tmp_path)
    raw_text = report_path.read_text(encoding="utf-8")

    assert "Infinity" not in raw_text
    assert "NaN" not in raw_text
    payload = json.loads(raw_text)
    assert payload["cases"][0]["steps"][0]["estimated_cost"] is None


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
    """Twenty-first code review pass finding: create_sync_engine()'s errors default to a
    "Runtime storage" label describing platform-api/platform-worker's boot path -- misleading
    for this CLI's own operator-facing configuration errors (e.g. a bad --database-url-env
    DSN). _build_engine() passes its own context through to create_sync_engine(), which now
    owns the whole DSN-parsing/driver/decode/construction contract directly (team-lead-#6
    review: this function used to keep a second, independently-maintained copy of the driver
    coercion+allowlist logic, which is exactly the kind of duplicate contract that let three
    separate rounds each find a new exception type escaping through one copy but not the
    other)."""
    module = load_atoms_proof_module()

    with pytest.raises(RuntimeError, match=r"^atoms-proof:"):
        module._build_engine(
            "postgresql+psycopg://user:pass@127.0.0.1:5432", decode_database_name=True
        )

    with pytest.raises(RuntimeError, match=r"^atoms-proof "):
        module._build_engine("sqlite:///tmp.db")


def test_build_engine_converts_a_malformed_dsn_into_a_runtime_error() -> None:
    """Team-lead-#5 review: make_url() raises sqlalchemy.exc.ArgumentError, not RuntimeError,
    for a DSN that isn't a URL at all -- left uncaught, run()'s except RuntimeError/PROOF022
    handling never sees it, so it propagates as a raw traceback."""
    module = load_atoms_proof_module()

    with pytest.raises(RuntimeError, match="database"):
        module._build_engine("not a url at all")


def test_build_engine_rejects_a_driver_other_than_the_installed_one() -> None:
    """Team-lead-#6 review: require_postgresql_url() only checks the drivername *prefix*, so
    any "postgresql+<anything>" passes it -- this repo installs psycopg[binary] v3 only, no
    other DBAPI driver. Without an explicit allowlist, a wrong-but-plausible suffix reaches
    SQLAlchemy's dialect-loading machinery and fails with whatever exception that specific
    driver's import path happens to produce: sqlalchemy.exc.NoSuchModuleError (an ArgumentError
    subclass) for a dialect SQLAlchemy has never heard of ("postgresql+unknown"), or a bare
    ModuleNotFoundError (NOT an ArgumentError subclass -- team-lead-#5's ArgumentError-catching
    fix didn't cover this one) for a real dialect whose DBAPI package isn't installed here
    ("postgresql+psycopg2", the exact driver storage/db.py's own module docstring calls out as
    absent). Chasing each newly-discovered exception type doesn't converge, so _build_engine()
    now rejects any driver but postgresql+psycopg directly, before ever attempting engine
    construction -- both cases below never reach create_engine() at all."""
    module = load_atoms_proof_module()

    with pytest.raises(RuntimeError, match="postgresql\\+unknown"):
        module._build_engine("postgresql+unknown://user:pass@127.0.0.1:5432/anytoolai")

    with pytest.raises(RuntimeError, match="postgresql\\+psycopg2"):
        module._build_engine("postgresql+psycopg2://user:pass@127.0.0.1:5432/anytoolai")


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
    def fake(engine, *, label, scenario_id, kind, scenario_session_id, **_kwargs):
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

    def fake_run_one_case(api_url, scenario_id, scenario_input, timeout, **_kwargs):
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
        lambda api_url, scenario_id, scenario_input, timeout, **_kwargs: module.smoke.CaseResult(
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

    # Twenty-fourth code review pass: PROOF022 is deliberately broad (see run()'s own comment),
    # covering any RuntimeError _build_engine()/create_sync_engine() raises -- not just the
    # decode-fail-fast case above. A non-PostgreSQL DSN raises via require_postgresql_url()
    # instead, a different call site entirely; nothing at the run() level proved that one also
    # reaches PROOF022 rather than a raw traceback.
    cases, exit_code = module.run(
        "http://127.0.0.1:8000", "sqlite:///tmp.db", timeout=5.0, decode_database_name=True,
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
        lambda api_url, scenario_id, scenario_input, timeout, **_kwargs: (
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
        lambda api_url, scenario_id, scenario_input, timeout, **_kwargs: module.smoke.CaseResult(
            session_id="s1", error_code=None, error_message=None
        ),
    )

    cases, exit_code = module.run(
        "http://127.0.0.1:8000", "postgresql://u:p@127.0.0.1:5432/db", timeout=5.0
    )

    assert exit_code == 1
    assert len(cases) == 1
    assert "PROOF009" in capsys.readouterr().err
