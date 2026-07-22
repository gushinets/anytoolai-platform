from __future__ import annotations

import asyncio
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
from anytoolai_platform_core.artifacts.service import _emit_recovered_artifact_created_event
from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.events.replay import (
    ReplayTimestampSequencer,
    sequence_existing_replay_event,
)
from anytoolai_platform_core.providers.gateway import ProviderGatewayExecutionError
from anytoolai_platform_core.providers.gateway import _emit_recovered_provider_events
from anytoolai_platform_core.providers.repository import ProviderCallRepository
from anytoolai_platform_core.storage.transactions import (
    RollbackRecoveryPhase,
    register_rollback_recovery_callback,
    transaction_boundary,
)
from anytoolai_platform_core.structured_output.errors import StructuredOutputValidationError
from anytoolai_platform_core.structured_output.schemas import normalize_mapping, normalize_schema_mapping

_OUTPUT_ARTIFACT_ID_UNSET = object()


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
                    "scenario_chain_id": context.scenario_chain_id,
                    "handoff_id": context.handoff_id,
                    "acquisition_source": context.acquisition_source,
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
                    "scenario_chain_id": context.scenario_chain_id,
                    "handoff_id": context.handoff_id,
                    "acquisition_source": context.acquisition_source,
                },
                guest_id=context.guest_id,
                user_id=context.user_id,
            )
            response = await executor.execute(request, session=self._session)
        except asyncio.CancelledError as exc:
            self._persist_failed_action_run_for_exception(
                action_run,
                exc,
                provider_policy_ref=provider_policy.provider_policy_ref,
            )
            raise
        except Exception as exc:
            self._persist_failed_action_run_for_exception(
                action_run,
                exc,
                provider_policy_ref=provider_policy.provider_policy_ref,
            )
            raise

        output_artifact_id = self._validated_structured_output_artifact_id(
            response,
            action_run_id=action_run.id,
        )
        provider_call = response.provider_call
        succeeded = self._action_run_service.mark_succeeded(
            replace(
                action_run,
                status=ActionRunStatus.succeeded,
                output_artifact_id=output_artifact_id,
                completed_at=utc_now(),
                metadata={
                    **dict(action_run.metadata),
                    "llm_response_metadata": dict(response.metadata),
                    **(
                        {}
                        if output_artifact_id is None
                        else {"structured_output_artifact_id": output_artifact_id}
                    ),
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
        self._register_success_recovery(succeeded)
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

    def _validated_structured_output_artifact_id(
        self,
        response: ActionExecutorResponse,
        *,
        action_run_id: str,
    ) -> str | None:
        artifact_id = response.metadata.get("structured_output_artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id:
            return None
        artifact = self._artifact_repository.get(artifact_id)
        if artifact is None:
            return None
        if artifact.action_run_id != action_run_id:
            return None
        if artifact.artifact_type != "structured_output":
            return None
        return artifact.id

    def _latest_structured_output_artifact_id(self, action_run_id: str) -> str | None:
        artifact = self._artifact_repository.get_latest_structured_output_for_action_run(
            action_run_id
        )
        return None if artifact is None else artifact.id

    def _persist_failed_action_run_for_exception(
        self,
        action_run: ActionRunRecord,
        exc: BaseException,
        *,
        provider_policy_ref: str,
    ) -> None:
        error_code = self._error_code_for_exception(exc)
        metadata_updates = {
            "error_type": type(exc).__name__,
            "provider_policy_ref": provider_policy_ref,
        }
        output_artifact_id = self._latest_structured_output_artifact_id(action_run.id)
        failed_action_run = _build_failed_action_run_record(
            action_run,
            error_code=error_code,
            metadata_updates=metadata_updates,
            output_artifact_id=output_artifact_id,
        )
        self._register_failure_recovery(
            failed_action_run,
            error_code=error_code,
            metadata_updates=metadata_updates,
            output_artifact_id=output_artifact_id,
        )
        self._action_run_service.mark_failed(
            failed_action_run,
            error_code=error_code,
        )

    def _error_code_for_exception(self, exc: BaseException) -> str:
        if isinstance(exc, asyncio.CancelledError):
            return "action_execution_cancelled"
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

    def _register_failure_recovery(
        self,
        action_run: ActionRunRecord,
        *,
        error_code: str,
        metadata_updates: Mapping[str, Any],
        output_artifact_id: str | None,
    ) -> None:
        register_rollback_recovery_callback(
            self._session,
            lambda recovery_session_factory: _recover_failed_action_run_row_after_rollback(
                recovery_session_factory,
                action_run,
                error_code=error_code,
                metadata_updates=metadata_updates,
                output_artifact_id=output_artifact_id,
            ),
            phase=RollbackRecoveryPhase.action_rows,
        )
        register_rollback_recovery_callback(
            self._session,
            lambda recovery_session_factory: _recover_action_events_after_rollback(
                recovery_session_factory,
                action_run.id,
            ),
            phase=RollbackRecoveryPhase.action_events,
        )

    def _register_success_recovery(self, action_run: ActionRunRecord) -> None:
        register_rollback_recovery_callback(
            self._session,
            lambda recovery_session_factory: _recover_succeeded_action_run_row_after_rollback(
                recovery_session_factory,
                action_run,
            ),
            phase=RollbackRecoveryPhase.action_rows,
        )
        register_rollback_recovery_callback(
            self._session,
            lambda recovery_session_factory: _recover_action_events_after_rollback(
                recovery_session_factory,
                action_run.id,
            ),
            phase=RollbackRecoveryPhase.action_events,
        )


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
        output_artifact_id: str | None | object = _OUTPUT_ARTIFACT_ID_UNSET,
    ) -> ActionRunRecord:
        failed_record = _build_failed_action_run_record(
            record,
            error_code=error_code,
            metadata_updates=metadata_updates,
            output_artifact_id=output_artifact_id,
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
        scenario_chain_id=_metadata_str(record.metadata, "scenario_chain_id"),
        action_type=record.action_type,
        action_config_id=record.action_config_id,
        action_run_id=record.id,
        provider_policy_ref=_metadata_str(record.metadata, "provider_policy_ref"),
        handoff_id=_metadata_str(record.metadata, "handoff_id"),
        acquisition_source=_metadata_str(record.metadata, "acquisition_source"),
    )


def _metadata_str(metadata: Mapping[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) and value else None


def _metadata_int(metadata: Mapping[str, Any], key: str) -> int | None:
    value = metadata.get(key)
    return value if isinstance(value, int) else None


def _build_failed_action_run_record(
    record: ActionRunRecord,
    *,
    error_code: str,
    metadata_updates: Mapping[str, Any] | None = None,
    output_artifact_id: str | None | object = _OUTPUT_ARTIFACT_ID_UNSET,
) -> ActionRunRecord:
    resolved_output_artifact_id = (
        record.output_artifact_id
        if output_artifact_id is _OUTPUT_ARTIFACT_ID_UNSET
        else output_artifact_id
    )
    return replace(
        record,
        status=ActionRunStatus.failed,
        error_code=error_code,
        output_artifact_id=resolved_output_artifact_id,
        completed_at=record.completed_at or utc_now(),
        metadata={
            **dict(record.metadata),
            **({} if metadata_updates is None else dict(metadata_updates)),
        },
    )


def _recover_failed_action_run_row_after_rollback(
    recovery_session_factory: Any,
    record: ActionRunRecord,
    *,
    error_code: str,
    metadata_updates: Mapping[str, Any],
    output_artifact_id: str | None,
) -> None:
    with transaction_boundary(recovery_session_factory) as recovery_session:
        action_run_repository = ActionRunRepository(recovery_session)
        artifact_repository = ArtifactRepository(recovery_session)

        persisted_artifact_id = output_artifact_id
        if persisted_artifact_id is not None and artifact_repository.get(persisted_artifact_id) is None:
            persisted_artifact_id = None

        existing = action_run_repository.get(record.id)
        if existing is None:
            failed_record = _build_failed_action_run_record(
                record,
                error_code=error_code,
                metadata_updates=metadata_updates,
                output_artifact_id=persisted_artifact_id,
            )
            action_run_repository.create(failed_record)
            return

        action_run_repository.update(
            _build_failed_action_run_record(
                replace(
                    record,
                    started_at=existing.started_at or record.started_at,
                    created_at=existing.created_at,
                ),
                error_code=error_code,
                metadata_updates=metadata_updates,
                output_artifact_id=persisted_artifact_id,
            )
        )


def _recover_succeeded_action_run_row_after_rollback(
    recovery_session_factory: Any,
    record: ActionRunRecord,
) -> None:
    with transaction_boundary(recovery_session_factory) as recovery_session:
        action_run_repository = ActionRunRepository(recovery_session)
        artifact_repository = ArtifactRepository(recovery_session)

        persisted_artifact_id = record.output_artifact_id
        if (
            persisted_artifact_id is not None
            and artifact_repository.get(persisted_artifact_id) is None
        ):
            persisted_artifact_id = None

        recovered_record = replace(record, output_artifact_id=persisted_artifact_id)
        existing = action_run_repository.get(record.id)
        if existing is None:
            action_run_repository.create(recovered_record)
        else:
            action_run_repository.update(recovered_record)


def _recover_action_events_after_rollback(
    recovery_session_factory: Any,
    action_run_id: str,
) -> None:
    with transaction_boundary(recovery_session_factory) as recovery_session:
        _emit_recovered_action_events(
            EventLogRepository(recovery_session),
            action_run_id=action_run_id,
            action_run_repository=ActionRunRepository(recovery_session),
            provider_call_repository=ProviderCallRepository(recovery_session),
            artifact_repository=ArtifactRepository(recovery_session),
        )


def _emit_recovered_action_events(
    event_log_repository: EventLogRepository,
    *,
    action_run_id: str,
    action_run_repository: ActionRunRepository,
    provider_call_repository: ProviderCallRepository,
    artifact_repository: ArtifactRepository,
    timestamp_sequencer: ReplayTimestampSequencer | None = None,
) -> ActionRunRecord | None:
    action_run = action_run_repository.get(action_run_id)
    if action_run is None:
        return None

    event_emitter = EventEmitter(event_log_repository)
    started_event = event_log_repository.find_event(
        event_type="action.started",
        action_run_id=action_run.id,
    )
    if started_event is None:
        preferred_timestamp = action_run.started_at or action_run.created_at
        event_emitter.emit(
            "action.started",
            _context_from_record(action_run),
            timestamp=(
                preferred_timestamp
                if timestamp_sequencer is None
                else timestamp_sequencer.next(preferred_timestamp)
            ),
            replay=True,
        )
    elif timestamp_sequencer is not None:
        sequence_existing_replay_event(
            event_log_repository,
            timestamp_sequencer,
            started_event,
        )

    for provider_call in provider_call_repository.list_for_action_run(action_run.id):
        _emit_recovered_provider_events(
            event_log_repository,
            provider_call,
            timestamp_sequencer=timestamp_sequencer,
        )

    for artifact in artifact_repository.list_for_action_run(action_run.id):
        _emit_recovered_artifact_created_event(
            event_log_repository,
            artifact,
            timestamp_sequencer=timestamp_sequencer,
        )

    if action_run.status is ActionRunStatus.succeeded:
        succeeded_event = event_log_repository.find_event(
            event_type="action.succeeded",
            action_run_id=action_run.id,
        )
        if succeeded_event is None:
            preferred_timestamp = (
                action_run.completed_at or action_run.started_at or action_run.created_at
            )
            event_emitter.emit(
                "action.succeeded",
                _context_from_record(action_run),
                result_status=action_run.status.value,
                timestamp=(
                    preferred_timestamp
                    if timestamp_sequencer is None
                    else timestamp_sequencer.next(preferred_timestamp)
                ),
                replay=True,
            )
        elif timestamp_sequencer is not None:
            sequence_existing_replay_event(
                event_log_repository,
                timestamp_sequencer,
                succeeded_event,
            )
        return action_run

    if action_run.status is ActionRunStatus.failed:
        failed_event = event_log_repository.find_event(
            event_type="action.failed",
            action_run_id=action_run.id,
        )
        if failed_event is None:
            preferred_timestamp = (
                action_run.completed_at or action_run.started_at or action_run.created_at
            )
            event_emitter.emit(
                "action.failed",
                _context_from_record(action_run),
                result_status=action_run.status.value,
                properties={"error_code": action_run.error_code},
                timestamp=(
                    preferred_timestamp
                    if timestamp_sequencer is None
                    else timestamp_sequencer.next(preferred_timestamp)
                ),
                replay=True,
            )
        elif timestamp_sequencer is not None:
            sequence_existing_replay_event(
                event_log_repository,
                timestamp_sequencer,
                failed_event,
            )
    return action_run
