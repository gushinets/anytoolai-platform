from __future__ import annotations

from dataclasses import dataclass

from anytoolai_platform_core.artifacts.models import ArtifactRecord
from anytoolai_platform_core.artifacts.service import ArtifactService
from anytoolai_platform_core.providers.repository import ProviderCallRepository
from anytoolai_platform_core.structured_output.errors import (
    StructuredOutputError,
    StructuredOutputValidationError,
    to_safe_validation_error,
)
from anytoolai_platform_core.structured_output.validator import (
    StructuredOutputValidationResult,
    validate_structured_output,
)


@dataclass(frozen=True)
class StructuredOutputPersistenceContext:
    tenant_id: str
    region: str
    product_id: str
    frontend_id: str
    scenario_session_id: str
    job_id: str
    action_run_id: str
    handoff_id: str | None = None
    scenario_chain_id: str | None = None


@dataclass(frozen=True)
class StructuredOutputFinalizationResult:
    validation_result: StructuredOutputValidationResult
    artifact: ArtifactRecord


class StructuredOutputFinalizer:
    def __init__(
        self,
        *,
        artifact_service: ArtifactService,
        provider_call_repository: ProviderCallRepository | None = None,
    ) -> None:
        self._artifact_service = artifact_service
        self._provider_call_repository = provider_call_repository

    def finalize(
        self,
        raw_text: str,
        *,
        persistence_context: StructuredOutputPersistenceContext,
        schema: dict[str, object] | None,
        schema_ref: str | None = None,
        schema_version: int | None = None,
    ) -> StructuredOutputFinalizationResult:
        try:
            validation_result = validate_structured_output(
                raw_text,
                schema=schema,
                schema_ref=schema_ref,
                schema_version=schema_version,
            )
        except StructuredOutputError as exc:
            safe_error = to_safe_validation_error(exc)
            self.persist_debug_artifact(
                raw_text,
                persistence_context=persistence_context,
                safe_error=safe_error,
                schema_ref=schema_ref,
                schema_version=schema_version,
            )
            raise safe_error from exc

        artifact = self._artifact_service.create_structured_output_artifact(
            tenant_id=persistence_context.tenant_id,
            region=persistence_context.region,
            product_id=persistence_context.product_id,
            frontend_id=persistence_context.frontend_id,
            scenario_session_id=persistence_context.scenario_session_id,
            job_id=persistence_context.job_id,
            action_run_id=persistence_context.action_run_id,
            content_json=validation_result.normalized_output,
            metadata={
                "schema_ref": schema_ref,
                "schema_version": schema_version,
                "handoff_id": persistence_context.handoff_id,
                "scenario_chain_id": persistence_context.scenario_chain_id,
            },
        )
        return StructuredOutputFinalizationResult(
            validation_result=validation_result,
            artifact=artifact,
        )

    def persist_debug_artifact(
        self,
        raw_text: str,
        *,
        persistence_context: StructuredOutputPersistenceContext,
        safe_error: StructuredOutputValidationError,
        schema_ref: str | None = None,
        schema_version: int | None = None,
    ) -> ArtifactRecord:
        provider_call = (
            None
            if self._provider_call_repository is None
            else self._provider_call_repository.get_latest_for_action_run(
                persistence_context.action_run_id
            )
        )
        return self._artifact_service.create_structured_output_debug_artifact(
            tenant_id=persistence_context.tenant_id,
            region=persistence_context.region,
            product_id=persistence_context.product_id,
            frontend_id=persistence_context.frontend_id,
            scenario_session_id=persistence_context.scenario_session_id,
            job_id=persistence_context.job_id,
            action_run_id=persistence_context.action_run_id,
            raw_output_text=raw_text,
            metadata={
                "error_code": safe_error.code,
                "failure_kind": safe_error.failure_kind,
                "reason": safe_error.reason,
                "error_type": safe_error.error_type,
                "schema_ref": schema_ref,
                "schema_version": schema_version,
                "handoff_id": persistence_context.handoff_id,
                "scenario_chain_id": persistence_context.scenario_chain_id,
                "provider_call_id": None if provider_call is None else provider_call.id,
                "provider_policy_ref": (
                    None if provider_call is None else provider_call.provider_policy_ref
                ),
                "physical_call_index": (
                    None if provider_call is None else provider_call.physical_call_index
                ),
                "semantic_attempt_index": (
                    None if provider_call is None else provider_call.semantic_attempt_index
                ),
                "transport_attempt_index": (
                    None if provider_call is None else provider_call.transport_attempt_index
                ),
                "pydantic_run_id": (
                    None if provider_call is None else provider_call.pydantic_run_id
                ),
            },
        )
