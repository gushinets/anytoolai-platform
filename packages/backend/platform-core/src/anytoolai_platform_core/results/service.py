from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from anytoolai_platform_core.artifacts.canonical import (
    CanonicalArtifactError,
    resolve_canonical_workflow_result,
)
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.workflows.repository import JobRepository


class ResultArtifactNotFoundError(PlatformError):
    def __init__(self) -> None:
        super().__init__("result_artifact_not_found", "Result artifact not found.")


class ResultArtifactUnavailableError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "result_artifact_unavailable", "Result artifact is not available."
        )


@dataclass(frozen=True)
class ResultArtifactView:
    artifact_id: str
    scenario_session_id: str
    job_id: str
    workflow_id: str
    workflow_version: int
    schema_ref: str
    schema_version: int
    created_at: datetime
    output: dict[str, Any]


class ResultService:
    def __init__(
        self,
        *,
        config_registry: ConfigRegistry,
        artifact_repository: ArtifactRepository,
        job_repository: JobRepository,
    ) -> None:
        self._registry = config_registry
        self._artifacts = artifact_repository
        self._jobs = job_repository

    def get_result(
        self,
        artifact_id: str,
        *,
        tenant_id: str,
        region: str,
    ) -> ResultArtifactView:
        artifact = self._artifacts.get_in_scope(
            artifact_id,
            tenant_id=tenant_id,
            region=region,
        )
        if artifact is None:
            raise ResultArtifactNotFoundError()
        job = None if artifact.job_id is None else self._jobs.get(artifact.job_id)
        try:
            canonical = resolve_canonical_workflow_result(
                artifact=artifact,
                job=job,
                config_registry=self._registry,
            )
        except CanonicalArtifactError as exc:
            raise ResultArtifactUnavailableError() from exc
        return ResultArtifactView(
            artifact_id=canonical.artifact.id,
            scenario_session_id=canonical.artifact.scenario_session_id,
            job_id=canonical.job.id,
            workflow_id=canonical.workflow.workflow_id,
            workflow_version=canonical.job.workflow_version,
            schema_ref=canonical.schema.schema_ref,
            schema_version=canonical.schema.version,
            created_at=canonical.artifact.created_at,
            output=canonical.normalized_output,
        )
