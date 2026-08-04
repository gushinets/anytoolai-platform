from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord


def build_scenario_identity_metadata(
    session: ScenarioSessionRecord,
) -> dict[str, Any]:
    return {
        "guest_id": session.guest_id,
        "user_id": session.user_id,
        "scenario_chain_id": session.scenario_chain_id,
    }


def enrich_job_metadata_with_scenario_identity(
    metadata: Mapping[str, Any] | None,
    session: ScenarioSessionRecord,
) -> dict[str, Any]:
    return {
        **({} if metadata is None else dict(metadata)),
        **build_scenario_identity_metadata(session),
    }
