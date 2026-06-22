from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import replace
from time import perf_counter
from typing import Any

from sqlalchemy.orm import Session

from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.common.time import utc_now
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
        policy_resolver: ProviderPolicyResolver,
        provider_call_repository: Any | None = None,
    ) -> None:
        self._adapters = dict(adapters)
        self._policy_resolver = policy_resolver
        self._provider_call_repository = provider_call_repository

    async def request(
        self,
        request: ProviderRequest,
        *,
        session: Session | None = None,
    ) -> ProviderResponse:
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
        request: ProviderRequest,
        policy: ProviderPolicy,
        fallback_from_policy_id: str | None,
        session: Session | None,
        visited_policy_ids: set[str],
    ) -> ProviderResponse:
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
        request: ProviderRequest,
        policy: ProviderPolicy,
        fallback_from_policy_id: str | None,
        session: Session | None,
    ) -> tuple[ProviderResponse | None, ProviderGatewayExecutionError | None]:
        repository = self._resolve_provider_call_repository(session)
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
                response = await asyncio.wait_for(
                    adapter.complete(resolved_request),
                    timeout=policy.timeout_seconds,
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
                if attempt_number == max_attempts:
                    break
                continue
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
                        error_code=stored_response.error_type,
                        error_message_safe=stored_response.error_message_safe,
                        completed_at=utc_now(),
                        metadata=self._build_provider_call_metadata(
                            resolved_request,
                            response=stored_response,
                        ),
                    )
                )
            return stored_response, None

        return None, last_error

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
