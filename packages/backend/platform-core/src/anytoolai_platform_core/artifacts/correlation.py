from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from anytoolai_platform_core.artifacts.models import ArtifactRecord
from anytoolai_platform_core.common.metadata import metadata_str
from anytoolai_platform_core.context.execution_context import ExecutionContext


def build_artifact_correlation_metadata(
    *,
    workflow_id: str | None = None,
    workflow_version: int | None = None,
    guest_id: str | None = None,
    user_id: str | None = None,
    scenario_chain_id: str | None = None,
    handoff_id: str | None = None,
    acquisition_source: str | None = None,
    action_type: str | None = None,
    action_config_id: str | None = None,
    schema_ref: str | None = None,
    schema_version: int | None = None,
    artifact_role: str | None = None,
    provider_call_id: str | None = None,
    provider_policy_ref: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    physical_call_index: int | None = None,
    semantic_attempt_index: int | None = None,
    transport_attempt_index: int | None = None,
    pydantic_run_id: str | None = None,
    litellm_response_id: str | None = None,
) -> dict[str, object]:
    metadata: dict[str, object] = {}
    _set_str(metadata, "workflow_id", workflow_id)
    _set_int(metadata, "workflow_version", workflow_version)
    _set_str(metadata, "guest_id", guest_id)
    _set_str(metadata, "user_id", user_id)
    _set_str(metadata, "scenario_chain_id", scenario_chain_id)
    _set_str(metadata, "handoff_id", handoff_id)
    _set_str(metadata, "acquisition_source", acquisition_source)
    _set_str(metadata, "action_type", action_type)
    _set_str(metadata, "action_config_id", action_config_id)
    _set_str(metadata, "schema_ref", schema_ref)
    _set_int(metadata, "schema_version", schema_version)
    _set_str(metadata, "artifact_role", artifact_role)
    _set_str(metadata, "provider_call_id", provider_call_id)
    _set_str(metadata, "provider_policy_ref", provider_policy_ref)
    _set_str(metadata, "provider", provider)
    _set_str(metadata, "model", model)
    _set_int(metadata, "physical_call_index", physical_call_index)
    _set_int(metadata, "semantic_attempt_index", semantic_attempt_index)
    _set_int(metadata, "transport_attempt_index", transport_attempt_index)
    _set_str(metadata, "pydantic_run_id", pydantic_run_id)
    _set_str(metadata, "litellm_response_id", litellm_response_id)
    return metadata


def artifact_execution_context_from_record(record: ArtifactRecord) -> ExecutionContext:
    return ExecutionContext(
        tenant_id=record.tenant_id,
        region=record.region,
        product_id=record.product_id,
        frontend_id=record.frontend_id,
        scenario_session_id=record.scenario_session_id,
        job_id=record.job_id,
        workflow_id=metadata_str(record.metadata, "workflow_id"),
        workflow_version=_metadata_int(record.metadata, "workflow_version"),
        guest_id=metadata_str(record.metadata, "guest_id"),
        user_id=metadata_str(record.metadata, "user_id"),
        scenario_chain_id=metadata_str(record.metadata, "scenario_chain_id"),
        action_type=metadata_str(record.metadata, "action_type"),
        action_config_id=metadata_str(record.metadata, "action_config_id"),
        artifact_id=record.id,
        handoff_id=metadata_str(record.metadata, "handoff_id"),
        acquisition_source=metadata_str(record.metadata, "acquisition_source"),
        action_run_id=record.action_run_id,
        provider_policy_ref=metadata_str(record.metadata, "provider_policy_ref"),
        provider_call_id=metadata_str(record.metadata, "provider_call_id"),
        provider=metadata_str(record.metadata, "provider"),
        model=metadata_str(record.metadata, "model"),
        physical_call_index=_metadata_int(record.metadata, "physical_call_index"),
        pydantic_run_id=metadata_str(record.metadata, "pydantic_run_id"),
        litellm_response_id=metadata_str(record.metadata, "litellm_response_id"),
    )


def _metadata_int(metadata: Mapping[str, Any], key: str) -> int | None:
    value = metadata.get(key)
    return value if isinstance(value, int) else None


def _set_str(metadata: dict[str, object], key: str, value: str | None) -> None:
    if isinstance(value, str) and value:
        metadata[key] = value


def _set_int(metadata: dict[str, object], key: str, value: int | None) -> None:
    if isinstance(value, int):
        metadata[key] = value
