from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter, enrich_event_context
from anytoolai_platform_core.providers.gateway.errors import ProviderGatewayExecutionError
from anytoolai_platform_core.providers.models import (
    ProviderCallRecord,
    ProviderCallStatus,
    ProviderResponse,
    ResolvedProviderRequest,
)


def event_context_from_resolved_request(
    request: ResolvedProviderRequest,
) -> ExecutionContext:
    return ExecutionContext(
        tenant_id=request.tenant_id,
        region=request.region,
        product_id=request.product_id,
        frontend_id=request.frontend_id,
        scenario_session_id=request.scenario_session_id,
        job_id=request.job_id,
        workflow_id=request.workflow_id,
        workflow_version=request.workflow_version,
        guest_id=_metadata_str(request.metadata, "guest_id"),
        user_id=_metadata_str(request.metadata, "user_id"),
        scenario_chain_id=_metadata_str(request.metadata, "scenario_chain_id"),
        action_type=request.action_type,
        action_config_id=request.action_config_id,
        handoff_id=_metadata_str(request.metadata, "handoff_id"),
        provider=request.provider,
        model=request.model,
        acquisition_source=_metadata_str(request.metadata, "acquisition_source"),
        action_run_id=request.action_run_id,
        provider_policy_ref=request.provider_policy_ref,
    )


def emit_provider_started(
    event_emitter: EventEmitter | None,
    context: ExecutionContext,
    *,
    provider_call: ProviderCallRecord,
) -> None:
    if event_emitter is None:
        return
    event_emitter.emit(
        "provider.request_started",
        _provider_event_context(
            context,
            provider_call=provider_call,
            pydantic_run_id=provider_call.pydantic_run_id,
        ),
        properties=_provider_event_properties(provider_call=provider_call),
    )


def emit_provider_succeeded(
    event_emitter: EventEmitter | None,
    context: ExecutionContext,
    *,
    provider_call: ProviderCallRecord,
    response: ProviderResponse,
) -> None:
    if event_emitter is None:
        return
    event_emitter.emit(
        "provider.request_succeeded",
        _provider_event_context(
            context,
            provider_call=provider_call,
            pydantic_run_id=response.pydantic_run_id,
            litellm_response_id=response.litellm_response_id,
        ),
        result_status=response.status.value,
        properties=_provider_event_properties(
            provider_call=provider_call,
            pydantic_run_id=response.pydantic_run_id,
            litellm_response_id=response.litellm_response_id,
            total_tokens=response.usage.total_tokens,
            http_status=response.http_status,
        ),
    )


def emit_provider_failed(
    event_emitter: EventEmitter | None,
    context: ExecutionContext,
    *,
    provider_call: ProviderCallRecord,
    error: ProviderGatewayExecutionError,
) -> None:
    if event_emitter is None:
        return
    event_emitter.emit(
        "provider.request_failed",
        _provider_event_context(
            context,
            provider_call=provider_call,
            pydantic_run_id=provider_call.pydantic_run_id,
        ),
        result_status=(
            ProviderCallStatus.timed_out.value
            if error.error_code == "provider_request_timed_out"
            else ProviderCallStatus.failed.value
        ),
        properties=_provider_event_properties(
            provider_call=provider_call,
            pydantic_run_id=provider_call.pydantic_run_id,
            error_code=error.error_code,
            failure_kind=error.failure_kind,
        ),
    )


def _provider_event_context(
    context: ExecutionContext,
    *,
    provider_call: ProviderCallRecord,
    pydantic_run_id: str | None = None,
    litellm_response_id: str | None = None,
) -> ExecutionContext:
    return enrich_event_context(
        context,
        action_run_id=provider_call.action_run_id,
        provider_policy_ref=provider_call.provider_policy_ref,
        provider_call_id=provider_call.id,
        physical_call_index=provider_call.physical_call_index,
        pydantic_run_id=pydantic_run_id,
        litellm_response_id=litellm_response_id,
    )


def _provider_event_properties(
    *,
    provider_call: ProviderCallRecord,
    pydantic_run_id: str | None = None,
    litellm_response_id: str | None = None,
    total_tokens: int | None = None,
    http_status: int | None = None,
    error_code: str | None = None,
    failure_kind: str | None = None,
) -> dict[str, Any]:
    return {
        "provider_call_id": provider_call.id,
        "action_run_id": provider_call.action_run_id,
        "provider_policy_ref": provider_call.provider_policy_ref,
        "physical_call_index": provider_call.physical_call_index,
        "semantic_attempt_index": provider_call.semantic_attempt_index,
        "transport_attempt_index": provider_call.transport_attempt_index,
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