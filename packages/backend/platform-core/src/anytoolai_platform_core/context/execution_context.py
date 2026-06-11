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
