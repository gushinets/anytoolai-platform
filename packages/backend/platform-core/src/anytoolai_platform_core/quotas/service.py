from __future__ import annotations

from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.identity.service import GuestIdentityNotFoundError
from anytoolai_platform_core.quotas.models import (
    QuotaPeriod,
    QuotaPolicy,
    QuotaState,
    QuotaUsageRecord,
)
from anytoolai_platform_core.quotas.repository import QuotaUsageRepository


class ProductNotFoundError(PlatformError):
    def __init__(self) -> None:
        super().__init__("product_not_found", "Product not found.")


class GuestIdentityRequiredError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "guest_identity_required",
            "Guest identity is required for this product.",
        )


class QuotaPolicyNotConfiguredError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "quota_policy_not_configured",
            "Quota policy is not configured for this product.",
        )


class QuotaExhaustedError(PlatformError):
    def __init__(self) -> None:
        super().__init__("quota_exhausted", "Guest quota exhausted.")


class GuestQuotaService:
    def __init__(
        self,
        *,
        config_registry: ConfigRegistry,
        quota_repository: QuotaUsageRepository,
        guest_repository: GuestIdentityRepository,
        event_emitter: EventEmitter,
    ) -> None:
        self._config_registry = config_registry
        self._quota_repository = quota_repository
        self._guest_repository = guest_repository
        self._event_emitter = event_emitter

    def check_quota(
        self,
        *,
        tenant_id: str,
        region: str,
        product_id: str,
        guest_id: str,
        frontend_id: str = "",
        emit_event: bool = True,
    ) -> QuotaState:
        policy = self._require_product_quota_policy(product_id)
        self._require_guest(
            guest_id,
            tenant_id=tenant_id,
            region=region,
        )
        usage = self._ensure_usage(
            tenant_id=tenant_id,
            region=region,
            guest_id=guest_id,
            product_id=product_id,
            policy=policy,
        )
        state = _state_from_usage(usage, policy)
        if emit_event:
            self._emit_quota_event(
                "quota.checked",
                state=state,
                tenant_id=tenant_id,
                region=region,
                frontend_id=frontend_id,
            )
        return state

    def consume_for_accepted_start(
        self,
        *,
        tenant_id: str,
        region: str,
        product_id: str,
        frontend_id: str,
        guest_id: str | None,
        scenario_id: str,
        scenario_session_id: str | None = None,
        scenario_chain_id: str | None = None,
    ) -> QuotaState | None:
        product = self._config_registry.get_product(product_id)
        if product is None:
            raise ProductNotFoundError()
        if not product.quota_policy_ref:
            return None
        if not guest_id:
            raise GuestIdentityRequiredError()

        policy = self._require_quota_policy(product.quota_policy_ref)
        self._require_guest(
            guest_id,
            tenant_id=tenant_id,
            region=region,
        )
        usage = self._ensure_usage(
            tenant_id=tenant_id,
            region=region,
            guest_id=guest_id,
            product_id=product_id,
            policy=policy,
        )
        checked_state = _state_from_usage(usage, policy)
        context_kwargs = {
            "tenant_id": tenant_id,
            "region": region,
            "frontend_id": frontend_id,
            "scenario_id": scenario_id,
            "scenario_session_id": scenario_session_id,
            "scenario_chain_id": scenario_chain_id,
        }
        self._emit_quota_event(
            "quota.checked",
            state=checked_state,
            **context_kwargs,
        )

        consumed = self._quota_repository.consume_if_available(usage)
        if consumed is None:
            latest = self._quota_repository.get(usage.id) or usage
            exhausted_state = _state_from_usage(latest, policy)
            self._emit_quota_event(
                "quota.exhausted",
                state=exhausted_state,
                result_status="failed",
                error_code="quota_exhausted",
                **context_kwargs,
            )
            raise QuotaExhaustedError()

        consumed_state = _state_from_usage(consumed, policy)
        self._emit_quota_event(
            "quota.consumed",
            state=consumed_state,
            result_status="accepted",
            **context_kwargs,
        )
        return consumed_state

    def _require_product_quota_policy(self, product_id: str) -> QuotaPolicy:
        product = self._config_registry.get_product(product_id)
        if product is None:
            raise ProductNotFoundError()
        if not product.quota_policy_ref:
            raise QuotaPolicyNotConfiguredError()
        return self._require_quota_policy(product.quota_policy_ref)

    def _require_quota_policy(self, quota_policy_ref: str) -> QuotaPolicy:
        policy = self._config_registry.get_quota_policy(quota_policy_ref)
        if policy is None:
            raise QuotaPolicyNotConfiguredError()
        return policy

    def _require_guest(
        self,
        guest_id: str,
        *,
        tenant_id: str,
        region: str,
    ) -> None:
        guest = self._guest_repository.get(
            guest_id,
            tenant_id=tenant_id,
            region=region,
        )
        if guest is None:
            raise GuestIdentityNotFoundError()

    def _ensure_usage(
        self,
        *,
        tenant_id: str,
        region: str,
        guest_id: str,
        product_id: str,
        policy: QuotaPolicy,
    ) -> QuotaUsageRecord:
        return self._quota_repository.ensure_usage(
            tenant_id=tenant_id,
            region=region,
            guest_id=guest_id,
            product_id=product_id,
            quota_policy_id=policy.quota_policy_id,
            period_key=_period_key(policy),
            limit_count=policy.limit_count,
            metadata={"unit": policy.unit.value, "period": policy.period.value},
        )

    def _emit_quota_event(
        self,
        event_type: str,
        *,
        state: QuotaState,
        tenant_id: str,
        region: str,
        frontend_id: str = "",
        scenario_id: str | None = None,
        scenario_session_id: str | None = None,
        scenario_chain_id: str | None = None,
        result_status: str | None = None,
        error_code: str | None = None,
    ) -> None:
        properties = {
            "quota_policy_id": state.quota_policy_id,
            "unit": state.unit.value,
            "period": state.period.value,
            "period_key": state.period_key,
            "limit_count": state.limit_count,
            "used_count": state.used_count,
            "remaining_count": state.remaining_count,
            "exhausted": state.exhausted,
        }
        if scenario_id is not None:
            properties["scenario_id"] = scenario_id
        if error_code is not None:
            properties["error_code"] = error_code

        self._event_emitter.emit(
            event_type,
            ExecutionContext(
                tenant_id=tenant_id,
                region=region,
                product_id=state.product_id,
                frontend_id=frontend_id,
                guest_id=state.guest_id,
                scenario_session_id=scenario_session_id,
                scenario_chain_id=scenario_chain_id,
            ),
            result_status=result_status,
            properties=properties,
        )


def _state_from_usage(record: QuotaUsageRecord, policy: QuotaPolicy) -> QuotaState:
    remaining_count = max(record.limit_count - record.used_count, 0)
    return QuotaState(
        guest_id=record.guest_id,
        product_id=record.product_id,
        quota_policy_id=record.quota_policy_id,
        unit=policy.unit,
        period=policy.period,
        period_key=record.period_key,
        limit_count=record.limit_count,
        used_count=record.used_count,
        remaining_count=remaining_count,
        exhausted=remaining_count <= 0,
    )


def _period_key(policy: QuotaPolicy) -> str:
    if policy.period is QuotaPeriod.lifetime:
        return "lifetime"
    raise QuotaPolicyNotConfiguredError()
