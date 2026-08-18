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
from typing import Any, Iterator

import pytest
import sqlalchemy as sa
from anytoolai_platform_core.config.loader import ConfigLoader
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
from test_scenario_runtime_api import CONFIG_ROOT, FIXTURE_ROOT, _create_test_app, _request

from tests.db_support import provision_database

pytestmark = [pytest.mark.postgresql, pytest.mark.slow]


@pytest.fixture
def session_factory() -> Iterator[SessionFactory]:
    with provision_database(
        database_name_prefix="anytoolai_atom_runtime_matrix_test",
        skip_reason="PostgreSQL atom runtime matrix coverage",
    ) as (engine, _alembic_config, _database_url):
        yield build_session_factory(engine)

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


ATOM_MATRIX: tuple[AtomCase, ...] = (
    AtomCase(
        action_type="text.extract_structured_fields",
        scenario_id="kernel_demo.single_action_smoke_v1",
        action_config_id="kernel_demo.extract_structured_fields_v1",
        expected_output_schema_ref="kernel_demo.extract_output_v1",
        start_input={
            "source_text": "deadline budget deliverables",
            "fields": [
                {
                    "name": "deadline",
                    "type": "string",
                    "description": "Project deadline mentioned in the text.",
                    "required": True,
                },
                {
                    "name": "budget",
                    "type": "string",
                    "description": "Budget mentioned in the text.",
                    "required": False,
                },
                {
                    "name": "deliverables",
                    "type": "array_of_strings",
                    "description": "Deliverables mentioned in the text.",
                    "required": False,
                },
            ],
            "strict": False,
        },
    ),
    AtomCase(
        action_type="text.detect_issues_by_taxonomy",
        scenario_id="kernel_demo.single_action_detect_issues_smoke_v1",
        action_config_id="kernel_demo.detect_issues_v1",
        expected_output_schema_ref="kernel.schemas.issue_detection_output_v1",
        start_input={"source_text": "We need this soon."},
    ),
    AtomCase(
        action_type="document.generate_from_template",
        scenario_id="kernel_demo.single_action_generate_report_smoke_v1",
        action_config_id="kernel_demo.generate_report_v1",
        expected_output_schema_ref="kernel.schemas.generate_document_output_v1",
        start_input={"source_text": "The project is on track."},
    ),
    AtomCase(
        action_type="text.compose_reply",
        scenario_id="kernel_demo.single_action_compose_reply_smoke_v1",
        action_config_id="kernel_demo.compose_reply_v1",
        expected_output_schema_ref="kernel.schemas.compose_reply_output_v1",
        start_input={"source_text": "Sorry about the delay, can you send an update?"},
    ),
    AtomCase(
        action_type="text.generate_clarifying_questions",
        scenario_id="kernel_demo.single_action_generate_clarifying_questions_smoke_v1",
        action_config_id="kernel_demo.generate_clarifying_questions_v1",
        expected_output_schema_ref="kernel.schemas.generate_questions_output_v1",
        start_input={"source_text": "We need this done soon, no date given."},
    ),
    AtomCase(
        action_type="text.synthesize_angle",
        scenario_id="kernel_demo.single_action_synthesize_angle_smoke_v1",
        action_config_id="kernel_demo.synthesize_angle_v1",
        expected_output_schema_ref="kernel.schemas.synthesize_angle_output_v1",
        start_input={"source_text": "unused by this workflow, kept for input-shape parity"},
    ),
    AtomCase(
        action_type="text.compose_persuasive_text",
        scenario_id="kernel_demo.single_action_compose_persuasive_text_smoke_v1",
        action_config_id="kernel_demo.compose_persuasive_text_v1",
        expected_output_schema_ref="kernel.schemas.compose_persuasive_text_output_v1",
        start_input={"source_text": "unused by this workflow, kept for input-shape parity"},
    ),
    AtomCase(
        action_type="text.generate_gap_rewrites",
        scenario_id="kernel_demo.single_action_generate_gap_rewrites_smoke_v1",
        action_config_id="kernel_demo.generate_gap_rewrites_v1",
        expected_output_schema_ref="kernel.schemas.generate_gap_rewrites_output_v1",
        start_input={"source_text": "The proposal does not state a delivery date."},
    ),
    AtomCase(
        action_type="text.compare_and_classify",
        scenario_id="kernel_demo.single_action_compare_and_classify_smoke_v1",
        action_config_id="kernel_demo.compare_and_classify_v1",
        expected_output_schema_ref="kernel.schemas.compare_classify_output_v1",
        start_input={"source_text": "Subject text for comparison."},
    ),
    AtomCase(
        action_type="text.score_match_by_rubric",
        scenario_id="kernel_demo.single_action_score_match_by_rubric_smoke_v1",
        action_config_id="kernel_demo.score_match_by_rubric_v1",
        expected_output_schema_ref="kernel.schemas.score_match_output_v1",
        start_input={"source_text": "Reference text A for scoring."},
    ),
    AtomCase(
        action_type="text.score_multidimensional_axes",
        scenario_id="kernel_demo.single_action_score_multidimensional_axes_smoke_v1",
        action_config_id="kernel_demo.score_multidimensional_axes_v1",
        expected_output_schema_ref="kernel.schemas.score_multidim_output_v1",
        start_input={"source_text": "The proposal states its point directly."},
    ),
)

_EXPECTED_ACTION_TYPES = {
    "text.extract_structured_fields",
    "text.detect_issues_by_taxonomy",
    "text.compose_reply",
    "text.generate_clarifying_questions",
    "text.synthesize_angle",
    "text.compose_persuasive_text",
    "text.generate_gap_rewrites",
    "text.compare_and_classify",
    "text.score_match_by_rubric",
    "text.score_multidimensional_axes",
    "document.generate_from_template",
}


def _fixture_response_json(action_config_id: str) -> dict[str, Any]:
    fixture_path = FIXTURE_ROOT / f"{action_config_id}.json"
    with fixture_path.open("r", encoding="utf-8") as handle:
        fixture = json.load(handle)
    return fixture["response_json"]


def _run_single_action_scenario_and_assert_full_path(
    app: Any, session_factory: SessionFactory, case: AtomCase
) -> None:
    started = asyncio.run(
        _request(
            app,
            "POST",
            f"/v1/products/kernel_demo/scenarios/{case.scenario_id}/start",
            json={
                "frontend_id": "kernel_demo_ce",
                "guest_id": "guest_demo",
                "input": case.start_input,
            },
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


@pytest.mark.parametrize("case", ATOM_MATRIX, ids=lambda c: c.action_type)
def test_atom_runtime_matrix(session_factory: SessionFactory, case: AtomCase) -> None:
    app = _create_test_app(session_factory)
    _run_single_action_scenario_and_assert_full_path(app, session_factory, case)


def test_atom_runtime_matrix_reports_eleven_of_eleven() -> None:
    covered_action_types = {case.action_type for case in ATOM_MATRIX}
    assert covered_action_types == _EXPECTED_ACTION_TYPES
    assert len(ATOM_MATRIX) == 11
    assert len({case.scenario_id for case in ATOM_MATRIX}) == 11, (
        "ATOM_MATRIX scenario_ids must be unique; a duplicate would silently cover the "
        "same scenario twice instead of a distinct atom"
    )

    registry = ConfigLoader(CONFIG_ROOT).load()
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
