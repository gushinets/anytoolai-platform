from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.events.replay import (
    ReplayTimestampSequencer,
    sequence_existing_replay_event,
)
from anytoolai_platform_core.providers.models import ProviderCallRecord, ProviderCallStatus
from anytoolai_platform_core.providers.repository import ProviderCallRepository
from anytoolai_platform_core.storage.transactions import transaction_boundary


def recover_provider_call_row_after_rollback(
    recovery_session_factory: Any,
    record: ProviderCallRecord,
) -> None:
    with transaction_boundary(recovery_session_factory) as recovery_session:
        repository = ProviderCallRepository(recovery_session)
        existing = repository.get(record.id)
        if existing is None:
            repository.create(record)
            return
        repository.update(record)


def recover_provider_call_events_after_rollback(
    recovery_session_factory: Any,
    provider_call_id: str,
) -> None:
    with transaction_boundary(recovery_session_factory) as recovery_session:
        repository = ProviderCallRepository(recovery_session)
        stored = repository.get(provider_call_id)
        if stored is None:
            return
        emit_recovered_provider_events(
            EventLogRepository(recovery_session),
            stored,
        )


def emit_recovered_provider_events(
    event_log_repository: EventLogRepository,
    record: ProviderCallRecord,
    *,
    timestamp_sequencer: ReplayTimestampSequencer | None = None,
) -> None:
    event_emitter = EventEmitter(event_log_repository)
    context = _provider_event_context_from_record(
        record,
        pydantic_run_id=record.pydantic_run_id,
    )
    started_event = event_log_repository.find_event(
        event_type="provider.request_started",
        provider_call_id=record.id,
    )
    if started_event is None:
        preferred_timestamp = record.started_at or record.created_at
        event_emitter.emit(
            "provider.request_started",
            context,
            properties=_provider_event_properties_from_record(record),
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

    if record.status is ProviderCallStatus.succeeded:
        succeeded_event = event_log_repository.find_event(
            event_type="provider.request_succeeded",
            provider_call_id=record.id,
        )
        if succeeded_event is None:
            preferred_timestamp = record.completed_at or record.started_at or record.created_at
            event_emitter.emit(
                "provider.request_succeeded",
                _provider_event_context_from_record(
                    record,
                    pydantic_run_id=record.pydantic_run_id,
                    litellm_response_id=record.litellm_response_id,
                ),
                result_status=record.status.value,
                properties=_provider_event_properties_from_record(
                    record,
                    pydantic_run_id=record.pydantic_run_id,
                    litellm_response_id=record.litellm_response_id,
                    total_tokens=record.total_tokens,
                    http_status=record.http_status,
                ),
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
        return

    if record.status in (ProviderCallStatus.failed, ProviderCallStatus.timed_out):
        failed_event = event_log_repository.find_event(
            event_type="provider.request_failed",
            provider_call_id=record.id,
        )
        if failed_event is None:
            preferred_timestamp = record.completed_at or record.started_at or record.created_at
            event_emitter.emit(
                "provider.request_failed",
                _provider_event_context_from_record(
                    record,
                    pydantic_run_id=record.pydantic_run_id,
                ),
                result_status=record.status.value,
                properties=_provider_event_properties_from_record(
                    record,
                    pydantic_run_id=record.pydantic_run_id,
                    error_code=record.error_code,
                    failure_kind=record.failure_kind,
                ),
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


def _provider_event_context_from_record(
    record: ProviderCallRecord,
    *,
    pydantic_run_id: str | None = None,
    litellm_response_id: str | None = None,
) -> ExecutionContext:
    request_metadata = record.metadata.get("request_metadata")
    if not isinstance(request_metadata, Mapping):
        request_metadata = {}
    return ExecutionContext(
        tenant_id=record.tenant_id,
        region=record.region,
        product_id=record.product_id,
        frontend_id=record.frontend_id,
        scenario_session_id=record.scenario_session_id,
        job_id=record.job_id,
        workflow_id=record.workflow_id,
        workflow_version=record.workflow_version,
        guest_id=_metadata_str(request_metadata, "guest_id"),
        user_id=_metadata_str(request_metadata, "user_id"),
        scenario_chain_id=_metadata_str(request_metadata, "scenario_chain_id"),
        action_run_id=record.action_run_id,
        action_type=record.action_type,
        action_config_id=record.action_config_id,
        provider_policy_ref=record.provider_policy_ref,
        provider_call_id=record.id,
        provider=record.provider,
        model=record.model,
        physical_call_index=record.physical_call_index,
        pydantic_run_id=pydantic_run_id,
        litellm_response_id=litellm_response_id,
        handoff_id=_metadata_str(request_metadata, "handoff_id"),
        acquisition_source=_metadata_str(request_metadata, "acquisition_source"),
    )


def _provider_event_properties_from_record(
    record: ProviderCallRecord,
    *,
    pydantic_run_id: str | None = None,
    litellm_response_id: str | None = None,
    total_tokens: int | None = None,
    http_status: int | None = None,
    error_code: str | None = None,
    failure_kind: str | None = None,
) -> dict[str, Any]:
    return {
        "provider_call_id": record.id,
        "action_run_id": record.action_run_id,
        "provider_policy_ref": record.provider_policy_ref,
        "physical_call_index": record.physical_call_index,
        "semantic_attempt_index": record.semantic_attempt_index,
        "transport_attempt_index": record.transport_attempt_index,
        "pydantic_run_id": pydantic_run_id,
        "litellm_response_id": litellm_response_id,
        "total_tokens": total_tokens,
        "http_status": http_status,
        "failure_kind": failure_kind,
        "error_code": error_code,
    }


def _metadata_str(metadata: Mapping[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) and value else None