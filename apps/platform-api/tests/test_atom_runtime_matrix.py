"""ANY-218: proves all 11 generic action types through the production-shaped
API -> session -> job -> worker -> workflow -> action -> provider -> artifact path.

One config-defined standalone single-action scenario per action type, run over the real
API/worker path (not a direct executor call), with deterministic fake-provider fixtures.
This is the parallel/generalized sibling of
test_scenario_runtime_api.py::test_start_then_real_worker_execution_preserves_a12_runtime_correlation,
not a refactor of it.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import pytest
import sqlalchemy as sa
from anytoolai_platform_core.config.loader import ConfigLoader
from anytoolai_platform_core.identity.models import GuestIdentityRecord
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.scenarios.checkpoints import RESULT_READY_CHECKPOINT_ID
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.db import (
    action_runs_table,
    artifacts_table,
    event_log_table,
    provider_calls_table,
)
from anytoolai_platform_core.storage.transactions import (
    SessionFactory,
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.workflows.models import JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from anytoolai_platform_worker.composition import build_worker
from test_scenario_runtime_api import (
    CONFIG_ROOT,
    FIXTURE_ROOT,
    _create_test_app,
    _request,
    _start_payload,
)

from tests.db_support import provision_database
from tests.test_kernel_demo_smoke import load_smoke_module

# Deliberately NOT a module-level pytestmark: test_atom_runtime_matrix_reports_eleven_of_eleven
# and test_atom_smoke_cases_match_atom_matrix below do no DB I/O and must keep running under
# quick-check's "not slow" pytest subset -- only the parametrized DB-backed test needs
# postgresql/slow.


@pytest.fixture(scope="module")
def session_factory() -> Iterator[SessionFactory]:
    # Module-scoped: one provision_database() (CREATE DATABASE + alembic upgrade) for the
    # whole 11-case parametrize sweep, not once per case. Safe to share because every case
    # uses its own guest_id (see _run_single_action_scenario_and_assert_full_path) and is
    # scoped by its own scenario_session_id/job_id in every assertion.
    with provision_database(
        database_name_prefix="anytoolai_atom_runtime_matrix_test",
        skip_reason="PostgreSQL atom runtime matrix coverage",
    ) as (engine, _alembic_config, _database_url):
        yield build_session_factory(engine)


@pytest.fixture(scope="module")
def app(session_factory: SessionFactory) -> Any:
    # Module-scoped to match session_factory: _create_test_app() seeds a "guest_demo" identity
    # row unconditionally, so calling it once per parametrized case against the same shared DB
    # would collide on a duplicate key from the second case onward.
    return _create_test_app(session_factory)

# ponytail: duplicates a literal inlined in test_scenario_runtime_api.py's
# test_start_then_real_worker_execution_preserves_a12_runtime_correlation (no shared module
# constant exists there to import instead). Not extracted to a shared helper: this file's own
# docstring documents that it deliberately doesn't refactor that test/file. Extract to a
# shared constant if a third consumer needs this event-type set.
_EXPECTED_EVENT_TYPES = {
    "scenario.started",
    "workflow.started",
    "action.started",
    "provider.request_started",
    "provider.request_succeeded",
    "artifact.created",
    "action.succeeded",
    "workflow.succeeded",
    "scenario.checkpoint_reached",
    "scenario.completed",
}


@dataclass(frozen=True)
class AtomCase:
    action_type: str
    scenario_id: str
    action_config_id: str
    expected_output_schema_ref: str
    start_input: dict[str, Any]


# Loaded from the same JSON file scripts/agent/kernel_demo_smoke.py's ATOM_SMOKE_CASES reads --
# one shared source of the 11 (action_type, scenario_id, ...) cases instead of two independently
# hand-maintained literals, so the two consumers structurally can't drift apart.
_ATOM_MATRIX_DATA_PATH = (
    Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "kernel_demo" / "atom_smoke_matrix.json"
)


def _load_atom_matrix() -> tuple[AtomCase, ...]:
    with _ATOM_MATRIX_DATA_PATH.open("r", encoding="utf-8") as handle:
        raw_cases = json.load(handle)
    return tuple(AtomCase(**raw_case) for raw_case in raw_cases)


ATOM_MATRIX: tuple[AtomCase, ...] = _load_atom_matrix()

def _fixture_response_json(action_config_id: str) -> dict[str, Any]:
    fixture_path = FIXTURE_ROOT / f"{action_config_id}.json"
    with fixture_path.open("r", encoding="utf-8") as handle:
        fixture = json.load(handle)
    return fixture["response_json"]


def _run_single_action_scenario_and_assert_full_path(
    app: Any, session_factory: SessionFactory, case: AtomCase
) -> None:
    # A distinct, DB-registered guest per case: session_factory is module-scoped (one DB for
    # all 11 cases), and kernel_demo's guest quota is a shared per-guest lifetime budget
    # smaller than 11, so reusing one guest_id here would exhaust it partway through.
    guest_id = f"guest_atom_matrix_{case.action_type}"
    with transaction_boundary(session_factory) as session:
        GuestIdentityRepository(session).create(
            GuestIdentityRecord(id=guest_id, tenant_id="anytoolai", region="default")
        )

    started = asyncio.run(
        _request(
            app,
            "POST",
            f"/v1/products/kernel_demo/scenarios/{case.scenario_id}/start",
            json=_start_payload(guest_id=guest_id, input=case.start_input),
        )
    ).json()

    worker = build_worker(
        session_factory=session_factory,
        config_root=CONFIG_ROOT,
        provider_adapters={"fake": FakeProviderAdapter(FIXTURE_ROOT)},
    )
    processed = asyncio.run(worker.process_next_job())
    worker.dispose()
    assert processed is not None
    assert processed.id == started["job_id"]
    assert processed.status is JobStatus.succeeded, (
        processed.error_code,
        processed.error_message_safe,
    )
    assert processed.result_artifact_id is not None

    session_response = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/scenario-sessions/{started['scenario_session_id']}",
            request_id=f"req_atom_matrix_{case.action_type}",
        )
    )
    assert session_response.status_code == 200
    session_body = session_response.json()
    assert session_body["status"] == "completed"
    assert session_body["current_checkpoint_id"] == RESULT_READY_CHECKPOINT_ID
    assert session_body["result_artifact_id"] == processed.result_artifact_id

    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).get_in_scope(
            started["scenario_session_id"],
            tenant_id="anytoolai",
            region="default",
        )
        job = JobRepository(session).get(started["job_id"])
        action_run = session.execute(
            sa.select(action_runs_table).where(action_runs_table.c.job_id == started["job_id"])
        ).mappings().one()
        provider_call = session.execute(
            sa.select(provider_calls_table).where(
                provider_calls_table.c.job_id == started["job_id"]
            )
        ).mappings().one()
        artifacts = list(
            session.execute(
                sa.select(artifacts_table).where(artifacts_table.c.job_id == started["job_id"])
            ).mappings()
        )
        events = list(
            session.execute(
                sa.select(event_log_table).where(
                    event_log_table.c.scenario_session_id == started["scenario_session_id"]
                )
            ).mappings()
        )

    assert scenario is not None
    assert scenario.status.value == "completed"
    assert job is not None
    assert job.scenario_session_id == started["scenario_session_id"]
    assert job.result_artifact_id == processed.result_artifact_id

    assert action_run["scenario_session_id"] == started["scenario_session_id"]
    assert action_run["action_type"] == case.action_type
    assert action_run["action_config_id"] == case.action_config_id
    assert provider_call["scenario_session_id"] == started["scenario_session_id"]
    assert provider_call["job_id"] == started["job_id"]
    assert provider_call["action_run_id"] == action_run["id"]
    assert any(artifact["id"] == processed.result_artifact_id for artifact in artifacts)
    result_artifact = next(
        artifact for artifact in artifacts if artifact["id"] == processed.result_artifact_id
    )
    assert result_artifact["job_id"] == started["job_id"]
    assert result_artifact["scenario_session_id"] == started["scenario_session_id"]

    event_types = {event_row["event_type"] for event_row in events}
    assert _EXPECTED_EVENT_TYPES.issubset(event_types)
    for event_row in events:
        if event_row["job_id"] is not None:
            assert event_row["job_id"] == started["job_id"]

    result_response = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/results/{processed.result_artifact_id}",
            request_id=f"req_atom_matrix_result_{case.action_type}",
        )
    )
    assert result_response.status_code == 200
    result_body = result_response.json()
    assert result_body["schema_ref"] == case.expected_output_schema_ref
    assert result_body["output"] == _fixture_response_json(case.action_config_id)


@pytest.mark.postgresql
@pytest.mark.slow
@pytest.mark.parametrize("case", ATOM_MATRIX, ids=lambda c: c.action_type)
def test_atom_runtime_matrix(app: Any, session_factory: SessionFactory, case: AtomCase) -> None:
    _run_single_action_scenario_and_assert_full_path(app, session_factory, case)


def test_atom_runtime_matrix_reports_eleven_of_eleven() -> None:
    """One of two remaining independent atom-coverage guards (the third, cross-checking
    ATOM_MATRIX against ATOM_SMOKE_CASES, was retired once both loaded from one shared JSON
    file -- see test_atom_smoke_cases_match_atom_matrix). This one checks ATOM_MATRIX against
    the validated ConfigLoader registry (scenario -> workflow -> step -> action_config_id ->
    action_type); kernel_demo_smoke.py's own _atom_coverage_error (SMOKE007) separately checks
    ATOM_SMOKE_CASES against a raw config-directory glob for its own live-HTTP run. Keep both
    in sync when changing what "11/11 covered" means.
    """
    registry = ConfigLoader(CONFIG_ROOT).load()
    # Derived from configs/kernel/action_definitions/*.yaml, the source of truth for "generic
    # action type", instead of a hardcoded 11-item set that a newly added atom wouldn't move.
    expected_action_types = set(registry.action_definitions.keys())

    covered_action_types = {case.action_type for case in ATOM_MATRIX}
    assert covered_action_types == expected_action_types
    assert len(ATOM_MATRIX) == len(expected_action_types)
    assert len({case.scenario_id for case in ATOM_MATRIX}) == len(ATOM_MATRIX), (
        "ATOM_MATRIX scenario_ids must be unique; a duplicate would silently cover the "
        "same scenario twice instead of a distinct atom"
    )

    for case in ATOM_MATRIX:
        # Binds the mapping end-to-end: scenario_id -> workflow's single step ->
        # action_config_id -> action_type, so a swapped action_type label on an otherwise
        # matching case is caught here instead of silently reporting 11/11.
        scenario_definition = registry.get_scenario(case.scenario_id)
        assert scenario_definition is not None, f"missing scenario definition for {case.scenario_id}"
        workflow_definition = registry.get_workflow(scenario_definition.workflow_id)
        assert workflow_definition is not None, (
            f"missing workflow definition for {scenario_definition.workflow_id}"
        )
        assert len(workflow_definition.steps) == 1, (
            f"{scenario_definition.workflow_id} must be a single-action workflow for the "
            "standalone atom matrix"
        )
        assert workflow_definition.steps[0].action_config_id == case.action_config_id

        # result_body["schema_ref"] reflects the *workflow's* output_schema_ref, which for
        # the pre-existing extract workflow is a permissive pass-through wrapper -- the real
        # non-permissive contract enforced on every provider response is the *action's*
        # output schema (prompts.yaml's output_schema_ref), so that is what the placeholder
        # guard below checks.
        result_schema_definition = registry.get_schema(case.expected_output_schema_ref)
        assert result_schema_definition is not None, (
            f"missing schema definition for {case.expected_output_schema_ref}"
        )

        action_configuration = registry.get_action_configuration(case.action_config_id)
        assert action_configuration is not None, (
            f"missing action configuration for {case.action_config_id}"
        )
        assert action_configuration.action_type == case.action_type
        prompt_definition = registry.get_prompt(action_configuration.prompt_ref)
        assert prompt_definition is not None, (
            f"missing prompt definition for {action_configuration.prompt_ref}"
        )
        action_schema_ref = prompt_definition.output_schema_ref
        assert action_schema_ref is not None, (
            f"{case.action_config_id} has no output_schema_ref; a placeholder atom cannot "
            "count toward 11/11"
        )
        action_schema_definition = registry.get_schema(action_schema_ref)
        assert action_schema_definition is not None, (
            f"missing schema definition for {action_schema_ref}"
        )
        action_schema = action_schema_definition.schema
        assert action_schema.get("additionalProperties") is not True, (
            f"{action_schema_ref} is permissive; a permissive or placeholder atom cannot "
            "count toward 11/11"
        )
        assert action_schema.get("properties"), (
            f"{action_schema_ref} has no declared properties; a placeholder atom cannot "
            "count toward 11/11"
        )


def test_atom_smoke_cases_match_atom_matrix() -> None:
    """ATOM_MATRIX (this file) and ATOM_SMOKE_CASES (kernel_demo_smoke.py) both load from the
    same tests/fixtures/kernel_demo/atom_smoke_matrix.json, so their case data structurally
    can't drift -- this is a regression check on the two loaders' field-selection logic (e.g.
    a typo'd JSON key silently dropping a field), not a lock between two hand-maintained
    lists."""
    smoke = load_smoke_module()

    smoke_cases = {
        action_type: (scenario_id, start_input)
        for action_type, scenario_id, start_input in smoke.ATOM_SMOKE_CASES
    }
    matrix_cases = {case.action_type: (case.scenario_id, case.start_input) for case in ATOM_MATRIX}
    assert smoke_cases == matrix_cases
