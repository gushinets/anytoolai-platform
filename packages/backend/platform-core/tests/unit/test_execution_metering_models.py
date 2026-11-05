from dataclasses import replace

import pytest
from anytoolai_platform_core.quotas.models import (
    MAX_ALLOWANCE_QUANTITY,
    ExecutionOwner,
    ExecutionOwnerKind,
    ExecutionReplayNamespace,
    PaidAllowance,
    ReservationState,
)
from anytoolai_platform_core.workflows.models import JobConsumptionMode


def paid_allowance() -> PaidAllowance:
    return PaidAllowance(
        owner=ExecutionOwner(
            tenant_id="test",
            region="ru",
            owner_kind=ExecutionOwnerKind.portal_user,
            owner_id="c795407a-b60f-45be-840d-1a80d07ebf6e",
        ),
        allowance_id="cycle-one",
        product_id="kernel_demo",
        metric_key="test_runs",
        unit="scenario_run",
        quantity=1,
    )


@pytest.mark.parametrize("quantity", [True, False, 1.0, "1", -1, MAX_ALLOWANCE_QUANTITY + 1])
def test_paid_quantity_is_a_strict_safe_integer(quantity: object) -> None:
    with pytest.raises(ValueError, match="quantity"):
        replace(paid_allowance(), quantity=quantity)


@pytest.mark.parametrize("quantity", [0, MAX_ALLOWANCE_QUANTITY])
def test_paid_quantity_boundaries(quantity: int) -> None:
    assert replace(paid_allowance(), quantity=quantity).quantity == quantity


@pytest.mark.parametrize("owner_id", ["guest_opaque", "C795407A-B60F-45BE-840D-1A80D07EBF6E"])
def test_portal_owner_requires_canonical_uuid(owner_id: str) -> None:
    with pytest.raises(ValueError):
        replace(paid_allowance().owner, owner_id=owner_id)


def test_guest_opaque_identity_is_preserved_but_cannot_own_paid_allowance() -> None:
    guest = ExecutionOwner("test", "ru", ExecutionOwnerKind.guest, "guest_opaque")
    assert guest.owner_id == "guest_opaque"
    with pytest.raises(ValueError, match="Portal owner"):
        replace(paid_allowance(), owner=guest)


@pytest.mark.parametrize(
    "enum_type",
    [
        ExecutionOwnerKind,
        ExecutionReplayNamespace,
        ReservationState,
        JobConsumptionMode,
    ],
)
def test_unknown_metering_protocol_member_is_rejected(enum_type: type) -> None:
    with pytest.raises(ValueError):
        enum_type("unknown")
