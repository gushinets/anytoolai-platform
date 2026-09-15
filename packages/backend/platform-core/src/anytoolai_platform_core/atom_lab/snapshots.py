from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from anytoolai_platform_core.actions.executor import RunLocalActionSettings
from anytoolai_platform_core.atom_lab.models import AtomLabRunRecord
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.providers.models import (
    ProviderPolicy,
    ProviderRetryHardLimits,
    ProviderRetryPolicy,
    ProviderTransportRetryPolicy,
    ProviderValidationRetryPolicy,
    ReasoningEffort,
    StructuredOutputMode,
)
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.workflows.models import JobRecord


class AtomLabSnapshotCompatibilityError(RuntimeError):
    def __init__(self, message: str = "Atom Lab run snapshot is incompatible with the registry."):
        super().__init__(message)


@dataclass(frozen=True)
class AtomLabSnapshotRequest:
    atom_id: str
    input_payload: Mapping[str, Any]
    prompt: str
    model_id: str
    reasoning_effort: ReasoningEffort | None
    capability_snapshot_id: str
    capability_provenance: Mapping[str, Any]
    preset_id: str | None = None
    preset_version: int | None = None


def build_atom_lab_run_record(
    registry: ConfigRegistry,
    *,
    scenario: ScenarioSessionRecord,
    job: JobRecord,
    request: AtomLabSnapshotRequest,
) -> AtomLabRunRecord:
    workflow, step, action_config, action, prompt, input_schema, output_schema = (
        _resolve_execution_definitions(registry, scenario=scenario, job=job)
    )
    atom_metadata = action_config.metadata.get("atom_lab")
    if not isinstance(atom_metadata, Mapping) or atom_metadata.get("atom_id") != request.atom_id:
        raise ValueError("Atom Lab atom does not match the selected action configuration")
    if dict(request.input_payload) != scenario.metadata.get("input"):
        raise ValueError("Atom Lab snapshot input does not match the scenario input")
    if not request.prompt.strip():
        raise ValueError("Atom Lab prompt must not be empty")
    if not request.model_id.startswith("openai/"):
        raise ValueError("Atom Lab selected model must be an addressable OpenAI model")
    policy = registry.get_provider_policy(action_config.provider_policy_ref)
    if policy is None:
        raise LookupError(f"provider policy not found: {action_config.provider_policy_ref}")
    definition_bundle = _definition_bundle(
        workflow=workflow,
        step=step,
        action_config=action_config,
        action=action,
        prompt=prompt,
        input_schema=input_schema,
        output_schema=output_schema,
    )
    policy_snapshot = provider_policy_to_snapshot(policy)
    return AtomLabRunRecord(
        tenant_id=scenario.tenant_id,
        region=scenario.region,
        product_id=scenario.product_id,
        frontend_id=scenario.frontend_id,
        scenario_session_id=scenario.id,
        job_id=job.id,
        atom_id=request.atom_id,
        scenario_id=scenario.scenario_id,
        scenario_version=scenario.scenario_version,
        workflow_id=workflow.workflow_id,
        workflow_version=workflow.version,
        step_id=step.step_id,
        action_type=action.action_type,
        action_definition_version=action.version,
        action_config_id=action_config.action_config_id,
        action_config_schema_version=action_config.schema_version,
        prompt_ref=prompt.prompt_ref,
        prompt_version=prompt.version,
        base_prompt=prompt.content,
        prompt=request.prompt,
        input_schema_ref=input_schema.schema_ref,
        input_schema_version=input_schema.version,
        input_schema=_mutable_json(input_schema.schema),
        output_schema_ref=output_schema.schema_ref,
        output_schema_version=output_schema.version,
        output_schema=_mutable_json(output_schema.schema),
        input_payload=_mutable_json(request.input_payload),
        provider_policy_ref=policy.provider_policy_ref,
        provider_policy=policy_snapshot,
        model_id=request.model_id,
        reasoning_effort=request.reasoning_effort,
        capability_snapshot_id=request.capability_snapshot_id,
        capability_provenance=_mutable_json(request.capability_provenance),
        workflow_definition=definition_bundle["workflow"],
        action_definition=definition_bundle["action"],
        action_config_definition=definition_bundle["action_config"],
        execution_definition_hash=_definition_hash(definition_bundle),
        preset_id=request.preset_id,
        preset_version=request.preset_version,
    )


def load_run_local_action_settings(
    registry: ConfigRegistry,
    record: AtomLabRunRecord,
) -> RunLocalActionSettings:
    scenario = registry.get_scenario(record.scenario_id)
    workflow = registry.get_workflow(record.workflow_id)
    if scenario is None or workflow is None:
        raise AtomLabSnapshotCompatibilityError()
    synthetic_scenario = ScenarioSessionRecord(
        id=record.scenario_session_id,
        tenant_id=record.tenant_id,
        region=record.region,
        product_id=record.product_id,
        frontend_id=record.frontend_id,
        scenario_id=record.scenario_id,
        scenario_version=record.scenario_version,
        metadata={"input": record.input_payload},
    )
    synthetic_job = JobRecord(
        id=record.job_id,
        tenant_id=record.tenant_id,
        region=record.region,
        product_id=record.product_id,
        frontend_id=record.frontend_id,
        scenario_session_id=record.scenario_session_id,
        workflow_id=record.workflow_id,
        workflow_version=record.workflow_version,
    )
    try:
        _, step, action_config, action, prompt, input_schema, output_schema = (
            _resolve_execution_definitions(registry, scenario=synthetic_scenario, job=synthetic_job)
        )
    except (LookupError, ValueError) as exc:
        raise AtomLabSnapshotCompatibilityError() from exc
    current_bundle = _definition_bundle(
        workflow=workflow,
        step=step,
        action_config=action_config,
        action=action,
        prompt=prompt,
        input_schema=input_schema,
        output_schema=output_schema,
    )
    if _definition_hash(current_bundle) != record.execution_definition_hash:
        raise AtomLabSnapshotCompatibilityError()
    try:
        policy = provider_policy_from_snapshot(record.provider_policy_ref, record.provider_policy)
    except (KeyError, TypeError, ValueError) as exc:
        raise AtomLabSnapshotCompatibilityError() from exc
    return RunLocalActionSettings(
        run_id=record.id,
        action_type=record.action_type,
        action_config_id=record.action_config_id,
        prompt=record.prompt,
        prompt_ref=record.prompt_ref,
        prompt_version=record.prompt_version,
        provider_policy=replace(policy, model=record.model_id, fallback_policy=None),
        model_id=record.model_id,
        reasoning_effort=record.reasoning_effort,
    )


def provider_policy_to_snapshot(policy: ProviderPolicy) -> dict[str, Any]:
    return {
        "provider": policy.provider,
        "base_model": policy.model,
        "temperature": policy.temperature,
        "timeout_seconds": policy.timeout_seconds,
        "transport_owner": policy.retry_policy.transport.owner,
        "transport_max_attempts": policy.retry_policy.transport.max_attempts,
        "litellm_num_retries_per_attempt": (
            policy.retry_policy.transport.litellm_num_retries_per_attempt
        ),
        "validation_owner": policy.retry_policy.validation.owner,
        "validation_max_attempts": policy.retry_policy.validation.max_attempts,
        "max_physical_provider_calls_per_action": (
            policy.retry_policy.hard_limits.max_physical_provider_calls_per_action
        ),
        "structured_output_mode": policy.structured_output_mode.value,
        "schema_version": policy.schema_version,
    }


def provider_policy_from_snapshot(
    provider_policy_ref: str, snapshot: Mapping[str, Any]
) -> ProviderPolicy:
    return ProviderPolicy(
        provider_policy_ref=provider_policy_ref,
        provider=str(snapshot["provider"]),
        model=str(snapshot["base_model"]),
        temperature=float(snapshot["temperature"]),
        timeout_seconds=int(snapshot["timeout_seconds"]),
        retry_policy=ProviderRetryPolicy(
            transport=ProviderTransportRetryPolicy(
                owner=str(snapshot["transport_owner"]),
                max_attempts=int(snapshot["transport_max_attempts"]),
                litellm_num_retries_per_attempt=int(snapshot["litellm_num_retries_per_attempt"]),
            ),
            validation=ProviderValidationRetryPolicy(
                owner=str(snapshot["validation_owner"]),
                max_attempts=int(snapshot["validation_max_attempts"]),
            ),
            hard_limits=ProviderRetryHardLimits(
                max_physical_provider_calls_per_action=int(
                    snapshot["max_physical_provider_calls_per_action"]
                )
            ),
        ),
        structured_output_mode=StructuredOutputMode(str(snapshot["structured_output_mode"])),
        schema_version=int(snapshot["schema_version"]),
    )


def _resolve_execution_definitions(
    registry: ConfigRegistry,
    *,
    scenario: ScenarioSessionRecord,
    job: JobRecord,
) -> tuple[Any, Any, Any, Any, Any, Any, Any]:
    scenario_definition = registry.get_scenario(scenario.scenario_id)
    if scenario_definition is None or not scenario_definition.internal_only:
        raise LookupError(f"Atom Lab scenario not found: {scenario.scenario_id}")
    if scenario_definition.version != scenario.scenario_version:
        raise ValueError("Atom Lab scenario version does not match the registry")
    workflow = registry.get_workflow(job.workflow_id)
    if workflow is None or workflow.workflow_id != scenario_definition.workflow_id:
        raise LookupError(f"Atom Lab workflow not found: {job.workflow_id}")
    if workflow.version != job.workflow_version or len(workflow.steps) != 1:
        raise ValueError("Atom Lab workflow version or shape is incompatible")
    step = workflow.steps[0]
    if step.input_mapping:
        raise ValueError("Atom Lab workflow must pass the complete payload")
    action_config = registry.get_action_configuration(step.action_config_id)
    if action_config is None:
        raise LookupError(f"action config not found: {step.action_config_id}")
    action = registry.get_action_definition(action_config.action_type)
    prompt = registry.get_prompt(action_config.prompt_ref)
    if action is None or prompt is None:
        raise LookupError("Atom Lab action or prompt is missing")
    input_schema = registry.get_schema(action.input_schema_ref)
    output_schema = registry.get_schema(action.output_schema_ref)
    if input_schema is None or output_schema is None:
        raise LookupError("Atom Lab schemas are missing")
    if (workflow.input_schema_ref, workflow.output_schema_ref) != (
        input_schema.schema_ref,
        output_schema.schema_ref,
    ):
        raise ValueError("Atom Lab workflow schemas do not match the action")
    return workflow, step, action_config, action, prompt, input_schema, output_schema


def _definition_bundle(**definitions: Any) -> dict[str, Any]:
    workflow = definitions["workflow"]
    step = definitions["step"]
    action = definitions["action"]
    action_config = definitions["action_config"]
    prompt = definitions["prompt"]
    input_schema = definitions["input_schema"]
    output_schema = definitions["output_schema"]
    return {
        "workflow": {
            "workflow_id": workflow.workflow_id,
            "version": workflow.version,
            "input_schema_ref": workflow.input_schema_ref,
            "output_schema_ref": workflow.output_schema_ref,
            "schema_version": workflow.schema_version,
            "metadata": _definition_metadata(workflow.metadata),
            "steps": [
                {
                    "step_id": step.step_id,
                    "action_config_id": step.action_config_id,
                    "input_mapping": _mutable_json(step.input_mapping),
                    "output_mapping": _mutable_json(step.output_mapping),
                    "when": step.when,
                    "retry_count": step.retry_count,
                    "schema_version": step.schema_version,
                    "metadata": _definition_metadata(step.metadata),
                }
            ],
        },
        "action": {
            "action_type": action.action_type,
            "version": action.version,
            "input_schema_ref": action.input_schema_ref,
            "output_schema_ref": action.output_schema_ref,
            "executor": action.executor.value,
            "cross_validator_ref": action.cross_validator_ref,
            "input_validator_ref": action.input_validator_ref,
            "emits_events": _mutable_json(action.emits_events),
            "description": action.description,
            "schema_version": action.schema_version,
            "metadata": _definition_metadata(action.metadata),
        },
        "action_config": {
            "action_config_id": action_config.action_config_id,
            "action_type": action_config.action_type,
            "prompt_ref": action_config.prompt_ref,
            "provider_policy_ref": action_config.provider_policy_ref,
            "schema_version": action_config.schema_version,
            "metadata": _definition_metadata(action_config.metadata),
        },
        "prompt": {
            "prompt_ref": prompt.prompt_ref,
            "version": prompt.version,
            "content": prompt.content,
            "input_variables": _mutable_json(prompt.input_variables),
            "output_schema_ref": prompt.output_schema_ref,
            "schema_version": prompt.schema_version,
            "metadata": _definition_metadata(prompt.metadata),
        },
        "input_schema": {
            "schema_ref": input_schema.schema_ref,
            "version": input_schema.version,
            "schema": _mutable_json(input_schema.schema),
            "schema_version": input_schema.schema_version,
            "metadata": _definition_metadata(input_schema.metadata),
        },
        "output_schema": {
            "schema_ref": output_schema.schema_ref,
            "version": output_schema.version,
            "schema": _mutable_json(output_schema.schema),
            "schema_version": output_schema.schema_version,
            "metadata": _definition_metadata(output_schema.metadata),
        },
    }


def _definition_hash(bundle: Mapping[str, Any]) -> str:
    encoded = json.dumps(bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _definition_metadata(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): _mutable_json(item)
        for key, item in value.items()
        if not str(key).startswith("_")
    }


def _mutable_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _mutable_json(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_mutable_json(item) for item in value]
    return value
