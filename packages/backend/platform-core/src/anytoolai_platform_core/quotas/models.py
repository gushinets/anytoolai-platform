from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from anytoolai_platform_core.common.ids import new_id
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.scenarios.models import ScenarioSessionSnapshot

if TYPE_CHECKING:
    from anytoolai_platform_core.artifacts.models import ArtifactRecord
    from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
    from anytoolai_platform_core.workflows.models import JobRecord


class QuotaUnit(StrEnum):
    scenario_run = "scenario_run"


class QuotaPeriod(StrEnum):
    lifetime = "lifetime"
    calendar_day = "calendar_day"
    calendar_week = "calendar_week"
    calendar_month = "calendar_month"


class QuotaDimension(StrEnum):
    product = "product"
    scenario = "scenario"


MAX_ALLOWANCE_QUANTITY = 2**53 - 1


class ExecutionOwnerKind(StrEnum):
    guest = "guest"
    portal_user = "portal_user"


class ReservationState(StrEnum):
    reserved = "reserved"
    consumed = "consumed"
    released = "released"


class ExecutionReplayNamespace(StrEnum):
    start = "start"
    handoff = "handoff"


@dataclass(frozen=True)
class ExecutionOwner:
    tenant_id: str
    region: str
    owner_kind: ExecutionOwnerKind
    owner_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.owner_kind, ExecutionOwnerKind):
            raise ValueError("execution owner kind must be an ExecutionOwnerKind")
        if not all(
            isinstance(value, str) and value
            for value in (
                self.tenant_id,
                self.region,
                self.owner_id,
            )
        ):
            raise ValueError("execution owner requires scope and identity")
        if (
            self.owner_kind is ExecutionOwnerKind.portal_user
            and str(UUID(self.owner_id)) != self.owner_id
        ):
            raise ValueError("Portal owner ID must be a canonical UUID")


@dataclass(frozen=True)
class PaidAllowance:
    owner: ExecutionOwner
    allowance_id: str
    product_id: str
    metric_key: str
    unit: str
    quantity: int

    def __post_init__(self) -> None:
        if self.owner.owner_kind is not ExecutionOwnerKind.portal_user:
            raise ValueError("paid allowance requires a Portal owner")
        if type(self.quantity) is not int or not 0 <= self.quantity <= MAX_ALLOWANCE_QUANTITY:
            raise ValueError("paid allowance quantity must be an integer in 0..2^53-1")
        if not all(
            isinstance(value, str) and value
            for value in (
                self.allowance_id,
                self.product_id,
                self.metric_key,
                self.unit,
            )
        ):
            raise ValueError("paid allowance requires allowance/product/metric/unit identity")


@dataclass(frozen=True)
class PaidAllowanceUsageRecord:
    allowance: PaidAllowance
    id: str = field(default_factory=lambda: new_id("paid_allowance_usage"))
    used_count: int = 0
    reserved_count: int = 0
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class ExecutionReservation:
    owner: ExecutionOwner
    scenario_session_id: str
    job_id: str
    product_id: str
    scenario_id: str
    frontend_id: str
    guest_quota_usage_id: str | None = None
    paid_allowance_usage_id: str | None = None
    replay_namespace: ExecutionReplayNamespace | None = None
    replay_key: str | None = None
    request_hash: str | None = None
    handoff_id: str | None = None
    id: str = field(default_factory=lambda: new_id("execution_reservation"))
    state: ReservationState = ReservationState.reserved
    result_artifact_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    finalized_at: datetime | None = None


@dataclass(frozen=True)
class ExecutionReplayIdentity:
    product_id: str
    scenario_id: str
    namespace: ExecutionReplayNamespace
    replay_key: str


@dataclass(frozen=True)
class ExecutionAcceptance(ScenarioSessionSnapshot):
    """Internal admission result; reservation is absent for legacy/unmetered starts."""

    reservation: ExecutionReservation | None = None
    is_replay: bool = False


@dataclass(frozen=True)
class ExecutionCandidate:
    session: ScenarioSessionRecord
    job: JobRecord
    replay_identity: ExecutionReplayIdentity | None = None
    request_hash: str | None = None
    handoff_id: str | None = None


@dataclass(frozen=True)
class ResolvedQuotaPeriod:
    """One quota window, resolved once from a single UTC instant.

    ends_at is the first instant of the next window (None for lifetime).
    """

    period: QuotaPeriod
    period_key: str
    starts_at: datetime | None
    ends_at: datetime | None


@dataclass(frozen=True)
class QuotaPolicy:
    quota_policy_id: str
    unit: QuotaUnit
    limit_count: int
    period: QuotaPeriod
    dimension: QuotaDimension
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QuotaUsageRecord:
    tenant_id: str
    region: str
    guest_id: str
    product_id: str
    quota_policy_id: str
    quota_dimension: QuotaDimension
    dimension_key: str
    period_key: str
    limit_count: int
    scenario_id: str | None = None
    id: str = field(default_factory=lambda: new_id("guest_quota_usage"))
    used_count: int = 0
    reserved_count: int = 0
    legacy_used_count: int = 0
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QuotaState:
    guest_id: str
    product_id: str
    quota_policy_id: str
    quota_dimension: QuotaDimension
    dimension_key: str
    scenario_id: str | None
    unit: QuotaUnit
    period: QuotaPeriod
    period_key: str
    limit_count: int
    used_count: int
    remaining_count: int
    exhausted: bool
    resets_at: datetime | None


@dataclass(frozen=True)
class FinalExecutionResult:
    job: JobRecord
    artifact: ArtifactRecord


@dataclass(frozen=True)
class ConsumptionTransition:
    applied: bool
    reservation: ExecutionReservation
    became_exhausted: bool = False
