from __future__ import annotations

from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.scenarios.correlation import build_scenario_identity_metadata
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.workflows.models import JobRecord
from anytoolai_platform_worker.handlers.run_workflow import RunWorkflowHandler


def _job(scenario_session_id: str) -> JobRecord:
    return JobRecord(
        tenant_id="tenant_demo",
        region="eu-central",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_session_id=scenario_session_id,
        workflow_id="kernel_demo.single_action_extract_v1",
        workflow_version=1,
        metadata={
            "handoff_id": "handoff_demo",
            "acquisition_source": "extension",
        },
    )


def _scenario(
    *,
    guest_id: str | None,
    user_id: str | None,
    scenario_chain_id: str | None,
) -> ScenarioSessionRecord:
    return ScenarioSessionRecord(
        id="scenario_session_demo",
        tenant_id="tenant_demo",
        region="eu-central",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_id="kernel_demo.single_action_smoke_v1",
        scenario_version=1,
        guest_id=guest_id,
        user_id=user_id,
        scenario_chain_id=scenario_chain_id,
    )


def _execution_context(
    job: JobRecord,
    scenario: ScenarioSessionRecord,
) -> ExecutionContext:
    handler = object.__new__(RunWorkflowHandler)
    return handler._execution_context(job, scenario)


def _identity_from_context(
    context: ExecutionContext,
    scenario: ScenarioSessionRecord,
) -> dict[str, object]:
    identity = build_scenario_identity_metadata(scenario)
    return {key: getattr(context, key) for key in identity}


def test_execution_context_uses_guest_scenario_identity_contract() -> None:
    scenario = _scenario(
        guest_id="guest_context",
        user_id=None,
        scenario_chain_id="scenario_chain_context",
    )
    job = _job(scenario.id)

    context = _execution_context(job, scenario)

    assert _identity_from_context(context, scenario) == build_scenario_identity_metadata(
        scenario
    )
    assert context.guest_id == "guest_context"
    assert context.user_id is None
    assert context.scenario_chain_id == "scenario_chain_context"
    assert context.handoff_id == "handoff_demo"
    assert context.acquisition_source == "extension"


def test_execution_context_uses_authenticated_scenario_identity_contract() -> None:
    scenario = _scenario(
        guest_id=None,
        user_id="user_context",
        scenario_chain_id="scenario_chain_context",
    )
    job = _job(scenario.id)

    context = _execution_context(job, scenario)

    assert _identity_from_context(context, scenario) == build_scenario_identity_metadata(
        scenario
    )
    assert context.guest_id is None
    assert context.user_id == "user_context"
    assert context.scenario_chain_id == "scenario_chain_context"
