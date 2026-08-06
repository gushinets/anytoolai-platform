from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class ScenarioIdentitySource(Protocol):
    """Structural shape shared by `ScenarioSessionRecord` and `ExecutionContext`.

    A `Protocol` (rather than importing either concrete type) lets both callers --
    `run_workflow.py`, which has a `ScenarioSessionRecord`, and `runner.py`, which has
    an `ExecutionContext` -- pass their own object straight through without a
    conversion step or a dependency between `scenarios` and `context`.
    """

    @property
    def guest_id(self) -> str | None: ...

    @property
    def user_id(self) -> str | None: ...

    @property
    def scenario_chain_id(self) -> str | None: ...


def build_scenario_identity_metadata(
    source: ScenarioIdentitySource,
) -> dict[str, Any]:
    return {
        "guest_id": source.guest_id,
        "user_id": source.user_id,
        "scenario_chain_id": source.scenario_chain_id,
    }


def enrich_job_metadata_with_scenario_identity(
    metadata: Mapping[str, Any] | None,
    source: ScenarioIdentitySource,
) -> dict[str, Any]:
    return {
        **({} if metadata is None else dict(metadata)),
        **build_scenario_identity_metadata(source),
    }
