from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import replace
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
    ProviderRequest,
    ProviderResponse,
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
        resolved_request: ResolvedProviderRequest | None = None,
    ) -> None:
        super().__init__(message)
        self.provider_policy_id = provider_policy_id
        self.provider = provider
        self.model = model
        self.error_code = error_code
        self.error_type = error_type
        self.message = message
        self.resolved_request = resolved_request


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
        request: ProviderRequest,
        *,
        session: Session | None = None,
    ) -> ProviderResponse:
        if self._policy_resolver is None:
            raise TypeError(
                "ProviderGateway.request() requires a policy_resolver configured on the gateway"
            )

        initial_policy = self._policy_resolver.resolve(request.provider_policy_id)
        initial_context = self._event_context_from_request(
            request,
            provider=initial_policy.provider,
            model=initial_policy.model,
        )
        self._emit_provider_started(initial_context)

        repository = self._resolve_provider_call_repository(session)
        should_persist = self._should_persist_provider_call(request)
        stored = None
        if repository is not None and should_persist:
            initial_resolved_request = self._resolved_request_from_policy(
                request=request,
                policy=initial_policy,
                fallback_from_policy_id=None,
            )
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
                    provider_policy_id=initial_policy.provider_policy_id,
                    provider=initial_policy.provider,
                    model=initial_policy.model,
                    status=ProviderCallStatus.running,
                    started_at=utc_now(),
                    metadata=self._build_provider_call_metadata(initial_resolved_request),
                )
            )

        started = perf_counter()
        try:
            resolved_request, response = await self._execute_policy_chain(
                request=request,
                policy=initial_policy,
                fallback_from_policy_id=None,
                visited_policy_ids=set(),
            )
        except asyncio.CancelledError:
            latency_ms = self._latency_ms(started)
            safe_message = "provider request cancelled"
            if repository is not None and stored is not None:
                repository.update(
                    replace(
                        stored,
                        status=ProviderCallStatus.failed,
                        latency_ms=latency_ms,
                        error_code="provider_request_cancelled",
                        error_message_safe=safe_message,
                        completed_at=utc_now(),
                    )
                )
            self._emit_provider_failed(
                initial_context,
                error_code="provider_request_cancelled",
                result_status=ProviderCallStatus.failed.value,
            )
            raise
        except ProviderGatewayExecutionError as exc:
            latency_ms = self._latency_ms(started)
            failure_request = exc.resolved_request or self._resolved_request_from_policy(
                request=request,
                policy=initial_policy,
                fallback_from_policy_id=None,
            )
            failure_context = replace(
                initial_context,
                provider_policy_id=failure_request.provider_policy_id,
                provider=failure_request.provider,
                model=failure_request.model,
            )
            if repository is not None and stored is not None:
                repository.update(
                    replace(
                        stored,
                        provider_policy_id=failure_request.provider_policy_id,
                        provider=failure_request.provider,
                        model=failure_request.model,
                        status=(
                            ProviderCallStatus.timed_out
                            if exc.error_code == "provider_request_timed_out"
                            else ProviderCallStatus.failed
                        ),
                        latency_ms=latency_ms,
                        error_code=exc.error_code,
                        error_message_safe=exc.message,
                        completed_at=utc_now(),
                        metadata=self._build_provider_call_metadata(
                            failure_request,
                            error_type=exc.error_type,
                            error_code=exc.error_code,
                            error_message_safe=exc.message,
                        ),
                    )
                )
            self._emit_provider_failed(
                failure_context,
                error_code=exc.error_code,
                result_status=(
                    ProviderCallStatus.timed_out.value
                    if exc.error_code == "provider_request_timed_out"
                    else ProviderCallStatus.failed.value
                ),
            )
            raise

        latency_ms = response.latency_ms or self._latency_ms(started)
        stored_response = replace(response, latency_ms=latency_ms)
        success_context = replace(
            initial_context,
            provider_policy_id=resolved_request.provider_policy_id,
            provider=stored_response.provider,
            model=stored_response.model,
        )
        if repository is not None and stored is not None:
            repository.update(
                replace(
                    stored,
                    provider_policy_id=resolved_request.provider_policy_id,
                    provider=stored_response.provider,
                    model=stored_response.model,
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
        if self._is_success_status(stored_response.status):
            self._emit_provider_succeeded(
                success_context,
                result_status=stored_response.status.value,
            )
        else:
            self._emit_provider_failed(
                success_context,
                error_code=self._response_error_code(stored_response),
                result_status=stored_response.status.value,
            )
        return stored_response

    async def _execute_policy_chain(
        self,
        *,
        request: ProviderRequest,
        policy: ProviderPolicy,
        fallback_from_policy_id: str | None,
        visited_policy_ids: set[str],
    ) -> tuple[ResolvedProviderRequest, ProviderResponse]:
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

        resolved_request = self._resolved_request_from_policy(
            request=request,
            policy=policy,
            fallback_from_policy_id=fallback_from_policy_id,
        )

        root_exception: Exception | None = None
        try:
            adapter = self._adapters[policy.provider]
            raw_response = await asyncio.wait_for(
                self._invoke_adapter(adapter, resolved_request),
                timeout=policy.timeout_seconds,
            )
            response = self._normalize_internal_response(raw_response)
            return resolved_request, response
        except TimeoutError as exc:
            root_exception = exc
            error = ProviderGatewayExecutionError(
                provider_policy_id=policy.provider_policy_id,
                provider=policy.provider,
                model=policy.model,
                error_code="provider_request_timed_out",
                error_type="TimeoutError",
                message=(
                    "provider request exceeded configured timeout of "
                    f"{policy.timeout_seconds} second(s)"
                ),
                resolved_request=resolved_request,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - exercised by tests via adapters.
            root_exception = exc
            error = ProviderGatewayExecutionError(
                provider_policy_id=policy.provider_policy_id,
                provider=policy.provider,
                model=policy.model,
                error_code=self._safe_error_code(exc),
                error_type=type(exc).__name__,
                message=self._safe_error_message(exc),
                resolved_request=resolved_request,
            )

        if policy.fallback_policy is not None:
            fallback_policy = self._policy_resolver.resolve(policy.fallback_policy)
            next_visited = set(visited_policy_ids)
            next_visited.add(policy.provider_policy_id)
            return await self._execute_policy_chain(
                request=request,
                policy=fallback_policy,
                fallback_from_policy_id=policy.provider_policy_id,
                visited_policy_ids=next_visited,
            )

        if root_exception is None:
            raise error
        raise error from root_exception

    def _resolved_request_from_policy(
        self,
        *,
        request: ProviderRequest,
        policy: ProviderPolicy,
        fallback_from_policy_id: str | None,
    ) -> ResolvedProviderRequest:
        return ResolvedProviderRequest(
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
            attempt_number=1,
            fallback_from_policy_id=fallback_from_policy_id,
        )

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
                "owned_by": "litellm" if request.provider == "litellm" else "adapter",
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
        if request.provider == "litellm":
            metadata["litellm"] = {"model_group": request.model}
        if response is not None:
            metadata["response_metadata"] = self._sanitize_metadata(response.metadata)
            litellm_metadata = response.metadata.get("litellm")
            if request.provider == "litellm" and isinstance(litellm_metadata, Mapping):
                metadata["litellm"] = {
                    **metadata.get("litellm", {}),
                    **self._sanitize_metadata(litellm_metadata),
                }
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

    def _is_success_status(self, status: ProviderCallStatus) -> bool:
        return status is ProviderCallStatus.succeeded

    def _response_error_code(self, response: ProviderResponse) -> str:
        if response.error_code:
            return response.error_code
        if response.status is ProviderCallStatus.timed_out:
            return "provider_request_timed_out"
        return "provider_request_failed"

    def _event_context_from_request(
        self,
        request: ProviderRequest,
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
    ) -> ProviderResponse:
        if isinstance(response, ProviderResponse):
            return response
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
