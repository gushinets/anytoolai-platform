from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, replace
import inspect
from time import perf_counter
from typing import Any

from sqlalchemy.orm import Session

from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.providers.adapters.base import ProviderAdapter
from anytoolai_platform_core.providers.models import (
    ProviderCallRecord,
    ProviderCallStatus,
    ProviderPolicy,
    ProviderRequest as InternalProviderRequest,
    ProviderResponse as InternalProviderResponse,
    ProviderUsage,
    ResolvedProviderRequest,
)
from anytoolai_platform_core.providers.policies import ProviderPolicyResolver
from anytoolai_platform_core.providers.repository import ProviderCallRepository

_SECRET_KEYS = {
    "api_key",
    "authorization",
    "cookie",
    "credential",
    "password",
    "secret",
    "token",
}
_MAX_STRING_LENGTH = 500
_MAX_COLLECTION_ITEMS = 20
_MAX_NESTING_DEPTH = 4


@dataclass(frozen=True)
class ProviderRequest:
    prompt: str
    model: str
    response_schema: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ProviderResponse:
    content: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    estimated_cost: float = 0.0


class ProviderGatewayExecutionError(RuntimeError):
    def __init__(
        self,
        *,
        provider_policy_id: str,
        provider: str,
        model: str,
        error_code: str,
        error_type: str,
        message: str,
    ) -> None:
        super().__init__(message)
        self.provider_policy_id = provider_policy_id
        self.provider = provider
        self.model = model
        self.error_code = error_code
        self.error_type = error_type
        self.message = message


class ProviderGateway:
    def __init__(
        self,
        adapters: Mapping[str, ProviderAdapter],
        policy_resolver: ProviderPolicyResolver | None = None,
        provider_call_repository: Any | None = None,
        event_emitter: EventEmitter | None = None,
    ) -> None:
        self._adapters = dict(adapters)
        self._policy_resolver = policy_resolver
        self._provider_call_repository = provider_call_repository
        self._event_emitter = event_emitter

    async def request(
        self,
        request: InternalProviderRequest,
        *,
        session: Session | None = None,
    ) -> InternalProviderResponse:
        if self._policy_resolver is None:
            raise TypeError(
                "ProviderGateway.request() requires a policy_resolver configured on the gateway"
            )
        policy = self._policy_resolver.resolve(request.provider_policy_id)
        return await self._execute_policy_chain(
            request=request,
            policy=policy,
            fallback_from_policy_id=None,
            session=session,
            visited_policy_ids=set(),
        )

    async def _execute_policy_chain(
        self,
        *,
        request: InternalProviderRequest,
        policy: ProviderPolicy,
        fallback_from_policy_id: str | None,
        session: Session | None,
        visited_policy_ids: set[str],
    ) -> InternalProviderResponse:
        if policy.provider_policy_id in visited_policy_ids:
            raise ProviderGatewayExecutionError(
                provider_policy_id=policy.provider_policy_id,
                provider=policy.provider,
                model=policy.model,
                error_code="provider_policy_cycle",
                error_type="ProviderPolicyCycleError",
                message=(
                    "provider policy fallback cycle detected for "
                    f"{policy.provider_policy_id}"
                ),
            )

        visited_policy_ids = set(visited_policy_ids)
        visited_policy_ids.add(policy.provider_policy_id)

        response, final_error = await self._execute_policy_attempts(
            request=request,
            policy=policy,
            fallback_from_policy_id=fallback_from_policy_id,
            session=session,
        )
        if response is not None:
            return response

        if policy.fallback_policy is None:
            assert final_error is not None
            raise final_error

        fallback_policy = self._policy_resolver.resolve(policy.fallback_policy)
        return await self._execute_policy_chain(
            request=request,
            policy=fallback_policy,
            fallback_from_policy_id=policy.provider_policy_id,
            session=session,
            visited_policy_ids=visited_policy_ids,
        )

    async def _execute_policy_attempts(
        self,
        *,
        request: InternalProviderRequest,
        policy: ProviderPolicy,
        fallback_from_policy_id: str | None,
        session: Session | None,
    ) -> tuple[InternalProviderResponse | None, ProviderGatewayExecutionError | None]:
        repository = self._resolve_provider_call_repository(session)
        event_context = self._event_context_from_request(
            request,
            provider=policy.provider,
            model=policy.model,
        )
        self._emit_provider_started(event_context)
        should_persist = self._should_persist_provider_call(request)
        max_attempts = policy.max_retries + 1
        last_error: ProviderGatewayExecutionError | None = None

        for attempt_number in range(1, max_attempts + 1):
            resolved_request = ResolvedProviderRequest(
                provider_policy_id=policy.provider_policy_id,
                provider=policy.provider,
                model=policy.model,
                temperature=policy.temperature,
                timeout_seconds=policy.timeout_seconds,
                max_retries=policy.max_retries,
                structured_output_mode=policy.structured_output_mode,
                tenant_id=request.tenant_id,
                region=request.region,
                product_id=request.product_id,
                frontend_id=request.frontend_id,
                scenario_session_id=request.scenario_session_id,
                job_id=request.job_id,
                workflow_id=request.workflow_id,
                step_id=request.step_id,
                action_run_id=request.action_run_id,
                action_type=request.action_type,
                action_config_id=request.action_config_id,
                prompt=request.prompt,
                prompt_ref=request.prompt_ref,
                response_schema=request.response_schema,
                messages=request.messages,
                metadata=request.metadata,
                fixture_key=request.fixture_key,
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                attempt_number=attempt_number,
                fallback_from_policy_id=fallback_from_policy_id,
            )
            started_at = utc_now()
            stored = None
            if repository is not None and should_persist:
                stored = repository.create(
                    ProviderCallRecord(
                        tenant_id=request.tenant_id,
                        region=request.region,
                        product_id=request.product_id,
                        frontend_id=request.frontend_id,
                        scenario_session_id=request.scenario_session_id,
                        job_id=request.job_id,
                        action_run_id=request.action_run_id,
                        workflow_id=request.workflow_id,
                        step_id=request.step_id,
                        action_type=request.action_type,
                        action_config_id=request.action_config_id,
                        provider_policy_id=policy.provider_policy_id,
                        provider=policy.provider,
                        model=policy.model,
                        status=ProviderCallStatus.running,
                        started_at=started_at,
                        metadata=self._build_provider_call_metadata(resolved_request),
                    )
                )
            attempt_started = perf_counter()

            try:
                adapter = self._adapters[policy.provider]
                raw_response = await asyncio.wait_for(
                    self._invoke_adapter(adapter, resolved_request),
                    timeout=policy.timeout_seconds,
                )
                response = self._normalize_internal_response(
                    raw_response,
                    provider_policy_id=policy.provider_policy_id,
                    provider=policy.provider,
                    model=policy.model,
                )
            except TimeoutError as exc:
                latency_ms = self._latency_ms(attempt_started)
                safe_message = (
                    f"provider request exceeded configured timeout of "
                    f"{policy.timeout_seconds} second(s)"
                )
                last_error = ProviderGatewayExecutionError(
                    provider_policy_id=policy.provider_policy_id,
                    provider=policy.provider,
                    model=policy.model,
                    error_code="provider_request_timed_out",
                    error_type="TimeoutError",
                    message=safe_message,
                )
                if repository is not None and stored is not None:
                    repository.update(
                        replace(
                            stored,
                            status=ProviderCallStatus.timed_out,
                            latency_ms=latency_ms,
                            error_code=last_error.error_code,
                            error_message_safe=safe_message,
                            completed_at=utc_now(),
                            metadata=self._build_provider_call_metadata(
                                resolved_request,
                                error_type=last_error.error_type,
                                error_code=last_error.error_code,
                                error_message_safe=safe_message,
                            ),
                        )
                    )
                self._emit_provider_failed(
                    event_context,
                    error_code=last_error.error_code,
                    result_status=ProviderCallStatus.timed_out.value,
                )
                if attempt_number == max_attempts:
                    break
                continue
            except asyncio.CancelledError:
                latency_ms = self._latency_ms(attempt_started)
                safe_message = "provider request cancelled"
                last_error = ProviderGatewayExecutionError(
                    provider_policy_id=policy.provider_policy_id,
                    provider=policy.provider,
                    model=policy.model,
                    error_code="provider_request_cancelled",
                    error_type="CancelledError",
                    message=safe_message,
                )
                if repository is not None and stored is not None:
                    repository.update(
                        replace(
                            stored,
                            status=ProviderCallStatus.failed,
                            latency_ms=latency_ms,
                            error_code=last_error.error_code,
                            error_message_safe=safe_message,
                            completed_at=utc_now(),
                            metadata=self._build_provider_call_metadata(
                                resolved_request,
                                error_type=last_error.error_type,
                                error_code=last_error.error_code,
                                error_message_safe=safe_message,
                            ),
                        )
                    )
                self._emit_provider_failed(
                    event_context,
                    error_code=last_error.error_code,
                    result_status=ProviderCallStatus.failed.value,
                )
                raise
            except Exception as exc:  # pragma: no cover - exercised by tests via fake adapter.
                latency_ms = self._latency_ms(attempt_started)
                safe_message = self._safe_error_message(exc)
                safe_error_code = self._safe_error_code(exc)
                last_error = ProviderGatewayExecutionError(
                    provider_policy_id=policy.provider_policy_id,
                    provider=policy.provider,
                    model=policy.model,
                    error_code=safe_error_code,
                    error_type=type(exc).__name__,
                    message=safe_message,
                )
                if repository is not None and stored is not None:
                    repository.update(
                        replace(
                            stored,
                            status=ProviderCallStatus.failed,
                            latency_ms=latency_ms,
                            error_code=last_error.error_code,
                            error_message_safe=safe_message,
                            completed_at=utc_now(),
                            metadata=self._build_provider_call_metadata(
                                resolved_request,
                                error_type=last_error.error_type,
                                error_code=last_error.error_code,
                                error_message_safe=safe_message,
                            ),
                        )
                    )
                self._emit_provider_failed(
                    event_context,
                    error_code=last_error.error_code,
                    result_status=ProviderCallStatus.failed.value,
                )
                if attempt_number == max_attempts:
                    break
                continue

            latency_ms = response.latency_ms or self._latency_ms(attempt_started)
            stored_response = replace(
                response,
                latency_ms=latency_ms,
            )
            if repository is not None and stored is not None:
                repository.update(
                    replace(
                        stored,
                        status=stored_response.status,
                        input_tokens=stored_response.usage.input_tokens,
                        output_tokens=stored_response.usage.output_tokens,
                        latency_ms=stored_response.latency_ms,
                        estimated_cost=stored_response.estimated_cost,
                        error_code=stored_response.error_code,
                        error_message_safe=stored_response.error_message_safe,
                        completed_at=utc_now(),
                        metadata=self._build_provider_call_metadata(
                            resolved_request,
                            response=stored_response,
                        ),
                    )
                )
            self._emit_provider_succeeded(
                event_context,
                result_status=stored_response.status.value,
            )
            return stored_response, None

        return None, last_error

    def execute(
        self,
        provider: str,
        request: ProviderRequest,
        context: ExecutionContext,
        *,
        provider_policy_id: str,
        action_run_id: str,
    ) -> ProviderResponse:
        adapter = self._adapters[provider]
        repository = self._resolve_provider_call_repository(None)
        event_context = replace(
            context,
            provider=provider,
            model=request.model,
            action_run_id=action_run_id,
            provider_policy_id=provider_policy_id,
        )
        self._emit_provider_started(event_context)
        should_persist = self._should_persist_context(event_context)
        stored = None
        if repository is not None and should_persist:
            stored = repository.create(
                ProviderCallRecord(
                    tenant_id=event_context.tenant_id,
                    region=event_context.region,
                    product_id=event_context.product_id,
                    frontend_id=event_context.frontend_id,
                    scenario_session_id=event_context.scenario_session_id or "",
                    job_id=event_context.job_id or "",
                    action_run_id=action_run_id,
                    workflow_id=event_context.workflow_id or "",
                    step_id=event_context.step_id or "",
                    action_type=event_context.action_type or "",
                    action_config_id=event_context.action_config_id or "",
                    provider_policy_id=provider_policy_id,
                    provider=provider,
                    model=request.model,
                    status=ProviderCallStatus.running,
                    started_at=utc_now(),
                    metadata={
                        "response_schema_present": request.response_schema is not None,
                        "provider_policy_id": provider_policy_id,
                    },
                )
            )

        started = perf_counter()
        try:
            raw_response = self._invoke_adapter_sync(adapter, request)
            response = self._normalize_compat_response(
                raw_response,
                provider=provider,
                model=request.model,
            )
        except Exception as exc:
            safe_error_code = self._safe_error_code(exc)
            safe_message = self._safe_error_message(exc)
            status = (
                ProviderCallStatus.timed_out if isinstance(exc, TimeoutError) else ProviderCallStatus.failed
            )
            if repository is not None and stored is not None:
                repository.update(
                    replace(
                        stored,
                        status=status,
                        latency_ms=self._latency_ms(started),
                        error_code=safe_error_code,
                        error_message_safe=safe_message,
                        completed_at=utc_now(),
                        metadata={
                            **stored.metadata,
                            "error": {
                                "code": safe_error_code,
                                "type": type(exc).__name__,
                                "message_safe": safe_message,
                            },
                        },
                    )
                )
            self._emit_provider_failed(
                event_context,
                error_code=safe_error_code,
                result_status=status.value,
            )
            raise

        latency_ms = response.latency_ms or self._latency_ms(started)
        normalized_response = replace(response, latency_ms=latency_ms)
        if repository is not None and stored is not None:
            repository.update(
                replace(
                    stored,
                    status=ProviderCallStatus.succeeded,
                    input_tokens=normalized_response.input_tokens,
                    output_tokens=normalized_response.output_tokens,
                    latency_ms=normalized_response.latency_ms,
                    estimated_cost=normalized_response.estimated_cost,
                    completed_at=utc_now(),
                    metadata={
                        **stored.metadata,
                        "provider": provider,
                        "model": request.model,
                    },
                )
            )
        self._emit_provider_succeeded(
            event_context,
            result_status=ProviderCallStatus.succeeded.value,
        )
        return normalized_response

    def _build_provider_call_metadata(
        self,
        request: ResolvedProviderRequest,
        *,
        response: ProviderResponse | None = None,
        error_type: str | None = None,
        error_code: str | None = None,
        error_message_safe: str | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "prompt_ref": request.prompt_ref,
            "request_id": request.request_id,
            "correlation_id": request.correlation_id,
            "fixture_key": request.fixture_key,
            "structured_output_mode": request.structured_output_mode.value,
            "temperature": request.temperature,
            "timeout": {"configured_seconds": request.timeout_seconds},
            "retry": {
                "attempt_number": request.attempt_number,
                "max_retries": request.max_retries,
            },
            "fallback_from_policy_id": request.fallback_from_policy_id,
            "request_payload": {
                "prompt_chars": len(request.prompt),
                "message_count": len(request.messages),
                "response_schema_present": request.response_schema is not None,
            },
            "request_metadata": self._sanitize_metadata(request.metadata),
        }
        if response is not None:
            metadata["response_metadata"] = self._sanitize_metadata(response.metadata)
        if error_type is not None or error_message_safe is not None:
            metadata["error"] = {
                "type": error_type,
                "code": error_code,
                "message_safe": error_message_safe,
            }
        return metadata

    async def _invoke_adapter(
        self,
        adapter: ProviderAdapter,
        request: ResolvedProviderRequest,
    ) -> Any:
        result = adapter.complete(request)
        if inspect.isawaitable(result):
            return await result
        return result

    def _invoke_adapter_sync(
        self,
        adapter: ProviderAdapter,
        request: ProviderRequest,
    ) -> Any:
        result = adapter.complete(request)
        if inspect.isawaitable(result):
            return asyncio.run(result)
        return result

    def _resolve_provider_call_repository(
        self,
        session: Session | None,
    ) -> Any | None:
        if self._provider_call_repository is not None:
            return self._provider_call_repository
        if session is None:
            raise TypeError(
                "ProviderGateway.request() requires a session when "
                "provider_call_repository is not injected"
            )
        return ProviderCallRepository(session)

    def _should_persist_provider_call(self, request: ProviderRequest) -> bool:
        return self._has_required_dimension(request.tenant_id) and self._has_required_dimension(
            request.region
        )

    def _should_persist_context(self, context: ExecutionContext) -> bool:
        return self._has_required_dimension(context.tenant_id) and self._has_required_dimension(
            context.region
        )

    def _has_required_dimension(self, value: str | None) -> bool:
        return isinstance(value, str) and value.strip() != ""

    def _latency_ms(self, started: float) -> int:
        return max(int((perf_counter() - started) * 1000), 0)

    def _safe_error_code(self, error: Exception) -> str:
        if isinstance(error, PlatformError):
            return error.code
        if isinstance(error, TimeoutError):
            return "provider_request_timed_out"
        return "provider_request_failed"

    def _safe_error_message(self, error: Exception) -> str:
        raw = str(error).strip() or type(error).__name__
        lowered = raw.lower()
        if any(secret_key in lowered for secret_key in _SECRET_KEYS):
            return "[redacted provider error]"
        return raw[:_MAX_STRING_LENGTH]

    def _event_context_from_request(
        self,
        request: InternalProviderRequest,
        *,
        provider: str,
        model: str,
    ) -> ExecutionContext:
        return ExecutionContext(
            tenant_id=request.tenant_id,
            region=request.region,
            product_id=request.product_id,
            frontend_id=request.frontend_id,
            scenario_session_id=request.scenario_session_id,
            job_id=request.job_id,
            workflow_id=request.workflow_id,
            step_id=request.step_id,
            action_type=request.action_type,
            action_config_id=request.action_config_id,
            provider=provider,
            model=model,
            action_run_id=request.action_run_id,
            provider_policy_id=request.provider_policy_id,
        )

    def _emit_provider_started(self, context: ExecutionContext) -> None:
        if self._event_emitter is None:
            return
        self._event_emitter.emit("provider.request_started", context)

    def _emit_provider_succeeded(
        self,
        context: ExecutionContext,
        *,
        result_status: str,
    ) -> None:
        if self._event_emitter is None:
            return
        self._event_emitter.emit(
            "provider.request_succeeded",
            context,
            result_status=result_status,
        )

    def _emit_provider_failed(
        self,
        context: ExecutionContext,
        *,
        error_code: str,
        result_status: str,
    ) -> None:
        if self._event_emitter is None:
            return
        self._event_emitter.emit(
            "provider.request_failed",
            context,
            result_status=result_status,
            properties={"error_code": error_code},
        )

    def _normalize_internal_response(
        self,
        response: Any,
        *,
        provider_policy_id: str,
        provider: str,
        model: str,
    ) -> InternalProviderResponse:
        if isinstance(response, InternalProviderResponse):
            return response
        normalized = self._normalize_compat_response(
            response,
            provider=provider,
            model=model,
        )
        return InternalProviderResponse(
            provider_policy_id=provider_policy_id,
            provider=normalized.provider,
            model=normalized.model,
            output_text=normalized.content,
            usage=ProviderUsage(
                input_tokens=normalized.input_tokens,
                output_tokens=normalized.output_tokens,
            ),
            latency_ms=normalized.latency_ms,
            estimated_cost=normalized.estimated_cost,
        )

    def _normalize_compat_response(
        self,
        response: Any,
        *,
        provider: str,
        model: str,
    ) -> ProviderResponse:
        if isinstance(response, ProviderResponse):
            return response
        if isinstance(response, InternalProviderResponse):
            return ProviderResponse(
                content=response.output_text,
                provider=response.provider,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                latency_ms=response.latency_ms,
                estimated_cost=response.estimated_cost,
            )
        raise TypeError(
            "provider adapter returned an unsupported response type: "
            f"{type(response).__name__}"
        )

    def _sanitize_metadata(self, value: Mapping[str, Any] | None) -> dict[str, Any]:
        if value is None:
            return {}
        return {
            str(key): self._sanitize_value(key=str(key), value=item, depth=0)
            for key, item in value.items()
        }

    def _sanitize_value(self, *, key: str, value: Any, depth: int) -> Any:
        if any(secret_key in key.lower() for secret_key in _SECRET_KEYS):
            return "[redacted]"
        if depth >= _MAX_NESTING_DEPTH:
            return "[truncated]"
        if value is None or isinstance(value, bool | int | float):
            return value
        if isinstance(value, str):
            return value[:_MAX_STRING_LENGTH]
        if isinstance(value, Mapping):
            items = list(value.items())[:_MAX_COLLECTION_ITEMS]
            return {
                str(child_key): self._sanitize_value(
                    key=str(child_key),
                    value=child_value,
                    depth=depth + 1,
                )
                for child_key, child_value in items
            }
        if isinstance(value, list | tuple):
            items = list(value)[:_MAX_COLLECTION_ITEMS]
            return [
                self._sanitize_value(
                    key=key,
                    value=item,
                    depth=depth + 1,
                )
                for item in items
            ]
        return str(value)[:_MAX_STRING_LENGTH]
