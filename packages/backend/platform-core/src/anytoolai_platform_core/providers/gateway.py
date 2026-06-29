from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter, EventValidationError
from anytoolai_platform_core.providers.models import ProviderCallRecord, ProviderCallStatus
from anytoolai_platform_core.providers.repository import ProviderCallRepository


@dataclass(frozen=True)
class ProviderRequest:
    prompt: str
    model: str
    response_schema: dict | None = None


@dataclass(frozen=True)
class ProviderResponse:
    content: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int | None = None
    latency_ms: int = 0
    estimated_cost: float = 0.0
    http_status: int | None = None
    litellm_response_id: str | None = None


class ProviderAdapter(Protocol):
    def complete(self, request: ProviderRequest) -> ProviderResponse: ...


class ProviderGateway:
    def __init__(
        self,
        adapters: dict[str, ProviderAdapter],
        provider_call_repository: ProviderCallRepository | None = None,
        event_emitter: EventEmitter | None = None,
    ) -> None:
        self._adapters = adapters
        self._provider_call_repository = provider_call_repository
        self._event_emitter = event_emitter

    def complete(self, provider: str, request: ProviderRequest) -> ProviderResponse:
        adapter = self._adapters[provider]
        return adapter.complete(request)

    def execute(
        self,
        provider: str,
        request: ProviderRequest,
        context: ExecutionContext,
        *,
        provider_policy_id: str,
        action_run_id: str,
        semantic_attempt_index: int = 1,
        transport_attempt_index: int = 1,
        physical_call_index: int = 1,
        pydantic_run_id: str | None = None,
    ) -> tuple[ProviderCallRecord, ProviderResponse]:
        if self._provider_call_repository is None or self._event_emitter is None:
            raise RuntimeError("provider runtime execution requires repository and event emitter")

        _require_event_dimension(context.tenant_id, "tenant_id")
        _require_event_dimension(context.region, "region")
        provider_call = self._provider_call_repository.create(
            ProviderCallRecord(
                tenant_id=context.tenant_id,
                region=context.region,
                product_id=context.product_id,
                frontend_id=context.frontend_id,
                scenario_session_id=_require_context_field(
                    context.scenario_session_id,
                    "scenario_session_id",
                ),
                job_id=_require_context_field(context.job_id, "job_id"),
                action_run_id=action_run_id,
                workflow_id=_require_context_field(context.workflow_id, "workflow_id"),
                workflow_version=_require_context_int(
                    context.workflow_version,
                    "workflow_version",
                ),
                step_id=_require_context_field(context.step_id, "step_id"),
                action_type=_require_context_field(context.action_type, "action_type"),
                action_config_id=_require_context_field(
                    context.action_config_id,
                    "action_config_id",
                ),
                provider_policy_id=provider_policy_id,
                gateway_backend="litellm_sdk",
                gateway_model=request.model,
                provider=provider,
                model=request.model,
                semantic_attempt_index=semantic_attempt_index,
                transport_attempt_index=transport_attempt_index,
                physical_call_index=physical_call_index,
                status=ProviderCallStatus.running,
                pydantic_run_id=pydantic_run_id,
                started_at=utc_now(),
            )
        )
        runtime_context = replace(
            context,
            action_run_id=action_run_id,
            provider_policy_id=provider_policy_id,
            provider_call_id=provider_call.id,
            provider=provider,
            model=request.model,
            physical_call_index=physical_call_index,
            pydantic_run_id=pydantic_run_id,
        )
        self._event_emitter.emit(
            "provider.request_started",
            runtime_context,
            properties={
                "provider_policy_id": provider_policy_id,
                "provider_call_id": provider_call.id,
                "physical_call_index": physical_call_index,
                "gateway_backend": provider_call.gateway_backend,
                "gateway_model": provider_call.gateway_model,
                "response_schema_present": request.response_schema is not None,
            },
        )
        try:
            response = self.complete(provider, request)
        except Exception as exc:
            error_code = _provider_error_code(exc)
            http_status = _provider_http_status(exc)
            failure_kind = _provider_failure_kind(exc, http_status)
            failed_status = (
                ProviderCallStatus.timed_out
                if isinstance(exc, TimeoutError)
                else ProviderCallStatus.failed
            )
            failed_record = self._provider_call_repository.update(
                replace(
                    provider_call,
                    status=failed_status,
                    failure_kind=failure_kind,
                    error_code=error_code,
                    http_status=http_status,
                    completed_at=utc_now(),
                )
            )
            self._event_emitter.emit(
                "provider.request_failed",
                runtime_context,
                result_status=failed_record.status.value,
                properties={
                    "error_code": error_code,
                    "error_type": type(exc).__name__,
                    "provider_policy_id": provider_policy_id,
                    "provider_call_id": failed_record.id,
                    "physical_call_index": failed_record.physical_call_index,
                    "gateway_backend": failed_record.gateway_backend,
                    "gateway_model": failed_record.gateway_model,
                    "failure_kind": failed_record.failure_kind,
                    "http_status": failed_record.http_status,
                },
            )
            raise

        total_tokens = _response_total_tokens(response)
        completed_record = self._provider_call_repository.update(
            replace(
                provider_call,
                provider=response.provider,
                model=response.model,
                status=ProviderCallStatus.succeeded,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                total_tokens=total_tokens,
                latency_ms=response.latency_ms,
                estimated_cost=response.estimated_cost,
                http_status=response.http_status,
                litellm_response_id=response.litellm_response_id,
                completed_at=utc_now(),
            )
        )
        success_context = replace(
            runtime_context,
            provider=response.provider,
            model=response.model,
            litellm_response_id=response.litellm_response_id,
        )
        self._event_emitter.emit(
            "provider.request_succeeded",
            success_context,
            result_status=completed_record.status.value,
            properties={
                "provider_policy_id": provider_policy_id,
                "provider_call_id": completed_record.id,
                "physical_call_index": completed_record.physical_call_index,
                "gateway_backend": completed_record.gateway_backend,
                "gateway_model": completed_record.gateway_model,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "total_tokens": total_tokens,
                "latency_ms": response.latency_ms,
                "estimated_cost": response.estimated_cost,
                "http_status": response.http_status,
            },
        )
        return completed_record, response


def _require_context_field(value: str | None, field_name: str) -> str:
    if value is None or not value.strip():
        raise ValueError(f"provider runtime context missing {field_name}")
    return value


def _require_context_int(value: int | None, field_name: str) -> int:
    if value is None:
        raise ValueError(f"provider runtime context missing {field_name}")
    return value


def _require_event_dimension(value: str | None, field_name: str) -> str:
    if value is None or not value.strip():
        raise EventValidationError(f"missing required event dimension: {field_name}")
    return value


def _provider_error_code(exc: Exception) -> str:
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, PlatformError):
        return exc.code
    return type(exc).__name__.lower()


def _provider_http_status(exc: Exception) -> int | None:
    for attribute in ("http_status", "status_code", "status"):
        value = getattr(exc, attribute, None)
        if isinstance(value, int):
            return value
    return None


def _provider_failure_kind(exc: Exception, http_status: int | None) -> str:
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, PlatformError):
        return "platform_error"
    if http_status is not None:
        return "http_error"
    return "unexpected_error"


def _response_total_tokens(response: ProviderResponse) -> int:
    if response.total_tokens is not None:
        return response.total_tokens
    return response.input_tokens + response.output_tokens
