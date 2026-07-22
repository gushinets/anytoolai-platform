from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.common.ids import new_id
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.products.models import FrontendDefinition
from anytoolai_platform_core.quotas.service import GuestQuotaService
from anytoolai_platform_core.scenarios.checkpoints import (
    FAILED_CHECKPOINT_ID,
    PROCESSING_CHECKPOINT_ID,
    RESULT_READY_CHECKPOINT_ID,
    resolve_checkpoint_state,
    resolve_effective_status,
)
from anytoolai_platform_core.scenarios.models import (
    ScenarioDefinition,
    ScenarioSessionRecord,
    ScenarioSessionSnapshot,
    ScenarioSessionStatus,
)
from anytoolai_platform_core.scenarios.next_actions import validate_next_action
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.workflows.models import JobRecord
from anytoolai_platform_core.workflows.repository import JobRepository


class ScenarioNotFoundError(PlatformError):
    def __init__(self) -> None:
        super().__init__("scenario_not_found", "Scenario not found.")


class ScenarioSessionNotFoundError(PlatformError):
    def __init__(self) -> None:
        super().__init__("scenario_session_not_found", "Scenario session not found.")


class ScenarioFrontendInvalidError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "scenario_frontend_invalid",
            "Frontend is not enabled for this product scenario.",
        )


class ScenarioInputInvalidError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "scenario_input_invalid",
            "Scenario input must be a JSON object.",
        )


class ScenarioRuntimeService:
    def __init__(
        self,
        *,
        config_registry: ConfigRegistry,
        session_repository: ScenarioSessionRepository,
        session_service: ScenarioSessionService,
        job_repository: JobRepository,
        event_emitter: EventEmitter,
        quota_service: GuestQuotaService | None = None,
    ) -> None:
        self._config_registry = config_registry
        self._session_repository = session_repository
        self._session_service = session_service
        self._job_repository = job_repository
        self._event_emitter = event_emitter
        self._quota_service = quota_service

    def start_session(
        self,
        *,
        tenant_id: str,
        region: str,
        product_id: str,
        scenario_id: str,
        frontend_id: str,
        input_payload: Mapping[str, Any],
        guest_id: str | None = None,
        user_id: str | None = None,
        source_frontend_instance_id: str | None = None,
    ) -> ScenarioSessionSnapshot:
        scenario = self._require_product_scenario(product_id, scenario_id)
        self._require_enabled_frontend(product_id, frontend_id)

        if not isinstance(input_payload, Mapping):
            raise ScenarioInputInvalidError()

        workflow = self._config_registry.get_workflow(scenario.workflow_id)
        if workflow is None:
            raise LookupError(f"workflow not found: {scenario.workflow_id}")

        scenario_session_id = new_id("scenario_session")
        if self._quota_service is not None:
            self._quota_service.consume_for_accepted_start(
                tenant_id=tenant_id,
                region=region,
                product_id=product_id,
                frontend_id=frontend_id,
                guest_id=guest_id,
                scenario_id=scenario.scenario_id,
                scenario_session_id=scenario_session_id,
                scenario_chain_id=scenario_session_id,
            )

        session_record = ScenarioSessionRecord(
            id=scenario_session_id,
            tenant_id=tenant_id,
            region=region,
            product_id=product_id,
            frontend_id=frontend_id,
            scenario_id=scenario.scenario_id,
            scenario_version=scenario.version,
            guest_id=guest_id,
            user_id=user_id,
            status=ScenarioSessionStatus.started,
            current_checkpoint_id=PROCESSING_CHECKPOINT_ID,
            scenario_chain_id=scenario_session_id,
            source_frontend_instance_id=source_frontend_instance_id,
            metadata={"input": dict(input_payload)},
        )
        stored_session = self._session_service.start(session_record)

        job = self._job_repository.create(
            JobRecord(
                tenant_id=tenant_id,
                region=region,
                product_id=product_id,
                frontend_id=frontend_id,
                scenario_session_id=stored_session.id,
                workflow_id=workflow.workflow_id,
                workflow_version=workflow.version,
                metadata={
                    "guest_id": guest_id,
                    "user_id": user_id,
                    "scenario_chain_id": stored_session.scenario_chain_id,
                    "acquisition_source": frontend_id,
                },
            )
        )

        return self._snapshot_from_records(
            session=stored_session,
            scenario=scenario,
            job=job,
        )

    def get_session_snapshot(
        self,
        scenario_session_id: str,
        *,
        tenant_id: str,
        region: str,
    ) -> ScenarioSessionSnapshot:
        session = self._session_repository.get_in_scope(
            scenario_session_id,
            tenant_id=tenant_id,
            region=region,
        )
        if session is None:
            raise ScenarioSessionNotFoundError()
        job = self._job_repository.get_latest_for_scenario_session(session.id)
        if job is None:
            raise LookupError(
                f"scenario session {scenario_session_id} does not have a linked job"
            )
        scenario = self._require_product_scenario(
            session.product_id,
            session.scenario_id,
            scenario_version=session.scenario_version,
        )
        return self._snapshot_from_records(
            session=session,
            scenario=scenario,
            job=job,
        )

    def record_next_action(
        self,
        scenario_session_id: str,
        *,
        tenant_id: str,
        region: str,
        next_action_id: str,
        checkpoint_id: str,
    ) -> ScenarioSessionSnapshot:
        session = self._session_repository.get_in_scope(
            scenario_session_id,
            tenant_id=tenant_id,
            region=region,
        )
        if session is None:
            raise ScenarioSessionNotFoundError()
        job = self._job_repository.get_latest_for_scenario_session(session.id)
        if job is None:
            raise LookupError(
                f"scenario session {scenario_session_id} does not have a linked job"
            )
        scenario = self._require_product_scenario(
            session.product_id,
            session.scenario_id,
            scenario_version=session.scenario_version,
        )
        checkpoint_state = resolve_checkpoint_state(
            scenario=scenario,
            session=session,
            job=job,
        )
        validate_next_action(
            expected_checkpoint_id=checkpoint_id,
            current_checkpoint=checkpoint_state,
            next_action_id=next_action_id,
        )
        self._event_emitter.emit(
            "client.next_action_clicked",
            ExecutionContext(
                tenant_id=session.tenant_id,
                region=session.region,
                product_id=session.product_id,
                frontend_id=session.frontend_id,
                scenario_session_id=session.id,
                scenario_chain_id=session.scenario_chain_id,
                guest_id=session.guest_id,
                user_id=session.user_id,
                job_id=job.id,
                workflow_id=job.workflow_id,
                workflow_version=job.workflow_version,
                acquisition_source=_metadata_str(job.metadata, "acquisition_source")
                or session.frontend_id,
            ),
            properties={
                "checkpoint_id": checkpoint_state.checkpoint_id,
                "next_action_id": next_action_id,
            },
        )
        return self._snapshot_from_records(
            session=session,
            scenario=scenario,
            job=job,
        )

    def _snapshot_from_records(
        self,
        *,
        session: ScenarioSessionRecord,
        scenario: ScenarioDefinition,
        job: JobRecord,
    ) -> ScenarioSessionSnapshot:
        checkpoint_state = resolve_checkpoint_state(
            scenario=scenario,
            session=session,
            job=job,
        )
        return ScenarioSessionSnapshot(
            scenario_session_id=session.id,
            job_id=job.id,
            status=resolve_effective_status(session=session, job=job),
            allowed_next_actions=checkpoint_state.allowed_next_actions,
            result_artifact_id=job.result_artifact_id,
            current_checkpoint_id=checkpoint_state.checkpoint_id,
        )

    def _require_product_scenario(
        self,
        product_id: str,
        scenario_id: str,
        *,
        scenario_version: int | None = None,
    ) -> ScenarioDefinition:
        product = self._config_registry.get_product(product_id)
        scenario = self._config_registry.get_scenario(scenario_id)
        if product is None or scenario is None:
            raise ScenarioNotFoundError()
        if scenario_id not in product.scenarios:
            raise ScenarioNotFoundError()
        if scenario_version is not None and scenario.version != scenario_version:
            raise ScenarioNotFoundError()
        return scenario

    def _require_enabled_frontend(
        self,
        product_id: str,
        frontend_id: str,
    ) -> FrontendDefinition:
        product = self._config_registry.get_product(product_id)
        if product is None:
            raise ScenarioNotFoundError()
        for frontend in product.frontends:
            if frontend.frontend_id == frontend_id and frontend.enabled:
                return frontend
        raise ScenarioFrontendInvalidError()


class ScenarioSessionService:
    def __init__(
        self,
        repository: ScenarioSessionRepository,
        event_emitter: EventEmitter,
    ) -> None:
        self._repository = repository
        self._event_emitter = event_emitter

    def start(self, record: ScenarioSessionRecord) -> ScenarioSessionRecord:
        stored = self._repository.create(record)
        self._event_emitter.emit(
            "scenario.started",
            _context_from_record(stored),
            properties={
                "scenario_id": stored.scenario_id,
                "scenario_version": stored.scenario_version,
            },
        )
        return stored

    def checkpoint(
        self,
        record: ScenarioSessionRecord,
        *,
        checkpoint_id: str,
        properties: dict[str, Any] | None = None,
    ) -> ScenarioSessionRecord:
        updated = self._repository.update(
            replace(
                record,
                current_checkpoint_id=checkpoint_id,
                last_event_at=utc_now(),
            ),
            tenant_id=record.tenant_id,
            region=record.region,
            product_id=record.product_id,
            frontend_id=record.frontend_id,
        )
        event_properties = dict(properties or {})
        event_properties["checkpoint_id"] = checkpoint_id
        self._event_emitter.emit(
            "scenario.checkpoint_reached",
            _context_from_record(updated),
            properties=event_properties,
        )
        return updated

    def mark_running(self, record: ScenarioSessionRecord) -> ScenarioSessionRecord:
        running_record = replace(
            record,
            status=ScenarioSessionStatus.running,
            current_checkpoint_id=record.current_checkpoint_id or PROCESSING_CHECKPOINT_ID,
            last_event_at=utc_now(),
        )
        return self._repository.update(
            running_record,
            tenant_id=record.tenant_id,
            region=record.region,
            product_id=record.product_id,
            frontend_id=record.frontend_id,
        )

    def mark_completed(
        self,
        record: ScenarioSessionRecord,
        *,
        context: ExecutionContext | None = None,
    ) -> ScenarioSessionRecord:
        updated = self._repository.update(
            replace(
                record,
                status=ScenarioSessionStatus.completed,
                current_checkpoint_id=RESULT_READY_CHECKPOINT_ID,
                completed_at=record.completed_at or utc_now(),
                last_event_at=utc_now(),
            ),
            tenant_id=record.tenant_id,
            region=record.region,
            product_id=record.product_id,
            frontend_id=record.frontend_id,
        )
        event_context = _event_context_from_record(updated, context)
        if record.current_checkpoint_id != RESULT_READY_CHECKPOINT_ID:
            self._event_emitter.emit(
                "scenario.checkpoint_reached",
                event_context,
                properties={
                    "checkpoint_id": RESULT_READY_CHECKPOINT_ID,
                    "scenario_id": updated.scenario_id,
                    "scenario_version": updated.scenario_version,
                },
            )
        self._event_emitter.emit(
            "scenario.completed",
            event_context,
            result_status=updated.status.value,
            properties={
                "scenario_id": updated.scenario_id,
                "scenario_version": updated.scenario_version,
            },
        )
        return updated

    def mark_failed(
        self,
        record: ScenarioSessionRecord,
        *,
        error_code: str,
        context: ExecutionContext | None = None,
    ) -> ScenarioSessionRecord:
        updated = self._repository.update(
            replace(
                record,
                status=ScenarioSessionStatus.failed,
                current_checkpoint_id=FAILED_CHECKPOINT_ID,
                completed_at=record.completed_at or utc_now(),
                last_event_at=utc_now(),
            ),
            tenant_id=record.tenant_id,
            region=record.region,
            product_id=record.product_id,
            frontend_id=record.frontend_id,
        )
        event_context = _event_context_from_record(updated, context)
        if record.current_checkpoint_id != FAILED_CHECKPOINT_ID:
            self._event_emitter.emit(
                "scenario.checkpoint_reached",
                event_context,
                properties={
                    "checkpoint_id": FAILED_CHECKPOINT_ID,
                    "error_code": error_code,
                    "scenario_id": updated.scenario_id,
                    "scenario_version": updated.scenario_version,
                },
            )
        self._event_emitter.emit(
            "scenario.failed",
            event_context,
            result_status=updated.status.value,
            properties={
                "error_code": error_code,
                "scenario_id": updated.scenario_id,
                "scenario_version": updated.scenario_version,
            },
        )
        return updated


def _context_from_record(record: ScenarioSessionRecord) -> ExecutionContext:
    return ExecutionContext(
        tenant_id=record.tenant_id,
        region=record.region,
        product_id=record.product_id,
        frontend_id=record.frontend_id,
        scenario_session_id=record.id,
        guest_id=record.guest_id,
        user_id=record.user_id,
        scenario_chain_id=record.scenario_chain_id,
    )


def _event_context_from_record(
    record: ScenarioSessionRecord,
    context: ExecutionContext | None,
) -> ExecutionContext:
    event_context = _context_from_record(record)
    if context is None:
        return event_context
    return replace(
        event_context,
        job_id=context.job_id,
        workflow_id=context.workflow_id,
        workflow_version=context.workflow_version,
        handoff_id=context.handoff_id,
        acquisition_source=context.acquisition_source,
    )


def _metadata_str(metadata: Mapping[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) and value else None
