from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
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
    latency_ms: int = 0
    estimated_cost: float = 0.0


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
    ) -> tuple[ProviderCallRecord, ProviderResponse]:
        if self._provider_call_repository is None or self._event_emitter is None:
            raise RuntimeError("provider runtime execution requires repository and event emitter")

        runtime_context = replace(context, provider=provider, model=request.model)
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
                step_id=_require_context_field(context.step_id, "step_id"),
                action_type=_require_context_field(context.action_type, "action_type"),
                action_config_id=_require_context_field(
                    context.action_config_id,
                    "action_config_id",
                ),
                provider_policy_id=provider_policy_id,
                provider=provider,
                model=request.model,
                status=ProviderCallStatus.running,
                started_at=utc_now(),
            )
        )
        self._event_emitter.emit(
            "provider.request_started",
            runtime_context,
            properties={
                "provider_policy_id": provider_policy_id,
                "response_schema_present": request.response_schema is not None,
            },
        )
        try:
            response = self.complete(provider, request)
        except Exception as exc:
            error_code = _provider_error_code(exc)
            failed_status = (
                ProviderCallStatus.timed_out
                if isinstance(exc, TimeoutError)
                else ProviderCallStatus.failed
            )
            failed_record = self._provider_call_repository.update(
                replace(
                    provider_call,
                    status=failed_status,
                    error_code=error_code,
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
                },
            )
            raise

        completed_record = self._provider_call_repository.update(
            replace(
                provider_call,
                provider=response.provider,
                model=response.model,
                status=ProviderCallStatus.succeeded,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                latency_ms=response.latency_ms,
                estimated_cost=response.estimated_cost,
                completed_at=utc_now(),
            )
        )
        success_context = replace(
            runtime_context,
            provider=response.provider,
            model=response.model,
        )
        self._event_emitter.emit(
            "provider.request_succeeded",
            success_context,
            result_status=completed_record.status.value,
            properties={
                "provider_policy_id": provider_policy_id,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "latency_ms": response.latency_ms,
                "estimated_cost": response.estimated_cost,
            },
        )
        return completed_record, response


def _require_context_field(value: str | None, field_name: str) -> str:
    if value is None or not value.strip():
        raise ValueError(f"provider runtime context missing {field_name}")
    return value


def _provider_error_code(exc: Exception) -> str:
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, PlatformError):
        return exc.code
    return type(exc).__name__.lower()
