from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from anytoolai_platform_core.artifacts.models import ArtifactRecord, ArtifactStatus
from anytoolai_platform_core.config.registry import ConfigRegistry, SchemaDefinition
from anytoolai_platform_core.structured_output.errors import StructuredOutputError
from anytoolai_platform_core.structured_output.validator import (
    validate_structured_output_value,
)
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus, WorkflowDefinition

CANONICAL_WORKFLOW_RESULT_ARTIFACT_TYPE = "structured_output"
CANONICAL_WORKFLOW_RESULT_ARTIFACT_ROLE = "workflow_result"


class CanonicalArtifactError(ValueError):
    """The artifact is not an available frontend-safe canonical workflow result."""


@dataclass(frozen=True)
class CanonicalWorkflowResult:
    artifact: ArtifactRecord
    job: JobRecord
    workflow: WorkflowDefinition
    schema: SchemaDefinition
    normalized_output: dict[str, Any]


def resolve_canonical_workflow_result(
    *,
    artifact: ArtifactRecord | None,
    job: JobRecord | None,
    config_registry: ConfigRegistry,
) -> CanonicalWorkflowResult:
    """Guard and re-validate a stored artifact as a frontend-safe canonical workflow result.

    Shared by the handoffs payload builder and the results API so both consumers reject
    raw/debug artifacts, stale job/workflow/schema pairings, and schema-invalid content the
    same way.
    """
    workflow = None if job is None else config_registry.get_workflow(job.workflow_id)
    schema = None if workflow is None else config_registry.get_schema(workflow.output_schema_ref)
    if (
        artifact is None
        or job is None
        or job.status is not JobStatus.succeeded
        or job.result_artifact_id != artifact.id
        or artifact.status is not ArtifactStatus.stored
        or artifact.artifact_type != CANONICAL_WORKFLOW_RESULT_ARTIFACT_TYPE
        or artifact.scenario_session_id != job.scenario_session_id
        or artifact.job_id != job.id
        or artifact.action_run_id is not None
        or artifact.metadata.get("artifact_role") != CANONICAL_WORKFLOW_RESULT_ARTIFACT_ROLE
        or workflow is None
        or schema is None
        or artifact.metadata.get("workflow_id") != job.workflow_id
        or artifact.metadata.get("workflow_version") != job.workflow_version
        or artifact.metadata.get("schema_ref") != workflow.output_schema_ref
        or artifact.metadata.get("schema_version") != schema.version
        or not isinstance(artifact.content_json, Mapping)
    ):
        raise CanonicalArtifactError("artifact is not a canonical workflow result")

    try:
        validated = validate_structured_output_value(
            artifact.content_json,
            schema=schema.schema,
            schema_ref=schema.schema_ref,
            schema_version=schema.version,
        )
    except StructuredOutputError as exc:
        raise CanonicalArtifactError(
            "artifact is invalid for its workflow output schema"
        ) from exc
    normalized_output = validated.normalized_output
    assert isinstance(normalized_output, dict)
    return CanonicalWorkflowResult(
        artifact=artifact,
        job=job,
        workflow=workflow,
        schema=schema,
        normalized_output=normalized_output,
    )
