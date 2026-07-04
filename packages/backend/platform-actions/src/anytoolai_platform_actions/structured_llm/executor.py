from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Any, Mapping

from sqlalchemy.orm import Session

from anytoolai_platform_core.artifacts.service import ArtifactService
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.providers.gateway import (
    ProviderGateway,
    ProviderGatewayExecutionError,
)
from anytoolai_platform_core.providers.models import ProviderRequest, ProviderResponse
from anytoolai_platform_core.providers.repository import ProviderCallRepository
from anytoolai_platform_core.structured_output.service import (
    StructuredOutputFinalizer,
    StructuredOutputPersistenceContext,
)
from anytoolai_platform_core.structured_output.errors import (
    StructuredOutputError,
    to_safe_validation_error,
)
from anytoolai_platform_core.structured_output.validator import (
    validate_structured_output,
)

from anytoolai_platform_actions.structured_llm.pydanticai_runner import (
    PydanticAIValidationExhaustedError,
    PydanticAIStructuredRunner,
)


@dataclass(frozen=True)
class StructuredLlmActionRequest:
    tenant_id: str
    region: str
    product_id: str
    frontend_id: str
    scenario_session_id: str
    job_id: str
    workflow_id: str
    workflow_version: int
    step_id: str
    action_run_id: str
    action_config_id: str
    input_payload: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fixture_key: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None


class StructuredLlmActionExecutor:
    """Generic structured-LLM executor that routes all model calls through ProviderGateway."""

    executor_id = "structured_llm"

    def __init__(
        self,
        *,
        config_registry: ConfigRegistry,
        provider_gateway: ProviderGateway,
        artifact_service: ArtifactService | None = None,
    ) -> None:
        self._config_registry = config_registry
        self._provider_gateway = provider_gateway
        self._structured_runner = PydanticAIStructuredRunner()
        self._artifact_service = artifact_service

    async def execute(
        self,
        request: StructuredLlmActionRequest,
        *,
        session: Session,
    ) -> ProviderResponse:
        action_config = self._require_action_config(request.action_config_id)
        action_definition = self._require_action_definition(action_config.action_type)
        prompt = self._require_prompt(action_config.prompt_ref)
        response_schema = self._config_registry.get_schema(
            action_definition.output_schema_ref
        )
        provider_request = ProviderRequest(
            provider_policy_ref=action_config.provider_policy_ref,
            tenant_id=request.tenant_id,
            region=request.region,
            product_id=request.product_id,
            frontend_id=request.frontend_id,
            scenario_session_id=request.scenario_session_id,
            job_id=request.job_id,
            workflow_id=request.workflow_id,
            workflow_version=request.workflow_version,
            step_id=request.step_id,
            action_run_id=request.action_run_id,
            action_type=action_config.action_type,
            action_config_id=request.action_config_id,
            prompt=self._render_prompt(prompt.content, request.input_payload),
            prompt_ref=prompt.prompt_ref,
            response_schema=None if response_schema is None else response_schema.schema,
            metadata=request.metadata,
            fixture_key=request.fixture_key,
            request_id=request.request_id,
            correlation_id=request.correlation_id,
        )
        provider_policy = self._require_provider_policy(action_config.provider_policy_ref)
        try:
            result = await self._structured_runner.run(
                provider_request,
                request_executor=lambda retry_request: self._provider_gateway.request(
                    retry_request,
                    session=session,
                ),
                validation_max_attempts=provider_policy.retry_policy.validation.max_attempts,
            )
        except PydanticAIValidationExhaustedError as exc:
            return self._finalize_response(
                response=exc.last_response,
                request=request,
                response_schema=response_schema,
                session=session,
            )
        return self._finalize_response(
            response=result.last_response,
            request=request,
            response_schema=response_schema,
            session=session,
        )

    def _require_action_config(self, action_config_id: str) -> Any:
        action_config = self._config_registry.get_action_configuration(action_config_id)
        if action_config is None:
            raise LookupError(f"action config not found: {action_config_id}")
        return action_config

    def _require_action_definition(self, action_type: str) -> Any:
        action_definition = self._config_registry.get_action_definition(action_type)
        if action_definition is None:
            raise LookupError(f"action definition not found: {action_type}")
        return action_definition

    def _require_prompt(self, prompt_ref: str) -> Any:
        prompt = self._config_registry.get_prompt(prompt_ref)
        if prompt is None:
            raise LookupError(f"prompt not found: {prompt_ref}")
        return prompt

    def _require_provider_policy(self, provider_policy_ref: str) -> Any:
        provider_policy = self._config_registry.get_provider_policy(provider_policy_ref)
        if provider_policy is None:
            raise LookupError(f"provider policy not found: {provider_policy_ref}")
        return provider_policy

    def _render_prompt(self, template: str, input_payload: Mapping[str, Any]) -> str:
        if not input_payload:
            return template
        serialized_payload = json.dumps(dict(input_payload), sort_keys=True)
        return f"{template}\n\nInput payload:\n{serialized_payload}"

    def _finalize_response(
        self,
        *,
        response: ProviderResponse,
        request: StructuredLlmActionRequest,
        response_schema: Any,
        session: Session,
    ) -> ProviderResponse:
        schema_mapping = None if response_schema is None else dict(response_schema.schema)
        if schema_mapping is None:
            return response
        if self._artifact_service is None:
            validation_result = None
            try:
                if schema_mapping is not None:
                    validation_result = validate_structured_output(
                        response.output_text,
                        schema=schema_mapping,
                        schema_ref=response_schema.schema_ref,
                        schema_version=response_schema.version,
                    )
            except StructuredOutputError as exc:
                raise to_safe_validation_error(exc) from exc
            return replace(
                response,
                structured_output=(
                    response.structured_output
                    if validation_result is None
                    else validation_result.normalized_output
                ),
            )

        finalizer = StructuredOutputFinalizer(
            artifact_service=self._artifact_service,
            provider_call_repository=ProviderCallRepository(session),
        )
        finalized = finalizer.finalize(
            response.output_text,
            persistence_context=StructuredOutputPersistenceContext(
                tenant_id=request.tenant_id,
                region=request.region,
                product_id=request.product_id,
                frontend_id=request.frontend_id,
                scenario_session_id=request.scenario_session_id,
                job_id=request.job_id,
                action_run_id=request.action_run_id,
            ),
            schema=schema_mapping,
            schema_ref=None if response_schema is None else response_schema.schema_ref,
            schema_version=None if response_schema is None else response_schema.version,
        )
        return replace(
            response,
            structured_output=finalized.validation_result.normalized_output,
            metadata={
                **dict(response.metadata),
                "structured_output_artifact_id": finalized.artifact.id,
            },
        )
