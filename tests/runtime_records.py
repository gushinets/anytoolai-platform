from __future__ import annotations

from typing import Any

from anytoolai_platform_core.actions.models import ActionRunRecord
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.workflows.models import JobRecord


def make_scenario_session(**overrides: Any) -> ScenarioSessionRecord:
    values = {
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_id": "smoke_start",
        "scenario_version": 1,
    }
    values.update(overrides)
    return ScenarioSessionRecord(**values)


def make_job(scenario_session_id: str, **overrides: Any) -> JobRecord:
    values = {
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_session_id": scenario_session_id,
        "workflow_id": "wf_smoke",
        "workflow_version": 1,
    }
    values.update(overrides)
    return JobRecord(**values)


def make_action_run(scenario_session_id: str, job_id: str, **overrides: Any) -> ActionRunRecord:
    values = {
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_session_id": scenario_session_id,
        "job_id": job_id,
        "workflow_id": "wf_smoke",
        "step_id": "step_1",
        "action_type": "text.extract_structured_fields",
        "action_config_id": "cfg_extract",
    }
    values.update(overrides)
    return ActionRunRecord(**values)
