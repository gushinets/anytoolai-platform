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

    # 0.1 + 0.1 + 0.1 = 0.3 > 0.25 -- cap trips after the 3rd case, so only 3 of 11 actually run.
    assert len(calls) == 3
    assert len(cases) == 11
    assert exit_code == 1
    ran_cases = cases[:3]
    skipped_cases = cases[3:]
    assert all(case.status == "pass" for case in ran_cases)
    assert all(case.status == "fail" and case.error_code == "LIVE001" for case in skipped_cases)
    # Skipped cases must still carry their real label/scenario_id (from LIVE_ATOM_CASES), not a
    # placeholder -- the evidence report's 11-total count must stay attributable per atom.
    assert [case.scenario_id for case in skipped_cases] == [
        scenario_id for _action_type, scenario_id, _input in module.LIVE_ATOM_CASES[3:]
    ]


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
