from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

import sqlalchemy as sa
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as validate_json_schema
from sqlalchemy.orm import Session

from anytoolai_platform_core.actions.models import ActionRunRecord, ActionRunStatus
from anytoolai_platform_core.actions.repository import ActionRunRepository
from anytoolai_platform_core.actions.runner import ActionRunner
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.artifacts.service import ArtifactService
from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter, enrich_event_context
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.storage.db import action_runs_table
from anytoolai_platform_core.storage.transactions import (
    register_rollback_recovery_callback,
    transaction_boundary,
)
from anytoolai_platform_core.structured_output.schemas import normalize_mapping, normalize_schema_mapping
from anytoolai_platform_core.workflows.errors import (
    WorkflowExecutionError,
    WorkflowInputValidationError,
    WorkflowOutputValidationError,
)
from anytoolai_platform_core.workflows.mappings import (
    apply_output_mapping,
    resolve_step_input,
    resolve_when_condition,
)
from anytoolai_platform_core.workflows.models import (
    JobRecord,
    JobStatus,
    WorkflowDefinition,
    WorkflowRunResult,
    WorkflowStepDefinition,
)
from anytoolai_platform_core.workflows.repository import JobRepository


class WorkflowJobService:
    def __init__(self, repository: JobRepository, event_emitter: EventEmitter) -> None:
        self._repository = repository
        self._event_emitter = event_emitter

    def start(self, record: JobRecord) -> JobRecord:
        stored = self._repository.create(record)
        self._event_emitter.emit(
            "workflow.started",
            _context_from_record(stored),
            properties={"workflow_version": stored.workflow_version},
        )
        return stored

    def mark_succeeded(self, record: JobRecord) -> JobRecord:
        updated = self._repository.update(record)
        self._event_emitter.emit(
            "workflow.succeeded",
            _context_from_record(updated),
            result_status=updated.status.value,
            properties={"workflow_version": updated.workflow_version},
        )
        return updated

    def mark_failed(self, record: JobRecord, *, error_code: str) -> JobRecord:
        failed_record = replace(record, status=JobStatus.failed, error_code=error_code)
        updated = self._repository.update(failed_record)
        self._event_emitter.emit(
            "workflow.failed",
            _context_from_record(updated),
            result_status=updated.status.value,
            properties={
                "error_code": error_code,
                "workflow_version": updated.workflow_version,
            },
        )
        return updated


class SequentialWorkflowRunner:
    def __init__(
        self,
        *,
        session: Session,
        config_registry: ConfigRegistry,
        job_service: WorkflowJobService,
        action_runner: ActionRunner,
        artifact_service: ArtifactService,
        event_emitter: EventEmitter,
        job_repository: JobRepository | None = None,
        action_run_repository: ActionRunRepository | None = None,
    ) -> None:
        self._session = session
        self._config_registry = config_registry
        self._job_service = job_service
        self._action_runner = action_runner
        self._artifact_service = artifact_service
        self._event_emitter = event_emitter
        self._job_repository = job_repository or JobRepository(session)
        self._action_run_repository = action_run_repository or ActionRunRepository(session)

    async def run(
        self,
        workflow_id: str,
        input_payload: Mapping[str, Any],
        context: ExecutionContext,
    ) -> WorkflowRunResult:
        workflow = self._require_workflow(workflow_id)
        normalized_input = normalize_mapping(dict(input_payload))
        now = utc_now()
        job = self._job_service.start(
            JobRecord(
                tenant_id=context.tenant_id,
                region=context.region,
                product_id=context.product_id,
                frontend_id=context.frontend_id,
                scenario_session_id=self._require_context(
                    context.scenario_session_id, "scenario_session_id"
                ),
                workflow_id=workflow.workflow_id,
                workflow_version=workflow.version,
                status=JobStatus.running,
                started_at=now,
                metadata={
                    "guest_id": context.guest_id,
                    "user_id": context.user_id,
                    "scenario_chain_id": context.scenario_chain_id,
                    "handoff_id": context.handoff_id,
                    "acquisition_source": context.acquisition_source,
                    "input_schema_ref": workflow.input_schema_ref,
                    "output_schema_ref": workflow.output_schema_ref,
                    "workflow_state": {
                        "steps": {},
                        "context": {},
                    },
                },
            )
        )

        state = _WorkflowExecutionState(
            scenario_input=normalized_input,
            step_outputs={},
            context={},
            step_state={},
        )
        job_context = ExecutionContext(
            tenant_id=context.tenant_id,
            region=context.region,
            product_id=context.product_id,
            frontend_id=context.frontend_id,
            scenario_session_id=job.scenario_session_id,
            job_id=job.id,
            workflow_id=workflow.workflow_id,
            workflow_version=workflow.version,
            guest_id=context.guest_id,
            user_id=context.user_id,
            scenario_chain_id=context.scenario_chain_id,
            handoff_id=context.handoff_id,
            acquisition_source=context.acquisition_source,
        )

        try:
            self._validate_workflow_input(
                workflow,
                normalized_input,
                schema_ref=workflow.input_schema_ref,
            )
            for step in workflow.steps:
                job = await self._run_step(
                    workflow=workflow,
                    step=step,
                    job=job,
                    job_context=job_context,
                    state=state,
                )

            final_payload, final_source = self._select_final_output(state)
            final_artifact = self._create_final_artifact(
                workflow=workflow,
                job=job,
                payload=final_payload,
            )
            state.final_output_source = final_source
            state.result_artifact_id = final_artifact.id
            job = self._persist_job_state(
                replace(
                    job,
                    status=JobStatus.succeeded,
                    result_artifact_id=final_artifact.id,
                    completed_at=utc_now(),
                ),
                state,
            )
            job = self._job_service.mark_succeeded(job)
            return WorkflowRunResult(
                job_id=job.id,
                workflow_id=job.workflow_id,
                workflow_version=job.workflow_version,
                status=job.status,
                output_payload=final_payload,
                result_artifact_id=final_artifact.id,
                metadata={"workflow_state": self._workflow_state_metadata(state)},
            )
        except Exception as exc:
            error_code = self._error_code_for_exception(exc)
            failed_job = self._build_failed_job_record(
                job,
                state,
                error_code=error_code,
                error_message_safe=self._safe_error_message_for_exception(exc),
            )
            self._register_failure_recovery(
                failed_job,
                error_code=error_code,
                failed_step=state.failed_step,
            )
            job = self._job_service.mark_failed(failed_job, error_code=error_code)
            raise

    async def _run_step(
        self,
        *,
        workflow: WorkflowDefinition,
        step: WorkflowStepDefinition,
        job: JobRecord,
        job_context: ExecutionContext,
        state: "_WorkflowExecutionState",
    ) -> JobRecord:
        action_config = self._require_action_config(step.action_config_id)
        step_event_context = enrich_event_context(
            job_context,
            step_id=step.step_id,
            action_type=action_config.action_type,
            action_config_id=step.action_config_id,
        )
        if step.when is not None:
            try:
                should_run = resolve_when_condition(
                    step.when,
                    scenario_input=state.scenario_input,
                    step_outputs=state.step_outputs,
                    context=state.context,
                )
            except Exception as exc:
                self._remember_failed_step(
                    state,
                    step=step,
                    action_type=action_config.action_type,
                    attempt_count=0,
                    error_code=self._error_code_for_exception(exc),
                    action_run_id=None,
                )
                self._emit_step_failed(
                    step_event_context,
                    step=step,
                    attempt_count=0,
                    error_code=self._error_code_for_exception(exc),
                    action_run_id=None,
                )
                raise
            if not should_run:
                skip_reason = f"`when` path `{step.when}` resolved to a falsy value."
                skipped_action_run = self._persist_skipped_action_run(
                    job=job,
                    workflow=workflow,
                    step=step,
                    action_type=action_config.action_type,
                    guest_id=job.metadata.get("guest_id"),
                    user_id=job.metadata.get("user_id"),
                    skip_reason=skip_reason,
                )
                state.step_state[step.step_id] = {
                    "status": ActionRunStatus.skipped.value,
                    "attempt_count": 0,
                    "last_action_run_id": skipped_action_run.id,
                    "output_artifact_id": None,
                    "skip_reason": skip_reason,
                }
                job = self._persist_job_state(job, state)
                self._event_emitter.emit(
                    "workflow.step_skipped",
                    enrich_event_context(step_event_context, action_run_id=skipped_action_run.id),
                    result_status=ActionRunStatus.skipped.value,
                    properties={
                        "step_id": step.step_id,
                        "retry_count": step.retry_count,
                        "skip_reason": skip_reason,
                    },
                )
                return job

        self._event_emitter.emit(
            "workflow.step_started",
            step_event_context,
            properties={
                "step_id": step.step_id,
                "retry_count": step.retry_count,
            },
        )

        try:
            step_input = resolve_step_input(
                input_mapping=step.input_mapping,
                scenario_input=state.scenario_input,
                step_outputs=state.step_outputs,
                context=state.context,
            )
        except Exception as exc:
            self._remember_failed_step(
                state,
                step=step,
                action_type=action_config.action_type,
                attempt_count=0,
                error_code=self._error_code_for_exception(exc),
                action_run_id=None,
            )
            self._emit_step_failed(
                step_event_context,
                step=step,
                attempt_count=0,
                error_code=self._error_code_for_exception(exc),
                action_run_id=None,
            )
            raise

        for attempt_index in range(1, step.retry_count + 2):
            action_context = step_event_context
            try:
                result = await self._action_runner.run(
                    action_config.action_type,
                    step.action_config_id,
                    step_input,
                    action_context,
                )
            except Exception as exc:
                last_action_run_id = self._latest_action_run_id(job.id, step.step_id)
                state.step_state[step.step_id] = {
                    "status": ActionRunStatus.failed.value,
                    "attempt_count": attempt_index,
                    "last_action_run_id": last_action_run_id,
                    "output_artifact_id": None,
                    "skip_reason": None,
                    "error_code": self._error_code_for_exception(exc),
                }
                job = self._persist_job_state(job, state)
                if attempt_index <= step.retry_count:
                    continue

                self._remember_failed_step(
                    state,
                    step=step,
                    action_type=action_config.action_type,
                    attempt_count=attempt_index,
                    error_code=self._error_code_for_exception(exc),
                    action_run_id=last_action_run_id,
                )
                self._emit_step_failed(
                    step_event_context,
                    step=step,
                    attempt_count=attempt_index,
                    error_code=self._error_code_for_exception(exc),
                    action_run_id=last_action_run_id,
                )
                raise

            state.step_outputs[step.step_id] = _normalize_output_payload(result.output_payload)
            try:
                applied_outputs = apply_output_mapping(
                    step.output_mapping,
                    step_id=step.step_id,
                    step_output=state.step_outputs[step.step_id],
                    context=state.context,
                )
            except Exception as exc:
                state.step_state[step.step_id] = {
                    "status": ActionRunStatus.failed.value,
                    "attempt_count": attempt_index,
                    "last_action_run_id": result.action_run_id,
                    "output_artifact_id": result.output_artifact_id,
                    "skip_reason": None,
                    "error_code": self._error_code_for_exception(exc),
                }
                job = self._persist_job_state(job, state)
                self._remember_failed_step(
                    state,
                    step=step,
                    action_type=action_config.action_type,
                    attempt_count=attempt_index,
                    error_code=self._error_code_for_exception(exc),
                    action_run_id=result.action_run_id,
                )
                self._emit_step_failed(
                    step_event_context,
                    step=step,
                    attempt_count=attempt_index,
                    error_code=self._error_code_for_exception(exc),
                    action_run_id=result.action_run_id,
                )
                raise
            state.last_successful_step_id = step.step_id
            state.last_successful_output = state.step_outputs[step.step_id]
            state.last_successful_output_artifact_id = result.output_artifact_id
            state.step_state[step.step_id] = {
                "status": result.status.value,
                "attempt_count": attempt_index,
                "last_action_run_id": result.action_run_id,
                "output_artifact_id": result.output_artifact_id,
                "skip_reason": None,
                "output_mapping_applied": applied_outputs,
            }
            job = self._persist_job_state(job, state)
            artifact_context = (
                step_event_context
                if result.output_artifact_id is None
                else enrich_event_context(step_event_context, artifact_id=result.output_artifact_id)
            )
            self._event_emitter.emit(
                "workflow.step_succeeded",
                enrich_event_context(artifact_context, action_run_id=result.action_run_id),
                result_status=result.status.value,
                properties={
                    "step_id": step.step_id,
                    "retry_count": step.retry_count,
                    "attempt_count": attempt_index,
                    "output_artifact_id": result.output_artifact_id,
                },
            )
            return job

    def _create_final_artifact(
        self,
        *,
        workflow: WorkflowDefinition,
        job: JobRecord,
        payload: dict[str, Any],
    ) -> Any:
        self._validate_workflow_output(
            workflow,
            payload,
            schema_ref=workflow.output_schema_ref,
        )
        return self._artifact_service.create_structured_output_artifact(
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
            scenario_session_id=job.scenario_session_id,
            job_id=job.id,
            action_run_id=None,
            content_json=payload,
            metadata={
                "schema_ref": workflow.output_schema_ref,
                "schema_version": self._schema_version(workflow.output_schema_ref),
                "workflow_id": workflow.workflow_id,
                "workflow_version": workflow.version,
                "artifact_role": "workflow_result",
            },
        )

    def _select_final_output(
        self,
        state: "_WorkflowExecutionState",
    ) -> tuple[dict[str, Any], str]:
        workflow_output = state.context.get("workflow_output")
        if isinstance(workflow_output, Mapping):
            return normalize_mapping(workflow_output), "context.workflow_output"
        if isinstance(state.last_successful_output, Mapping):
            assert state.last_successful_step_id is not None
            return (
                normalize_mapping(state.last_successful_output),
                f"steps.{state.last_successful_step_id}.output",
            )
        raise WorkflowOutputValidationError(
            "Workflow did not produce a final object output for artifact creation."
        )

    def _persist_skipped_action_run(
        self,
        *,
        job: JobRecord,
        workflow: WorkflowDefinition,
        step: WorkflowStepDefinition,
        action_type: str,
        guest_id: Any,
        user_id: Any,
        skip_reason: str,
    ) -> ActionRunRecord:
        now = utc_now()
        return self._action_run_repository.create(
            ActionRunRecord(
                tenant_id=job.tenant_id,
                region=job.region,
                product_id=job.product_id,
                frontend_id=job.frontend_id,
                scenario_session_id=job.scenario_session_id,
                job_id=job.id,
                workflow_id=workflow.workflow_id,
                step_id=step.step_id,
                action_type=action_type,
                action_config_id=step.action_config_id,
                status=ActionRunStatus.skipped,
                started_at=now,
                completed_at=now,
                metadata={
                    "workflow_version": workflow.version,
                    "guest_id": guest_id,
                    "user_id": user_id,
                    "skip_reason": skip_reason,
                },
            )
        )

    def _persist_job_state(
        self,
        job: JobRecord,
        state: "_WorkflowExecutionState",
    ) -> JobRecord:
        metadata = {
            **dict(job.metadata),
            "workflow_state": self._workflow_state_metadata(state),
        }
        return self._job_repository.update(replace(job, metadata=metadata))

    def _build_failed_job_record(
        self,
        job: JobRecord,
        state: "_WorkflowExecutionState",
        *,
        error_code: str,
        error_message_safe: str,
    ) -> JobRecord:
        metadata = {
            **dict(job.metadata),
            "workflow_state": self._workflow_state_metadata(state),
        }
        return replace(
            job,
            status=JobStatus.failed,
            error_code=error_code,
            error_message_safe=error_message_safe,
            completed_at=utc_now(),
            metadata=metadata,
        )

    def _workflow_state_metadata(
        self,
        state: "_WorkflowExecutionState",
    ) -> dict[str, Any]:
        return {
            "steps": dict(state.step_state),
            "context": normalize_mapping(state.context),
            "last_successful_step_id": state.last_successful_step_id,
            "last_successful_output_artifact_id": state.last_successful_output_artifact_id,
            "final_output_source": state.final_output_source,
            "result_artifact_id": state.result_artifact_id,
        }

    def _validate_workflow_input(
        self,
        workflow: WorkflowDefinition,
        payload: Mapping[str, Any],
        *,
        schema_ref: str,
    ) -> None:
        schema = self._require_schema(schema_ref)
        normalized_schema = normalize_schema_mapping(schema.schema)
        if normalized_schema is None:
            return
        try:
            validate_json_schema(instance=payload, schema=normalized_schema)
        except JsonSchemaValidationError as exc:
            raise WorkflowInputValidationError(
                f"Workflow input validation failed for {schema_ref}."
            ) from exc

    def _validate_workflow_output(
        self,
        workflow: WorkflowDefinition,
        payload: Mapping[str, Any],
        *,
        schema_ref: str,
    ) -> None:
        schema = self._require_schema(schema_ref)
        normalized_schema = normalize_schema_mapping(schema.schema)
        if normalized_schema is None:
            return
        try:
            validate_json_schema(instance=payload, schema=normalized_schema)
        except JsonSchemaValidationError as exc:
            raise WorkflowOutputValidationError(
                f"Workflow output validation failed for {schema_ref}."
            ) from exc

    def _schema_version(self, schema_ref: str) -> int | None:
        schema = self._config_registry.get_schema(schema_ref)
        return None if schema is None else schema.version

    def _require_workflow(self, workflow_id: str) -> WorkflowDefinition:
        workflow = self._config_registry.get_workflow(workflow_id)
        if workflow is None:
            raise LookupError(f"workflow not found: {workflow_id}")
        return workflow

    def _require_action_config(self, action_config_id: str) -> Any:
        action_config = self._config_registry.get_action_configuration(action_config_id)
        if action_config is None:
            raise LookupError(f"action config not found: {action_config_id}")
        return action_config

    def _require_schema(self, schema_ref: str) -> Any:
        schema = self._config_registry.get_schema(schema_ref)
        if schema is None:
            raise LookupError(f"schema not found: {schema_ref}")
        return schema

    def _require_context(self, value: str | None, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"missing required workflow context: {field_name}")
        return value

    def _error_code_for_exception(self, exc: Exception) -> str:
        if isinstance(exc, WorkflowExecutionError):
            return exc.code
        return getattr(exc, "code", "workflow_execution_failed")

    def _safe_error_message_for_exception(self, exc: Exception) -> str:
        if isinstance(exc, PlatformError):
            raw = str(exc).strip() or type(exc).__name__
            return self._redact_sensitive_error_message(raw)
        return "Workflow execution failed."

    def _redact_sensitive_error_message(self, message: str) -> str:
        lowered = message.lower()
        if any(secret_key in lowered for secret_key in _SECRET_KEYS):
            return "[redacted workflow error]"
        return message[:_MAX_SAFE_ERROR_MESSAGE_LENGTH]

    def _register_failure_recovery(
        self,
        job: JobRecord,
        *,
        error_code: str,
        failed_step: "_WorkflowFailedStepRecovery | None",
    ) -> None:
        register_rollback_recovery_callback(
            self._session,
            lambda recovery_session_factory: _persist_failed_workflow_job_after_rollback(
                recovery_session_factory,
                job,
                error_code=error_code,
                failed_step=failed_step,
            ),
        )

    @staticmethod
    def _remember_failed_step(
        state: "_WorkflowExecutionState",
        *,
        step: WorkflowStepDefinition,
        action_type: str,
        attempt_count: int,
        error_code: str,
        action_run_id: str | None,
    ) -> None:
        state.failed_step = _WorkflowFailedStepRecovery(
            step_id=step.step_id,
            action_type=action_type,
            action_config_id=step.action_config_id,
            retry_count=step.retry_count,
            attempt_count=attempt_count,
            error_code=error_code,
            action_run_id=action_run_id,
        )

    def _latest_action_run_id(self, job_id: str, step_id: str) -> str | None:
        return self._session.execute(
            sa.select(action_runs_table.c.id)
            .where(action_runs_table.c.job_id == job_id)
            .where(action_runs_table.c.step_id == step_id)
            .order_by(
                action_runs_table.c.created_at.desc(),
                action_runs_table.c.started_at.desc().nullslast(),
                action_runs_table.c.completed_at.desc().nullslast(),
            )
        ).scalars().first()

    def _emit_step_failed(
        self,
        context: ExecutionContext,
        *,
        step: WorkflowStepDefinition,
        attempt_count: int,
        error_code: str,
        action_run_id: str | None,
    ) -> None:
        failure_context = context
        if action_run_id is not None:
            failure_context = enrich_event_context(context, action_run_id=action_run_id)
        self._event_emitter.emit(
            "workflow.step_failed",
            failure_context,
            result_status=ActionRunStatus.failed.value,
            properties={
                "step_id": step.step_id,
                "retry_count": step.retry_count,
                "attempt_count": attempt_count,
                "error_code": error_code,
            },
        )


def _context_from_record(record: JobRecord) -> ExecutionContext:
    return ExecutionContext(
        tenant_id=record.tenant_id,
        region=record.region,
        product_id=record.product_id,
        frontend_id=record.frontend_id,
        scenario_session_id=record.scenario_session_id,
        job_id=record.id,
        workflow_id=record.workflow_id,
        workflow_version=record.workflow_version,
        guest_id=_metadata_str(record.metadata, "guest_id"),
        user_id=_metadata_str(record.metadata, "user_id"),
        scenario_chain_id=_metadata_str(record.metadata, "scenario_chain_id"),
        handoff_id=_metadata_str(record.metadata, "handoff_id"),
        acquisition_source=_metadata_str(record.metadata, "acquisition_source"),
    )


_MAX_SAFE_ERROR_MESSAGE_LENGTH = 256
_SECRET_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "bearer",
        "password",
        "secret",
        "token",
    }
)


def _persist_failed_workflow_job_after_rollback(
    recovery_session_factory: Any,
    record: JobRecord,
    *,
    error_code: str,
    failed_step: "_WorkflowFailedStepRecovery | None",
) -> None:
    with transaction_boundary(recovery_session_factory) as recovery_session:
        repository = JobRepository(recovery_session)
        action_run_repository = ActionRunRepository(recovery_session)
        artifact_repository = ArtifactRepository(recovery_session)
        event_emitter = EventEmitter(EventLogRepository(recovery_session))

        existing = repository.get(record.id)
        recovered_record = _rebuild_failed_workflow_record_for_recovery(
            record,
            action_run_repository=action_run_repository,
            artifact_repository=artifact_repository,
            failed_step=failed_step,
        )
        if existing is None:
            stored = repository.create(recovered_record)
            event_emitter.emit(
                "workflow.started",
                _context_from_record(stored),
                properties={"workflow_version": stored.workflow_version},
            )
        else:
            stored = repository.update(recovered_record)

        if failed_step is not None:
            persisted_failed_action_run_id = _existing_action_run_id(
                failed_step.action_run_id,
                action_run_repository,
            )
            step_context = enrich_event_context(
                _context_from_record(stored),
                step_id=failed_step.step_id,
                action_type=failed_step.action_type,
                action_config_id=failed_step.action_config_id,
            )
            event_emitter.emit(
                "workflow.step_started",
                step_context,
                properties={
                    "step_id": failed_step.step_id,
                    "retry_count": failed_step.retry_count,
                },
            )
            event_emitter.emit(
                "workflow.step_failed",
                (
                    step_context
                    if persisted_failed_action_run_id is None
                    else enrich_event_context(
                        step_context,
                        action_run_id=persisted_failed_action_run_id,
                    )
                ),
                result_status=ActionRunStatus.failed.value,
                properties={
                    "step_id": failed_step.step_id,
                    "retry_count": failed_step.retry_count,
                    "attempt_count": failed_step.attempt_count,
                    "error_code": failed_step.error_code,
                },
            )

        event_emitter.emit(
            "workflow.failed",
            _context_from_record(stored),
            result_status=stored.status.value,
            properties={
                "error_code": error_code,
                "workflow_version": stored.workflow_version,
            },
        )


def _metadata_str(metadata: Mapping[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) and value else None


@dataclass(frozen=True)
class _WorkflowFailedStepRecovery:
    step_id: str
    action_type: str
    action_config_id: str
    retry_count: int
    attempt_count: int
    error_code: str
    action_run_id: str | None


def _rebuild_failed_workflow_record_for_recovery(
    record: JobRecord,
    *,
    action_run_repository: ActionRunRepository,
    artifact_repository: ArtifactRepository,
    failed_step: _WorkflowFailedStepRecovery | None,
) -> JobRecord:
    metadata = dict(record.metadata)
    metadata["workflow_state"] = _sanitize_workflow_state_for_recovery(
        metadata.get("workflow_state"),
        action_run_repository=action_run_repository,
        artifact_repository=artifact_repository,
        failed_step=failed_step,
    )
    return replace(
        record,
        result_artifact_id=None,
        metadata=metadata,
    )


def _sanitize_workflow_state_for_recovery(
    workflow_state: Any,
    *,
    action_run_repository: ActionRunRepository,
    artifact_repository: ArtifactRepository,
    failed_step: _WorkflowFailedStepRecovery | None,
) -> dict[str, Any]:
    raw_steps = workflow_state.get("steps") if isinstance(workflow_state, Mapping) else None
    recovered_steps: dict[str, Any] = {}
    if failed_step is not None:
        raw_step_state = raw_steps.get(failed_step.step_id) if isinstance(raw_steps, Mapping) else None
        persisted_action_run_id = _existing_action_run_id(
            failed_step.action_run_id,
            action_run_repository,
        )
        recovered_steps[failed_step.step_id] = {
            "status": ActionRunStatus.failed.value,
            "attempt_count": failed_step.attempt_count,
            "last_action_run_id": persisted_action_run_id,
            "output_artifact_id": _existing_artifact_id(
                (
                    raw_step_state.get("output_artifact_id")
                    if isinstance(raw_step_state, Mapping)
                    else None
                ),
                artifact_repository,
            ),
            "skip_reason": None,
            "error_code": failed_step.error_code,
        }

    return {
        "steps": recovered_steps,
        "context": {},
        "last_successful_step_id": None,
        "last_successful_output_artifact_id": None,
        "final_output_source": None,
        "result_artifact_id": None,
    }


def _existing_artifact_id(
    artifact_id: Any,
    artifact_repository: ArtifactRepository,
) -> str | None:
    if not isinstance(artifact_id, str) or not artifact_id:
        return None
    artifact = artifact_repository.get(artifact_id)
    return None if artifact is None else artifact.id


def _existing_action_run_id(
    action_run_id: Any,
    action_run_repository: ActionRunRepository,
) -> str | None:
    if not isinstance(action_run_id, str) or not action_run_id:
        return None
    action_run = action_run_repository.get(action_run_id)
    return None if action_run is None else action_run.id


class _WorkflowExecutionState:
    def __init__(
        self,
        *,
        scenario_input: dict[str, Any],
        step_outputs: dict[str, Any],
        context: dict[str, Any],
        step_state: dict[str, dict[str, Any]],
    ) -> None:
        self.scenario_input = scenario_input
        self.step_outputs = step_outputs
        self.context = context
        self.step_state = step_state
        self.last_successful_step_id: str | None = None
        self.last_successful_output: dict[str, Any] | list[Any] | Any = None
        self.last_successful_output_artifact_id: str | None = None
        self.final_output_source: str | None = None
        self.result_artifact_id: str | None = None
        self.failed_step: _WorkflowFailedStepRecovery | None = None


def _normalize_output_payload(
    payload: dict[str, Any] | list[Any] | None,
) -> dict[str, Any] | list[Any] | None:
    if payload is None:
        return None
    if isinstance(payload, Mapping):
        return normalize_mapping(payload)
    return list(payload)
