from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as validate_json_schema
from sqlalchemy.orm import Session

from anytoolai_platform_core.actions.executor import (
    ActionExecutor,
    ActionExecutorRequest,
    ActionExecutorResponse,
)
from anytoolai_platform_core.actions.models import ActionResult, ActionRunRecord, ActionRunStatus
from anytoolai_platform_core.actions.repository import ActionRunRepository
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.providers.gateway import ProviderGatewayExecutionError
from anytoolai_platform_core.structured_output.errors import StructuredOutputValidationError
from anytoolai_platform_core.structured_output.schemas import normalize_mapping, normalize_schema_mapping


class ActionInputValidationError(PlatformError):
    def __init__(self, message: str = "Action input validation failed.") -> None:
        super().__init__("action_input_validation_failed", message)


class ActionRunner:
    def __init__(
        self,
        *,
        session: Session,
        config_registry: ConfigRegistry,
        action_run_service: ActionRunService,
        executors: Mapping[str, ActionExecutor],
        artifact_repository: ArtifactRepository | None = None,
    ) -> None:
        self._session = session
        self._config_registry = config_registry
        self._action_run_service = action_run_service
        self._executors = dict(executors)
        self._artifact_repository = artifact_repository or ArtifactRepository(session)

    async def run(
        self,
        action_type: str,
        action_config_id: str,
        input_payload: Mapping[str, Any],
        context: ExecutionContext,
    ) -> ActionResult:
        action_config = self._require_action_config(action_config_id)
        if action_config.action_type != action_type:
            raise LookupError(
                "action config type mismatch: "
                f"{action_config_id} -> {action_config.action_type} != {action_type}"
            )
        action_definition = self._require_action_definition(action_type)
        provider_policy = self._require_provider_policy(action_config.provider_policy_ref)
        prompt = self._require_prompt(action_config.prompt_ref)
        input_schema = self._require_schema(action_definition.input_schema_ref)
        output_schema = self._require_schema(action_definition.output_schema_ref)
        workflow_version = self._require_workflow_version(context.workflow_version)

        now = utc_now()
        action_run = self._action_run_service.start(
            ActionRunRecord(
                tenant_id=context.tenant_id,
                region=context.region,
                product_id=context.product_id,
                frontend_id=context.frontend_id,
                scenario_session_id=self._require_context(context.scenario_session_id, "scenario_session_id"),
                job_id=self._require_context(context.job_id, "job_id"),
                workflow_id=self._require_context(context.workflow_id, "workflow_id"),
                step_id=self._require_context(context.step_id, "step_id"),
                action_type=action_type,
                action_config_id=action_config_id,
                status=ActionRunStatus.running,
                started_at=now,
                metadata={
                    "workflow_version": workflow_version,
                    "guest_id": context.guest_id,
                    "user_id": context.user_id,
                    "provider_policy_ref": provider_policy.provider_policy_ref,
                    "prompt_ref": prompt.prompt_ref,
                    "input_schema_ref": input_schema.schema_ref,
                    "output_schema_ref": output_schema.schema_ref,
                },
            )
        )

        try:
            self._validate_input_payload(
                input_payload,
                schema=input_schema.schema,
                schema_ref=input_schema.schema_ref,
            )
            executor = self._resolve_executor(action_definition.executor.value)
            request = ActionExecutorRequest(
                tenant_id=context.tenant_id,
                region=context.region,
                product_id=context.product_id,
                frontend_id=context.frontend_id,
                scenario_session_id=action_run.scenario_session_id,
                job_id=action_run.job_id,
                workflow_id=action_run.workflow_id,
                workflow_version=workflow_version,
                step_id=action_run.step_id,
                action_run_id=action_run.id,
                action_type=action_type,
                action_config_id=action_config_id,
                input_payload=normalize_mapping(dict(input_payload)),
                metadata={
                    "guest_id": context.guest_id,
                    "user_id": context.user_id,
                },
                guest_id=context.guest_id,
                user_id=context.user_id,
            )
            response = await executor.execute(request, session=self._session)
        except Exception as exc:
            self._action_run_service.mark_failed(
                action_run,
                error_code=self._error_code_for_exception(exc),
                metadata_updates={
                    "error_type": type(exc).__name__,
                    "provider_policy_ref": provider_policy.provider_policy_ref,
                },
                output_artifact_id=self._latest_artifact_id(action_run.id),
            )
            raise

        output_artifact_id = self._artifact_id_from_response(response)
        provider_call = response.provider_call
        succeeded = self._action_run_service.mark_succeeded(
            replace(
                action_run,
                status=ActionRunStatus.succeeded,
                output_artifact_id=output_artifact_id,
                completed_at=utc_now(),
                metadata={
                    **dict(action_run.metadata),
                    "structured_output_artifact_id": output_artifact_id,
                    "llm_response_metadata": dict(response.metadata),
                    **(
                        {}
                        if provider_call is None
                        else {
                            "provider_policy_ref": provider_call.provider_policy_ref,
                            "provider": provider_call.provider,
                            "model": provider_call.model,
                        }
                    ),
                },
            )
        )
        return ActionResult(
            action_run_id=succeeded.id,
            action_type=action_type,
            action_config_id=action_config_id,
            status=succeeded.status,
            output_payload=(
                normalize_mapping(response.structured_output)
                if isinstance(response.structured_output, dict)
                else response.structured_output
            ),
            output_artifact_id=output_artifact_id,
            provider_policy_ref=(
                None if provider_call is None else provider_call.provider_policy_ref
            ),
            provider=None if provider_call is None else provider_call.provider,
            model=None if provider_call is None else provider_call.model,
            metadata={
                "prompt_ref": prompt.prompt_ref,
                "input_schema_ref": input_schema.schema_ref,
                "output_schema_ref": output_schema.schema_ref,
                "response_metadata": dict(response.metadata),
            },
        )

    def _resolve_executor(self, executor_id: str) -> ActionExecutor:
        try:
            return self._executors[executor_id]
        except KeyError as exc:
            raise LookupError(f"action executor not found: {executor_id}") from exc

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

    def _require_provider_policy(self, provider_policy_ref: str) -> Any:
        provider_policy = self._config_registry.get_provider_policy(provider_policy_ref)
        if provider_policy is None:
            raise LookupError(f"provider policy not found: {provider_policy_ref}")
        return provider_policy

    def _require_prompt(self, prompt_ref: str) -> Any:
        prompt = self._config_registry.get_prompt(prompt_ref)
        if prompt is None:
            raise LookupError(f"prompt not found: {prompt_ref}")
        return prompt

    def _require_schema(self, schema_ref: str) -> Any:
        schema = self._config_registry.get_schema(schema_ref)
        if schema is None:
            raise LookupError(f"schema not found: {schema_ref}")
        return schema

    def _validate_input_payload(
        self,
        input_payload: Mapping[str, Any],
        *,
        schema: Mapping[str, Any] | None,
        schema_ref: str,
    ) -> None:
        normalized_schema = normalize_schema_mapping(schema)
        if normalized_schema is None:
            return
        normalized_input = normalize_mapping(dict(input_payload))
        try:
            validate_json_schema(instance=normalized_input, schema=normalized_schema)
        except JsonSchemaValidationError as exc:
            raise ActionInputValidationError(
                f"Action input validation failed for {schema_ref}."
            ) from exc

    def _artifact_id_from_response(self, response: ActionExecutorResponse) -> str | None:
        artifact_id = response.metadata.get("structured_output_artifact_id")
        return artifact_id if isinstance(artifact_id, str) and artifact_id else None

    def _latest_artifact_id(self, action_run_id: str) -> str | None:
        artifact = self._artifact_repository.get_latest_for_action_run(action_run_id)
        return None if artifact is None else artifact.id

    def _error_code_for_exception(self, exc: Exception) -> str:
        if isinstance(exc, PlatformError):
            return exc.code
        if isinstance(exc, ProviderGatewayExecutionError):
            return exc.error_code
        if isinstance(exc, StructuredOutputValidationError):
            return exc.code
        return "action_execution_failed"

    def _require_context(self, value: str | None, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"missing required action context: {field_name}")
        return value

    def _require_workflow_version(self, value: int | None) -> int:
        if not isinstance(value, int):
            raise ValueError("missing required action context: workflow_version")
        return value


class ActionRunService:
    def __init__(self, repository: ActionRunRepository, event_emitter: EventEmitter) -> None:
        self._repository = repository
        self._event_emitter = event_emitter

    def start(self, record: ActionRunRecord) -> ActionRunRecord:
        stored = self._repository.create(record)
        self._event_emitter.emit("action.started", _context_from_record(stored))
        return stored

    def mark_succeeded(self, record: ActionRunRecord) -> ActionRunRecord:
        updated = self._repository.update(record)
        self._event_emitter.emit(
            "action.succeeded",
            _context_from_record(updated),
            result_status=updated.status.value,
        )
        return updated

    def mark_failed(
        self,
        record: ActionRunRecord,
        *,
        error_code: str,
        metadata_updates: Mapping[str, Any] | None = None,
        output_artifact_id: str | None = None,
    ) -> ActionRunRecord:
        failed_record = replace(
            record,
            status=ActionRunStatus.failed,
            error_code=error_code,
            output_artifact_id=output_artifact_id or record.output_artifact_id,
            completed_at=utc_now(),
            metadata={
                **dict(record.metadata),
                **({} if metadata_updates is None else dict(metadata_updates)),
            },
        )
        updated = self._repository.update(failed_record)
        self._event_emitter.emit(
            "action.failed",
            _context_from_record(updated),
            result_status=updated.status.value,
            properties={"error_code": error_code},
        )
        return updated


def _context_from_record(record: ActionRunRecord) -> ExecutionContext:
    return ExecutionContext(
        tenant_id=record.tenant_id,
        region=record.region,
        product_id=record.product_id,
        frontend_id=record.frontend_id,
        scenario_session_id=record.scenario_session_id,
        job_id=record.job_id,
        workflow_id=record.workflow_id,
        workflow_version=_metadata_int(record.metadata, "workflow_version"),
        step_id=record.step_id,
        guest_id=_metadata_str(record.metadata, "guest_id"),
        user_id=_metadata_str(record.metadata, "user_id"),
        action_type=record.action_type,
        action_config_id=record.action_config_id,
        action_run_id=record.id,
        provider_policy_ref=_metadata_str(record.metadata, "provider_policy_ref"),
    )


def _metadata_str(metadata: Mapping[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) and value else None


def _metadata_int(metadata: Mapping[str, Any], key: str) -> int | None:
    value = metadata.get(key)
    return value if isinstance(value, int) else None
