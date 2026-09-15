from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from anytoolai_platform_core.common.ids import new_id
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.providers.models import ReasoningEffort


@dataclass(frozen=True)
class AtomLabRunRecord:
    tenant_id: str
    region: str
    product_id: str
    frontend_id: str
    scenario_session_id: str
    job_id: str
    atom_id: str
    scenario_id: str
    scenario_version: int
    workflow_id: str
    workflow_version: int
    step_id: str
    action_type: str
    action_definition_version: int
    action_config_id: str
    action_config_schema_version: int
    prompt_ref: str
    prompt_version: int
    base_prompt: str
    prompt: str
    input_schema_ref: str
    input_schema_version: int
    input_schema: dict[str, Any]
    output_schema_ref: str
    output_schema_version: int
    output_schema: dict[str, Any]
    input_payload: dict[str, Any]
    provider_policy_ref: str
    provider_policy: dict[str, Any]
    model_id: str
    reasoning_effort: ReasoningEffort | None
    capability_snapshot_id: str
    capability_provenance: dict[str, Any]
    workflow_definition: dict[str, Any]
    action_definition: dict[str, Any]
    action_config_definition: dict[str, Any]
    execution_definition_hash: str
    id: str = field(default_factory=lambda: new_id("atom_lab_run"))
    preset_id: str | None = None
    preset_version: int | None = None
    action_run_id: str | None = None
    artifact_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)

    def snapshot_payload(self) -> dict[str, Any]:
        return {
            "atom_id": self.atom_id,
            "scenario": {"id": self.scenario_id, "version": self.scenario_version},
            "workflow": {
                "id": self.workflow_id,
                "version": self.workflow_version,
                "step_id": self.step_id,
                "definition": self.workflow_definition,
            },
            "action": {
                "type": self.action_type,
                "definition_version": self.action_definition_version,
                "definition": self.action_definition,
                "config_id": self.action_config_id,
                "config_schema_version": self.action_config_schema_version,
                "config_definition": self.action_config_definition,
            },
            "prompt": {
                "ref": self.prompt_ref,
                "version": self.prompt_version,
                "base": self.base_prompt,
                "content": self.prompt,
            },
            "schemas": {
                "input": {
                    "ref": self.input_schema_ref,
                    "version": self.input_schema_version,
                    "content": self.input_schema,
                },
                "output": {
                    "ref": self.output_schema_ref,
                    "version": self.output_schema_version,
                    "content": self.output_schema,
                },
            },
            "input": self.input_payload,
            "provider": {
                "policy_ref": self.provider_policy_ref,
                "policy": self.provider_policy,
                "model_id": self.model_id,
                "reasoning_effort": (
                    None if self.reasoning_effort is None else self.reasoning_effort.value
                ),
                "capability_snapshot_id": self.capability_snapshot_id,
                "capability_provenance": self.capability_provenance,
            },
            "preset": {"id": self.preset_id, "version": self.preset_version},
            "execution_definition_hash": self.execution_definition_hash,
        }


__all__ = ["AtomLabRunRecord", "ReasoningEffort"]
