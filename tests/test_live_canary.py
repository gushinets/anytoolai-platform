"""ANY-221: CI-safe tests for scripts/agent/live_canary.py -- no DB, no network, no credentials.
Mirrors tests/test_atoms_proof.py's module-loading pattern (load_cached_module by file path) so
this file can run as part of the normal credential-free quick-check gate even though the script
it tests is only ever meaningfully run manually/on a schedule with a real OPENAI_API_KEY."""

from __future__ import annotations

import json
from pathlib import Path

from tests.module_loading import load_cached_module


def load_live_canary_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "agent" / "live_canary.py"
    return load_cached_module("live_canary_module", module_path)


def test_load_live_canary_module_returns_the_same_cached_module_on_repeat_calls() -> None:
    assert load_live_canary_module() is load_live_canary_module()


def test_live_atom_cases_has_eleven_entries_matching_atom_smoke_cases_action_types() -> None:
    module = load_live_canary_module()

    assert len(module.LIVE_ATOM_CASES) == 11
    live_action_types = {action_type for action_type, _scenario_id, _input in module.LIVE_ATOM_CASES}
    smoke_action_types = {
        action_type for action_type, _scenario_id, _input in module.atoms_proof.ATOM_SMOKE_CASES
    }
    assert live_action_types == smoke_action_types

    # Every live scenario_id must actually be the `_live_` sibling, not accidentally reused from
    # ATOM_SMOKE_CASES -- a live case sharing a fake scenario_id would silently run the fake
    # provider instead of the real one.
    fake_scenario_ids = {
        scenario_id for _action_type, scenario_id, _input in module.atoms_proof.ATOM_SMOKE_CASES
    }
    for _action_type, live_scenario_id, _input in module.LIVE_ATOM_CASES:
        assert live_scenario_id not in fake_scenario_ids
        assert "live" in live_scenario_id


def test_live_composite_cases_has_three_entries_matching_composite_smoke_cases_workflow_ids() -> None:
    module = load_live_canary_module()

    assert len(module.LIVE_COMPOSITE_CASES) == 3
    live_workflow_ids = {
        workflow_id for workflow_id, _scenario_id, _input in module.LIVE_COMPOSITE_CASES
    }
    fake_workflow_ids = {
        workflow_id
        for workflow_id, _scenario_id, _input in module.atoms_proof.COMPOSITE_SMOKE_CASES
    }
    assert len(live_workflow_ids) == 3
    assert live_workflow_ids.isdisjoint(fake_workflow_ids)

    # Every live scenario_id must actually be the "_live_" sibling, not accidentally reused from
    # COMPOSITE_SMOKE_CASES -- a live case sharing a fake scenario_id would silently run the fake
    # provider instead of the real one.
    fake_scenario_ids = {
        scenario_id
        for _workflow_id, scenario_id, _input in module.atoms_proof.COMPOSITE_SMOKE_CASES
    }
    for workflow_id, live_scenario_id, _input in module.LIVE_COMPOSITE_CASES:
        assert live_scenario_id not in fake_scenario_ids
        assert workflow_id.endswith("_live_v1")
        assert live_scenario_id.endswith("_live_smoke_v1")


def test_live_composite_workflow_entries_returns_exactly_the_three_live_suffixed_entries() -> None:
    module = load_live_canary_module()

    entries = module._live_composite_workflow_entries()
    workflow_ids = {entry["workflow_id"] for entry in entries}

    assert len(entries) == 3
    assert workflow_ids == {
        workflow_id for workflow_id, _scenario_id, _input in module.LIVE_COMPOSITE_CASES
    }
    assert all(workflow_id.endswith("_live_v1") for workflow_id in workflow_ids)


def test_live_composite_coverage_error_covers_the_three_live_composite_workflows() -> None:
    module = load_live_canary_module()

    assert module._live_composite_coverage_error(module.LIVE_COMPOSITE_CASES) is None


def test_live_composite_coverage_error_reports_missing_workflow() -> None:
    module = load_live_canary_module()

    error = module._live_composite_coverage_error((("workflow.one", "scenario-one", {}),))

    assert error is not None and "LIVE010" in error


def test_live_composite_coverage_error_catches_scenario_workflow_mismatch() -> None:
    """Mirrors kernel_demo_smoke.py's own _composite_coverage_error() binding-mismatch guard, but
    for the live-suffixed workflows -- pairing a real live scenario_id with the wrong live
    workflow_id (each individually still unique/valid) must be caught, not just a bare duplicate
    check on either side alone."""
    module = load_live_canary_module()
    real_scenario_ids = [
        scenario_id for _workflow_id, scenario_id, _input in module.LIVE_COMPOSITE_CASES
    ]
    real_workflow_ids = [
        workflow_id for workflow_id, _scenario_id, _input in module.LIVE_COMPOSITE_CASES
    ]
    swapped_cases = tuple(
        (real_workflow_ids[(index + 1) % len(real_workflow_ids)], scenario_id, {})
        for index, scenario_id in enumerate(real_scenario_ids)
    )

    error = module._live_composite_coverage_error(swapped_cases)

    assert error is not None and "LIVE010" in error and "mismatch" in error


def test_cumulative_estimated_cost_treats_none_as_zero() -> None:
    module = load_live_canary_module()
    StepEvidence = module.atoms_proof.StepEvidence
    EvidenceCase = module.EvidenceCase

    def _case(*costs: float | None) -> "EvidenceCase":
        return EvidenceCase(
            label="atom.one", scenario_id="s", kind="atom", status="pass",
            session_id="session", job_id="job", error_code=None, error_message=None,
            steps=tuple(
                StepEvidence(step_id="x", action_type="t", action_config_id="c", estimated_cost=c)
                for c in costs
            ),
        )

    assert module._cumulative_estimated_cost([]) == 0.0
    assert module._cumulative_estimated_cost([_case(None)]) == 0.0
    assert module._cumulative_estimated_cost([_case(0.1, 0.2), _case(0.3)]) == 0.6


def test_run_aborts_remaining_cases_once_cost_cap_exceeded_without_running_them(monkeypatch) -> None:
    module = load_live_canary_module()
    calls: list[str] = []

    def _fake_run_case_with_ledger_check(
        api_url, engine, *, kind, label, scenario_id, scenario_input, timeout
    ):
        calls.append(scenario_id)
        return module.EvidenceCase(
            label=label, scenario_id=scenario_id, kind=kind, status="pass",
            session_id="session", job_id="job", error_code=None, error_message=None,
            steps=(
                module.atoms_proof.StepEvidence(
                    step_id="x", action_type=label, action_config_id="c", estimated_cost=0.1,
                ),
            ),
        )

    monkeypatch.setattr(
        module.atoms_proof, "_run_case_with_ledger_check", _fake_run_case_with_ledger_check
    )
    monkeypatch.setattr(module.atoms_proof, "_build_engine", lambda database_url: _FakeEngine())

    cases, exit_code = module.run(
        "http://127.0.0.1:8000", "postgresql://unused", timeout=1.0, max_total_cost_usd=0.25,
    )

    # 0.1 + 0.1 + 0.1 = 0.3 > 0.25 -- cap trips after the 3rd case, so only 3 of the combined
    # 11 atom + 3 composite queue (14 total) actually run; the rest -- the remaining 8 atoms and
    # all 3 composites, since the cap trips during the atom phase -- are marked LIVE001.
    assert len(calls) == 3
    assert len(cases) == 14
    assert exit_code == 1
    ran_cases = cases[:3]
    skipped_cases = cases[3:]
    assert all(case.status == "pass" for case in ran_cases)
    assert all(case.status == "fail" and case.error_code == "LIVE001" for case in skipped_cases)
    # Skipped cases must still carry their real label/scenario_id/kind (from LIVE_ATOM_CASES then
    # LIVE_COMPOSITE_CASES, in queue order), not a placeholder -- the evidence report's atom/
    # composite totals must stay attributable per case, and composite_total must still read 3 even
    # though the cost cap tripped before any composite case ran.
    assert [case.scenario_id for case in skipped_cases] == [
        scenario_id for _action_type, scenario_id, _input in module.LIVE_ATOM_CASES[3:]
    ] + [scenario_id for _workflow_id, scenario_id, _input in module.LIVE_COMPOSITE_CASES]
    assert [case.kind for case in skipped_cases] == ["atom"] * 8 + ["composite"] * 3


class _FakeEngine:
    def dispose(self) -> None:
        pass


def test_write_evidence_report_round_trips_extended_stepevidence_fields(tmp_path) -> None:
    module = load_live_canary_module()

    case = module.EvidenceCase(
        label="text.extract_structured_fields", scenario_id="kernel_demo.single_action_live_smoke_v1",
        kind="atom", status="pass", session_id="session-1", job_id="job-1", error_code=None,
        error_message=None,
        steps=(
            module.atoms_proof.StepEvidence(
                step_id="extract", action_type="text.extract_structured_fields",
                action_config_id="kernel_demo.extract_structured_fields_live_v1",
                latency_ms=842, input_tokens=120, output_tokens=45, total_tokens=165,
                estimated_cost=0.0021,
            ),
        ),
    )

    report_path = module.atoms_proof.write_evidence_report(
        [case], exit_code=0, output_root=tmp_path
    )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    step = payload["cases"][0]["steps"][0]
    assert step["latency_ms"] == 842
    assert step["input_tokens"] == 120
    assert step["output_tokens"] == 45
    assert step["total_tokens"] == 165
    assert step["estimated_cost"] == 0.0021

    # Privacy-safe by construction: no key anywhere in the payload should carry prompt/output
    # text or fixture bodies -- only ids/labels/booleans/numeric ledger metrics.
    serialized = json.dumps(payload)
    assert "start_input" not in serialized


def test_write_evidence_report_round_trips_composite_kind_with_multiple_steps(tmp_path) -> None:
    module = load_live_canary_module()

    atom_case = module.EvidenceCase(
        label="text.extract_structured_fields",
        scenario_id="kernel_demo.single_action_live_smoke_v1",
        kind="atom", status="pass", session_id="session-1", job_id="job-1", error_code=None,
        error_message=None,
        steps=(
            module.atoms_proof.StepEvidence(
                step_id="extract", action_type="text.extract_structured_fields",
                action_config_id="kernel_demo.extract_structured_fields_live_v1",
                latency_ms=842, input_tokens=120, output_tokens=45, total_tokens=165,
                estimated_cost=0.0021,
            ),
        ),
    )
    composite_case = module.EvidenceCase(
        label="kernel_demo.composite_analyze_and_clarify_live_v1",
        scenario_id="kernel_demo.composite_analyze_and_clarify_live_smoke_v1",
        kind="composite", status="pass", session_id="session-2", job_id="job-2", error_code=None,
        error_message=None,
        steps=tuple(
            module.atoms_proof.StepEvidence(
                step_id=step_id, action_type=f"text.{step_id}",
                action_config_id=f"{step_id}_live_v1",
                latency_ms=100 * index, input_tokens=10 * index, output_tokens=5 * index,
                total_tokens=15 * index, estimated_cost=0.001 * index,
            )
            for index, step_id in enumerate(
                ["extract", "detect_issues", "generate_questions", "generate_report"], start=1
            )
        ),
    )

    report_path = module.atoms_proof.write_evidence_report(
        [atom_case, composite_case], exit_code=0, output_root=tmp_path
    )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["atoms_total"] == 1
    assert payload["atoms_passed"] == 1
    assert payload["composite_total"] == 1
    assert payload["composite_passed"] == 1

    composite_payload = payload["cases"][1]
    assert composite_payload["kind"] == "composite"
    assert len(composite_payload["steps"]) == 4
    for index, step in enumerate(composite_payload["steps"], start=1):
        assert step["latency_ms"] == 100 * index
        assert step["input_tokens"] == 10 * index
        assert step["output_tokens"] == 5 * index
        assert step["total_tokens"] == 15 * index
        assert step["estimated_cost"] == 0.001 * index
