from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionContext:
    tenant_id: str
    region: str
    product_id: str
    frontend_id: str
    scenario_session_id: str | None = None
    job_id: str | None = None
    workflow_id: str | None = None
    workflow_version: int | None = None
    step_id: str | None = None
    guest_id: str | None = None
    user_id: str | None = None
    scenario_chain_id: str | None = None
    action_type: str | None = None
    action_config_id: str | None = None
    artifact_id: str | None = None
    handoff_id: str | None = None
    provider: str | None = None
    model: str | None = None
    acquisition_source: str | None = None
    action_run_id: str | None = None
    provider_policy_id: str | None = None
