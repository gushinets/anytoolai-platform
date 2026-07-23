from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as validate_json_schema

from anytoolai_platform_core.artifacts.models import ArtifactStatus
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.handoffs.models import HandoffDefinition
from anytoolai_platform_core.scenarios.models import ScenarioSessionStatus
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.structured_output.errors import StructuredOutputError
from anytoolai_platform_core.structured_output.schemas import normalize_schema_mapping
from anytoolai_platform_core.structured_output.validator import (
    validate_structured_output_value,
)
from anytoolai_platform_core.workflows.models import JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository

PREVIEW_MAX_DEPTH = 4
PREVIEW_MAX_ITEMS = 20
PREVIEW_MAX_STRING_LENGTH = 512
PREVIEW_MAX_BYTES = 8192
TRUNCATED = "[TRUNCATED]"


class HandoffPayloadError(ValueError):
    pass


@dataclass(frozen=True)
class BuiltHandoffPayload:
    source_session: Any
    source_job: Any
    context_payload: dict[str, Any]
    preview_payload: dict[str, Any]


class HandoffPayloadBuilder:
    def __init__(
        self,
        *,
        config_registry: ConfigRegistry,
        session_repository: ScenarioSessionRepository,
        job_repository: JobRepository,
        artifact_repository: ArtifactRepository,
    ) -> None:
        self._registry = config_registry
        self._sessions = session_repository
        self._jobs = job_repository
        self._artifacts = artifact_repository

    def build(
        self,
        *,
        definition: HandoffDefinition,
        tenant_id: str,
        region: str,
        source_scenario_session_id: str,
        source_artifact_id: str,
    ) -> BuiltHandoffPayload:
        source_session = self._sessions.get_in_scope(
            source_scenario_session_id,
            tenant_id=tenant_id,
            region=region,
        )
        if source_session is None:
            raise HandoffPayloadError("source scenario session not found")
        if (
            source_session.product_id != definition.source_product_id
            or source_session.scenario_id != definition.source_scenario_id
            or source_session.status is not ScenarioSessionStatus.completed
        ):
            raise HandoffPayloadError("source scenario session is not ready for this handoff")
        source_job = self._jobs.get_latest_for_scenario_session(source_session.id)
        if (
            source_job is None
            or source_job.status is not JobStatus.succeeded
            or source_job.result_artifact_id != source_artifact_id
        ):
            raise HandoffPayloadError("source workflow result is not ready for handoff")
        source_workflow = self._registry.get_workflow(source_job.workflow_id)
        source_schema = (
            None
            if source_workflow is None
            else self._registry.get_schema(source_workflow.output_schema_ref)
        )
        artifact = self._artifacts.get(source_artifact_id)
        if (
            artifact is None
            or artifact.status is not ArtifactStatus.stored
            or artifact.artifact_type != "structured_output"
            or artifact.scenario_session_id != source_session.id
            or artifact.job_id != source_job.id
            or artifact.action_run_id is not None
            or artifact.metadata.get("artifact_role") != "workflow_result"
            or source_workflow is None
            or source_schema is None
            or artifact.metadata.get("workflow_id") != source_job.workflow_id
            or artifact.metadata.get("workflow_version") != source_job.workflow_version
            or artifact.metadata.get("schema_ref") != source_workflow.output_schema_ref
            or artifact.metadata.get("schema_version") != source_schema.version
            or not isinstance(artifact.content_json, Mapping)
        ):
            raise HandoffPayloadError("source artifact is not a canonical workflow result")

        try:
            validated_source = validate_structured_output_value(
                artifact.content_json,
                schema=source_schema.schema,
                schema_ref=source_schema.schema_ref,
                schema_version=source_schema.version,
            )
        except StructuredOutputError as exc:
            raise HandoffPayloadError(
                "source artifact is invalid for its workflow output schema"
            ) from exc
        normalized_artifact = validated_source.normalized_output
        assert isinstance(normalized_artifact, dict)
        context_payload = _apply_mapping(definition.context_mapping, normalized_artifact)
        preview_payload = _safe_preview(
            _apply_mapping(definition.preview_mapping, normalized_artifact)
        )
        target_scenario = self._registry.get_scenario(definition.target_scenario_id)
        if target_scenario is None:
            raise HandoffPayloadError("target scenario is unavailable")
        target_workflow = self._registry.get_workflow(target_scenario.workflow_id)
        if target_workflow is None:
            raise HandoffPayloadError("target workflow is unavailable")
        target_schema = self._registry.get_schema(target_workflow.input_schema_ref)
        if target_schema is None:
            raise HandoffPayloadError("target workflow input schema is unavailable")
        try:
            normalized_schema = normalize_schema_mapping(target_schema.schema)
            assert normalized_schema is not None
            validate_json_schema(instance=context_payload, schema=normalized_schema)
        except JsonSchemaValidationError as exc:
            raise HandoffPayloadError(
                "mapped handoff context is invalid for target workflow"
            ) from exc
        return BuiltHandoffPayload(
            source_session=source_session,
            source_job=source_job,
            context_payload=context_payload,
            preview_payload=preview_payload,
        )


def _apply_mapping(mapping: Mapping[str, str], artifact: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for target_path, source_path in mapping.items():
        parts = source_path.split(".")
        current: Any = artifact
        for segment in parts[2:]:
            if not isinstance(current, Mapping) or segment not in current:
                raise HandoffPayloadError(
                    f"handoff source path could not be resolved: {source_path}"
                )
            current = current[segment]
        _set_path(result, target_path, current)
    return result


def _set_path(target: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    if any(not part for part in parts):
        raise HandoffPayloadError(f"invalid handoff target path: {path}")
    current = target
    for part in parts[:-1]:
        child = current.setdefault(part, {})
        if not isinstance(child, dict):
            raise HandoffPayloadError(f"handoff target path collision: {path}")
        current = child
    current[parts[-1]] = value


def _safe_preview(value: dict[str, Any]) -> dict[str, Any]:
    sanitized = _sanitize_preview_value(value, depth=0)
    assert isinstance(sanitized, dict)
    encoded = json.dumps(sanitized, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > PREVIEW_MAX_BYTES:
        return {"summary": TRUNCATED}
    return sanitized


def _sanitize_preview_value(value: Any, *, depth: int) -> Any:
    if depth >= PREVIEW_MAX_DEPTH:
        return TRUNCATED
    if value is None or isinstance(value, (bool, int, float)):
        return "[UNSUPPORTED]" if isinstance(value, float) and not math.isfinite(value) else value
    if isinstance(value, str):
        return (
            value
            if len(value) <= PREVIEW_MAX_STRING_LENGTH
            else value[:PREVIEW_MAX_STRING_LENGTH] + TRUNCATED
        )
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_preview_value(item, depth=depth + 1)
            for key, item in list(value.items())[:PREVIEW_MAX_ITEMS]
        }
    if isinstance(value, (list, tuple)):
        return [
            _sanitize_preview_value(item, depth=depth + 1)
            for item in list(value)[:PREVIEW_MAX_ITEMS]
        ]
    return "[UNSUPPORTED]"
