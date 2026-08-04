from __future__ import annotations

from typing import Any

from anytoolai_platform_core.scenarios.correlation import (
    build_scenario_identity_metadata,
    enrich_job_metadata_with_scenario_identity,
)
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord


def _scenario(
    *,
    guest_id: str | None,
    user_id: str | None,
    scenario_chain_id: str | None,
) -> ScenarioSessionRecord:
    return ScenarioSessionRecord(
        tenant_id="tenant_demo",
        region="eu-central",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_id="kernel_demo.single_action_smoke_v1",
        scenario_version=1,
        guest_id=guest_id,
        user_id=user_id,
        scenario_chain_id=scenario_chain_id,
    )


def test_build_scenario_identity_metadata_returns_canonical_identity() -> None:
    scenario = _scenario(
        guest_id="guest_demo",
        user_id=None,
        scenario_chain_id="scenario_chain_demo",
    )

    assert build_scenario_identity_metadata(scenario) == {
        "guest_id": "guest_demo",
        "user_id": None,
        "scenario_chain_id": "scenario_chain_demo",
    }


def test_enrich_job_metadata_with_scenario_identity_preserves_guest_metadata() -> None:
    source: dict[str, Any] = {
        "preexisting": "kept",
        "guest_id": "stale_guest",
        "user_id": "stale_user",
    }
    scenario = _scenario(
        guest_id="guest_demo",
        user_id=None,
        scenario_chain_id="scenario_chain_demo",
    )

    enriched = enrich_job_metadata_with_scenario_identity(source, scenario)

    assert source == {
        "preexisting": "kept",
        "guest_id": "stale_guest",
        "user_id": "stale_user",
    }
    assert enriched == {
        "preexisting": "kept",
        "guest_id": "guest_demo",
        "user_id": None,
        "scenario_chain_id": "scenario_chain_demo",
    }


def test_enrich_job_metadata_with_scenario_identity_preserves_authenticated_metadata() -> None:
    scenario = _scenario(
        guest_id=None,
        user_id="user_demo",
        scenario_chain_id="scenario_chain_demo",
    )

    enriched = enrich_job_metadata_with_scenario_identity(None, scenario)

    assert enriched == {
        "guest_id": None,
        "user_id": "user_demo",
        "scenario_chain_id": "scenario_chain_demo",
    }
