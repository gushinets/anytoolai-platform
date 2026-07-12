from __future__ import annotations

import asyncio
import inspect
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from time import perf_counter
from typing import Any

from sqlalchemy.orm import Session

from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter, enrich_event_context
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.providers.adapters.base import ProviderAdapter
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.providers.adapters.litellm import (
    LiteLLMProviderAdapter,
    build_litellm_router,
)
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
from anytoolai_platform_core.storage.transactions import (
    register_rollback_recovery_callback,
    transaction_boundary,
)

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
_GENERIC_PROVIDER_FAILURE_MESSAGE = "Provider request failed."
_PROVIDER_TIMEOUT_MESSAGE = "Provider request timed out."
_PROVIDER_CANCELLED_MESSAGE = "Provider request cancelled."


@dataclass
class _GatewayAttemptState:
    repository: Any
    should_persist: bool
    recovery_session: Session | None
    physical_call_count: int = 0


class ProviderGatewayExecutionError(RuntimeError):
    def __init__(
        self,
        *,
        provider_policy_ref: str,
        provider: str,
        model: str,
        error_code: str,
        error_type: str,
        message: str,
        resolved_request: ResolvedProviderRequest | None = None,
        failure_kind: str | None = None,
    ) -> None:
        super().__init__(message)
        self.provider_policy_ref = provider_policy_ref
        self.provider = provider
        self.model = model
        self.error_code = error_code
        self.error_type = error_type
        self.message = message
        self.resolved_request = resolved_request
        self.failure_kind = failure_kind


class LazyLiteLLMProviderAdapter:
    """Delay router/env resolution until a LiteLLM-backed job actually runs."""

    def __init__(self, config_root: Path | None = None) -> None:
        self._config_root = config_root
        self._adapter: LiteLLMProviderAdapter | None = None

    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse:
        if self._adapter is None:
            self._adapter = LiteLLMProviderAdapter(build_litellm_router(self._config_root))
        return await self._adapter.complete(request)


def build_default_provider_adapters(
    config_root: Path | None = None,
) -> dict[str, ProviderAdapter]:
    """Build production adapters without exposing concrete adapters to composition roots."""

    return {
        "fake": FakeProviderAdapter(),
        "litellm": LazyLiteLLMProviderAdapter(config_root),
    }


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

        repository = self._resolve_provider_call_repository(session)
        gateway_state = _GatewayAttemptState(
            repository=repository,
            should_persist=self._should_persist_provider_call(request),
            recovery_session=session,
        )
        initial_policy = self._policy_resolver.resolve(request.provider_policy_ref)
        return await self._execute_policy_chain(
            request=request,
            policy=initial_policy,
            fallback_from_policy_ref=None,
            visited_policy_refs=set(),
            gateway_state=gateway_state,
        )

    async def _execute_policy_chain(
        self,
        *,
        request: ProviderRequest,
        policy: ProviderPolicy,
        fallback_from_policy_ref: str | None,
        visited_policy_refs: set[str],
        gateway_state: _GatewayAttemptState,
    ) -> ProviderResponse:
        if policy.provider_policy_ref in visited_policy_refs:
            raise ProviderGatewayExecutionError(
                provider_policy_ref=policy.provider_policy_ref,
                provider=policy.provider,
                model=policy.model,
                error_code="provider_policy_cycle",
                error_type="ProviderPolicyCycleError",
                message=(
                    "provider policy fallback cycle detected for "
                    f"{policy.provider_policy_ref}"
                ),
                failure_kind="policy_cycle",
            )

        resolved_request = self._resolved_request_from_policy(
            request=request,
            policy=policy,
            fallback_from_policy_ref=fallback_from_policy_ref,
        )
        try:
            return await self._execute_transport_attempts(
                resolved_request,
                gateway_state=gateway_state,
            )
        except ProviderGatewayExecutionError as exc:
            error = exc
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive wrapper
            error = ProviderGatewayExecutionError(
                provider_policy_ref=policy.provider_policy_ref,
                provider=policy.provider,
                model=policy.model,
                error_code=self._safe_error_code(exc),
                error_type=type(exc).__name__,
                message=self._safe_error_message(exc),
                resolved_request=resolved_request,
                failure_kind="gateway",
            )

        if policy.fallback_policy is not None:
            fallback_policy = self._policy_resolver.resolve(policy.fallback_policy)
            next_visited = set(visited_policy_refs)
            next_visited.add(policy.provider_policy_ref)
            return await self._execute_policy_chain(
                request=request,
                policy=fallback_policy,
                fallback_from_policy_ref=policy.provider_policy_ref,
                visited_policy_refs=next_visited,
                gateway_state=gateway_state,
            )

        raise error

    async def _execute_transport_attempts(
        self,
        request: ResolvedProviderRequest,
        *,
        gateway_state: _GatewayAttemptState,
    ) -> ProviderResponse:
        last_error: ProviderGatewayExecutionError | None = None
        max_attempts = max(request.retry_policy.transport.max_attempts, 1)
        for transport_attempt_index in range(1, max_attempts + 1):
            if (
                gateway_state.physical_call_count
                >= request.retry_policy.hard_limits.max_physical_provider_calls_per_action
            ):
                raise ProviderGatewayExecutionError(
                    provider_policy_ref=request.provider_policy_ref,
                    provider=request.provider,
                    model=request.model,
                    error_code="provider_physical_call_limit_exceeded",
                    error_type="ProviderPhysicalCallLimitExceeded",
                    message="provider physical call limit exceeded",
                    resolved_request=request,
                    failure_kind="hard_limit",
                )

            physical_call_index = gateway_state.physical_call_count + 1
            gateway_state.physical_call_count = physical_call_index
            attempt_request = replace(
                request,
                transport_attempt_index=transport_attempt_index,
                physical_call_index=physical_call_index,
            )
            provider_call = ProviderCallRecord(
                tenant_id=attempt_request.tenant_id,
                region=attempt_request.region,
                product_id=attempt_request.product_id,
                frontend_id=attempt_request.frontend_id,
                scenario_session_id=attempt_request.scenario_session_id,
                job_id=attempt_request.job_id,
                action_run_id=attempt_request.action_run_id,
                workflow_id=attempt_request.workflow_id,
                workflow_version=attempt_request.workflow_version,
                step_id=attempt_request.step_id,
                action_type=attempt_request.action_type,
                action_config_id=attempt_request.action_config_id,
                provider_policy_ref=attempt_request.provider_policy_ref,
                provider=attempt_request.provider,
                model=attempt_request.model,
                gateway_backend=attempt_request.provider,
                gateway_model=attempt_request.model,
                semantic_attempt_index=attempt_request.semantic_attempt_index,
                transport_attempt_index=attempt_request.transport_attempt_index,
                physical_call_index=attempt_request.physical_call_index,
                status=ProviderCallStatus.running,
                started_at=utc_now(),
                pydantic_run_id=attempt_request.pydantic_run_id,
                metadata=self._build_provider_call_metadata(attempt_request),
            )
            context = self._event_context_from_resolved_request(attempt_request)
            self._emit_provider_started(
                context,
                provider_call=provider_call,
            )

            stored = None
            recovery_state: dict[str, ProviderCallRecord] | None = None
            if gateway_state.should_persist:
                stored = gateway_state.repository.create(provider_call)
                recovery_state = {"record": stored}
                self._register_provider_call_recovery(
                    session=gateway_state.recovery_session,
                    recovery_state=recovery_state,
                    emit_events=self._event_emitter is not None,
                )

            started = perf_counter()
            try:
                adapter = self._adapters[attempt_request.provider]
                raw_response = await asyncio.wait_for(
                    self._invoke_adapter(adapter, attempt_request),
                    timeout=attempt_request.timeout_seconds,
                )
                response = self._normalize_internal_response(raw_response)
                response = replace(
                    response,
                    latency_ms=response.latency_ms or self._latency_ms(started),
                    pydantic_run_id=attempt_request.pydantic_run_id
                    or response.pydantic_run_id,
                )
                if self._is_success_status(response.status):
                    updated = self._update_provider_call_success(
                        stored=stored,
                        provider_call=provider_call,
                        request=attempt_request,
                        response=response,
                        gateway_state=gateway_state,
                    )
                    self._update_recovery_state(
                        recovery_state,
                        updated,
                    )
                    self._emit_provider_succeeded(
                        context,
                        provider_call=provider_call,
                        response=response,
                    )
                    return response

                error = ProviderGatewayExecutionError(
                    provider_policy_ref=attempt_request.provider_policy_ref,
                    provider=response.provider,
                    model=response.model,
                    error_code=self._response_error_code(response),
                    error_type=response.error_type or type(response).__name__,
                    message=self._safe_response_error_message(response),
                    resolved_request=attempt_request,
                    failure_kind=response.failure_kind
                    or self._failure_kind_for_status(response.status),
                )
            except asyncio.CancelledError:
                latency_ms = self._latency_ms(started)
                error = ProviderGatewayExecutionError(
                    provider_policy_ref=attempt_request.provider_policy_ref,
                    provider=attempt_request.provider,
                    model=attempt_request.model,
                    error_code="provider_request_cancelled",
                    error_type="CancelledError",
                    message=_PROVIDER_CANCELLED_MESSAGE,
                    resolved_request=attempt_request,
                    failure_kind="cancelled",
                )
                updated = self._update_provider_call_failure(
                    stored=stored,
                    provider_call=provider_call,
                    request=attempt_request,
                    gateway_state=gateway_state,
                    error=error,
                    latency_ms=latency_ms,
                )
                self._update_recovery_state(
                    recovery_state,
                    updated,
                )
                self._emit_provider_failed(
                    context,
                    provider_call=provider_call,
                    error=error,
                )
                raise
            except TimeoutError:
                error = ProviderGatewayExecutionError(
                    provider_policy_ref=attempt_request.provider_policy_ref,
                    provider=attempt_request.provider,
                    model=attempt_request.model,
                    error_code="provider_request_timed_out",
                    error_type="TimeoutError",
                    message=_PROVIDER_TIMEOUT_MESSAGE,
                    resolved_request=attempt_request,
                    failure_kind="timeout",
                )
            except ProviderGatewayExecutionError as exc:  # pragma: no cover - defensive seam
                error = exc
            except Exception as exc:  # pragma: no cover - exercised by tests via adapters
                error = ProviderGatewayExecutionError(
                    provider_policy_ref=attempt_request.provider_policy_ref,
                    provider=attempt_request.provider,
                    model=attempt_request.model,
                    error_code=self._safe_error_code(exc),
                    error_type=type(exc).__name__,
                    message=self._safe_error_message(exc),
                    resolved_request=attempt_request,
                    failure_kind="transport",
                )

            latency_ms = self._latency_ms(started)
            updated = self._update_provider_call_failure(
                stored=stored,
                provider_call=provider_call,
                request=attempt_request,
                gateway_state=gateway_state,
                error=error,
                latency_ms=latency_ms,
            )
            self._update_recovery_state(
                recovery_state,
                updated,
            )
            self._emit_provider_failed(
                context,
                provider_call=provider_call,
                error=error,
            )
            last_error = error
            if transport_attempt_index == max_attempts:
                raise error

        if last_error is None:  # pragma: no cover - defensive
            raise RuntimeError("transport loop exhausted without a provider error")
        raise last_error

    def _update_provider_call_success(
        self,
        *,
        stored: ProviderCallRecord | None,
        provider_call: ProviderCallRecord,
        request: ResolvedProviderRequest,
        response: ProviderResponse,
        gateway_state: _GatewayAttemptState,
    ) -> ProviderCallRecord | None:
        if not gateway_state.should_persist or stored is None:
            return None
        return gateway_state.repository.update(
            replace(
                stored,
                provider=response.provider,
                model=response.model,
                status=response.status,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                total_tokens=response.usage.total_tokens,
                latency_ms=response.latency_ms,
                estimated_cost=response.estimated_cost,
                failure_kind=response.failure_kind,
                http_status=response.http_status,
                pydantic_run_id=response.pydantic_run_id,
                litellm_response_id=response.litellm_response_id,
                completed_at=utc_now(),
                metadata=self._build_provider_call_metadata(
                    request,
                    response=response,
                ),
            )
        )

    def _update_provider_call_failure(
        self,
        *,
        stored: ProviderCallRecord | None,
        provider_call: ProviderCallRecord,
        request: ResolvedProviderRequest,
        gateway_state: _GatewayAttemptState,
        error: ProviderGatewayExecutionError,
        latency_ms: int,
    ) -> ProviderCallRecord | None:
        if not gateway_state.should_persist or stored is None:
            return None
        return gateway_state.repository.update(
            replace(
                stored,
                status=(
                    ProviderCallStatus.timed_out
                    if error.error_code == "provider_request_timed_out"
                    else ProviderCallStatus.failed
                ),
                latency_ms=latency_ms,
                error_code=error.error_code,
                error_message_safe=error.message,
                failure_kind=error.failure_kind,
                pydantic_run_id=request.pydantic_run_id,
                completed_at=utc_now(),
                metadata=self._build_provider_call_metadata(
                    request,
                    error_type=error.error_type,
                    error_code=error.error_code,
                    error_message_safe=error.message,
                    failure_kind=error.failure_kind,
                ),
            )
        )

    def _resolved_request_from_policy(
        self,
        *,
        request: ProviderRequest,
        policy: ProviderPolicy,
        fallback_from_policy_ref: str | None,
    ) -> ResolvedProviderRequest:
        return ResolvedProviderRequest(
            provider_policy_ref=policy.provider_policy_ref,
            provider=policy.provider,
            model=policy.model,
            temperature=policy.temperature,
            timeout_seconds=policy.timeout_seconds,
            retry_policy=policy.retry_policy,
            structured_output_mode=policy.structured_output_mode,
            tenant_id=request.tenant_id,
            region=request.region,
            product_id=request.product_id,
            frontend_id=request.frontend_id,
            scenario_session_id=request.scenario_session_id,
            job_id=request.job_id,
            workflow_id=request.workflow_id,
            workflow_version=request.workflow_version,
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
            semantic_attempt_index=request.semantic_attempt_index,
            pydantic_run_id=request.pydantic_run_id,
            fallback_from_policy_ref=fallback_from_policy_ref,
        )

    def _build_provider_call_metadata(
        self,
        request: ResolvedProviderRequest,
        *,
        response: ProviderResponse | None = None,
        error_type: str | None = None,
        error_code: str | None = None,
        error_message_safe: str | None = None,
        failure_kind: str | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "prompt_ref": request.prompt_ref,
            "request_id": request.request_id,
            "correlation_id": request.correlation_id,
            "fixture_key": request.fixture_key,
            "structured_output_mode": request.structured_output_mode.value,
            "temperature": request.temperature,
            "timeout": {"configured_seconds": request.timeout_seconds},
            "retry_policy": {
                "transport": {
                    "owner": request.retry_policy.transport.owner,
                    "max_attempts": request.retry_policy.transport.max_attempts,
                    "litellm_num_retries_per_attempt": request.retry_policy.transport.litellm_num_retries_per_attempt,
                },
                "validation": {
                    "owner": request.retry_policy.validation.owner,
                    "max_attempts": request.retry_policy.validation.max_attempts,
                },
                "hard_limits": {
                    "max_physical_provider_calls_per_action": request.retry_policy.hard_limits.max_physical_provider_calls_per_action,
                },
            },
            "attempts": {
                "semantic_attempt_index": request.semantic_attempt_index,
                "transport_attempt_index": request.transport_attempt_index,
                "physical_call_index": request.physical_call_index,
                "pydantic_run_id": request.pydantic_run_id,
            },
            "fallback_from_policy_ref": request.fallback_from_policy_ref,
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
            metadata["response"] = {
                "http_status": response.http_status,
                "litellm_response_id": response.litellm_response_id,
                "total_tokens": response.usage.total_tokens,
            }
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
                "failure_kind": failure_kind,
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
    ) -> Any:
        if self._provider_call_repository is not None:
            return self._provider_call_repository
        if session is None:
            raise TypeError(
                "ProviderGateway.request() requires a session when "
                "provider_call_repository is not injected"
            )
        return ProviderCallRepository(session)

    def _register_provider_call_recovery(
        self,
        *,
        session: Session | None,
        recovery_state: dict[str, ProviderCallRecord],
        emit_events: bool,
    ) -> None:
        if session is None:
            return
        register_rollback_recovery_callback(
            session,
            lambda recovery_session_factory: _persist_provider_call_after_rollback(
                recovery_session_factory,
                recovery_state["record"],
                emit_events=emit_events,
            ),
        )

    @staticmethod
    def _update_recovery_state(
        recovery_state: dict[str, ProviderCallRecord] | None,
        updated_record: ProviderCallRecord | None,
    ) -> None:
        if recovery_state is None or updated_record is None:
            return
        recovery_state["record"] = updated_record

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
        return self._safe_message_for_code(self._safe_error_code(error))

    def _safe_response_error_message(self, response: ProviderResponse) -> str:
        return self._safe_message_for_code(self._response_error_code(response))

    def _safe_message_for_code(self, error_code: str) -> str:
        if error_code == "provider_request_timed_out":
            return _PROVIDER_TIMEOUT_MESSAGE
        if error_code == "provider_request_cancelled":
            return _PROVIDER_CANCELLED_MESSAGE
        return _GENERIC_PROVIDER_FAILURE_MESSAGE

    def _is_success_status(self, status: ProviderCallStatus) -> bool:
        return status is ProviderCallStatus.succeeded

    def _response_error_code(self, response: ProviderResponse) -> str:
        if response.error_code:
            return response.error_code
        if response.status is ProviderCallStatus.timed_out:
            return "provider_request_timed_out"
        return "provider_request_failed"

    def _failure_kind_for_status(self, status: ProviderCallStatus) -> str:
        if status is ProviderCallStatus.timed_out:
            return "timeout"
        return "response_failure"

    def _event_context_from_resolved_request(
        self,
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

    def _emit_provider_started(
        self,
        context: ExecutionContext,
        *,
        provider_call: ProviderCallRecord,
    ) -> None:
        if self._event_emitter is None:
            return
        self._event_emitter.emit(
            "provider.request_started",
            self._provider_event_context(
                context,
                provider_call=provider_call,
                pydantic_run_id=provider_call.pydantic_run_id,
            ),
            properties=self._provider_event_properties(provider_call=provider_call),
        )

    def _emit_provider_succeeded(
        self,
        context: ExecutionContext,
        *,
        provider_call: ProviderCallRecord,
        response: ProviderResponse,
    ) -> None:
        if self._event_emitter is None:
            return
        self._event_emitter.emit(
            "provider.request_succeeded",
            self._provider_event_context(
                context,
                provider_call=provider_call,
                pydantic_run_id=response.pydantic_run_id,
                litellm_response_id=response.litellm_response_id,
            ),
            result_status=response.status.value,
            properties=self._provider_event_properties(
                provider_call=provider_call,
                pydantic_run_id=response.pydantic_run_id,
                litellm_response_id=response.litellm_response_id,
                total_tokens=response.usage.total_tokens,
                http_status=response.http_status,
            ),
        )

    def _emit_provider_failed(
        self,
        context: ExecutionContext,
        *,
        provider_call: ProviderCallRecord,
        error: ProviderGatewayExecutionError,
    ) -> None:
        if self._event_emitter is None:
            return
        self._event_emitter.emit(
            "provider.request_failed",
            self._provider_event_context(
                context,
                provider_call=provider_call,
                pydantic_run_id=provider_call.pydantic_run_id,
            ),
            result_status=(
                ProviderCallStatus.timed_out.value
                if error.error_code == "provider_request_timed_out"
                else ProviderCallStatus.failed.value
            ),
            properties=self._provider_event_properties(
                provider_call=provider_call,
                pydantic_run_id=provider_call.pydantic_run_id,
                error_code=error.error_code,
                failure_kind=error.failure_kind,
            ),
        )

    def _provider_event_context(
        self,
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
        self,
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


def _persist_provider_call_after_rollback(
    recovery_session_factory: Any,
    record: ProviderCallRecord,
    *,
    emit_events: bool,
) -> None:
    with transaction_boundary(recovery_session_factory) as recovery_session:
        repository = ProviderCallRepository(recovery_session)
        existing = repository.get(record.id)
        if existing is None:
            stored = repository.create(record)
            if emit_events:
                _emit_recovered_provider_events(recovery_session, stored)
            return
        repository.update(record)


def _metadata_str(metadata: Mapping[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) and value else None


def _emit_recovered_provider_events(
    session: Session,
    record: ProviderCallRecord,
) -> None:
    event_emitter = EventEmitter(
        EventLogRepository(session),
    )
    context = _provider_event_context_from_record(record)
    event_emitter.emit(
        "provider.request_started",
        context,
        properties=_provider_event_properties_from_record(record),
    )
    if record.status is ProviderCallStatus.succeeded:
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
        )
        return

    if record.status in (ProviderCallStatus.failed, ProviderCallStatus.timed_out):
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
