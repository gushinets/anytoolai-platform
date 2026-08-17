"""ANY-219: proves all 11 generic action types compose through real, config-declared
multi-step workflows over the production-shaped API -> session -> job -> worker path.

Sibling of test_atom_runtime_matrix.py (ANY-218's standalone 11/11 proof); this file proves
the same 11 action types compose across three separate multi-step workflows, not merely run
independently, and not as a single artificial 11-step chain.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Iterator

import pytest
import sqlalchemy as sa
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.scenarios.checkpoints import RESULT_READY_CHECKPOINT_ID
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
from anytoolai_platform_worker.composition import build_worker
from test_atom_runtime_matrix import (
    _EXPECTED_ACTION_TYPES,
    _EXPECTED_EVENT_TYPES,
    _fixture_response_json,
)
from test_scenario_runtime_api import CONFIG_ROOT, FIXTURE_ROOT, _create_test_app, _request

from tests.db_support import provision_database

pytestmark = [pytest.mark.postgresql, pytest.mark.slow]

_EXTRACT_FIELDS = [
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
]

_ACTION_EVENT_TYPES = ("action.started", "action.succeeded")


@pytest.fixture
def session_factory() -> Iterator[SessionFactory]:
    with provision_database(
        database_name_prefix="anytoolai_composite_workflow_matrix_test",
        skip_reason="PostgreSQL composite workflow matrix coverage",
    ) as (engine, _alembic_config, _database_url):
        yield build_session_factory(engine)


@dataclass(frozen=True)
class CompositeCase:
    workflow_id: str
    scenario_id: str
    expected_output_schema_ref: str
    start_input: dict[str, Any]
    # (step_id, action_type, action_config_id), in declared workflow order.
    expected_steps: tuple[tuple[str, str, str], ...]


COMPOSITE_MATRIX: tuple[CompositeCase, ...] = (
    CompositeCase(
        workflow_id="kernel_demo.composite_analyze_and_clarify_v1",
        scenario_id="kernel_demo.composite_analyze_and_clarify_smoke_v1",
        expected_output_schema_ref="kernel.schemas.generate_document_output_v1",
        start_input={
            "source_text": "We need this soon.",
            "fields": _EXTRACT_FIELDS,
            "strict": False,
        },
        expected_steps=(
            (
                "extract",
                "text.extract_structured_fields",
                "kernel_demo.extract_structured_fields_v1",
            ),
            (
                "detect_issues",
                "text.detect_issues_by_taxonomy",
                "kernel_demo.detect_issues_v1",
            ),
            (
                "generate_questions",
                "text.generate_clarifying_questions",
                "kernel_demo.generate_clarifying_questions_v1",
            ),
            (
                "generate_report",
                "document.generate_from_template",
                "kernel_demo.generate_report_v1",
            ),
        ),
    ),
    CompositeCase(
        workflow_id="kernel_demo.composite_evaluate_match_v1",
        scenario_id="kernel_demo.composite_evaluate_match_smoke_v1",
        expected_output_schema_ref="kernel.schemas.score_multidim_output_v1",
        start_input={"source_text": "The proposal states its point directly."},
        expected_steps=(
            (
                "compare_and_classify",
                "text.compare_and_classify",
                "kernel_demo.compare_and_classify_v1",
            ),
            (
                "score_match_by_rubric",
                "text.score_match_by_rubric",
                "kernel_demo.score_match_by_rubric_v1",
            ),
            (
                "score_multidimensional_axes",
                "text.score_multidimensional_axes",
                "kernel_demo.score_multidimensional_axes_v1",
            ),
        ),
    ),
    CompositeCase(
        workflow_id="kernel_demo.composite_shape_and_write_v1",
        scenario_id="kernel_demo.composite_shape_and_write_smoke_v1",
        expected_output_schema_ref="kernel.schemas.compose_reply_output_v1",
        start_input={"source_text": "The proposal does not state a delivery date."},
        expected_steps=(
            (
                "synthesize_angle",
                "text.synthesize_angle",
                "kernel_demo.synthesize_angle_v1",
            ),
            (
                "generate_gap_rewrites",
                "text.generate_gap_rewrites",
                "kernel_demo.generate_gap_rewrites_v1",
            ),
            (
                "compose_persuasive_text",
                "text.compose_persuasive_text",
                "kernel_demo.compose_persuasive_text_v1",
            ),
            (
                "compose_reply",
                "text.compose_reply",
                "kernel_demo.compose_reply_v1",
            ),
        ),
    ),
)


def _run_composite_scenario_and_assert_full_path(
    app: Any, session_factory: SessionFactory, case: CompositeCase
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
    # A multi-step job completes in one process_next_job() call: SequentialWorkflowRunner
    # loops over every workflow step internally within a single run_claimed_job() invocation,
    # there is no re-queuing between steps (packages/backend/platform-core/.../workflows/runner.py).
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
            request_id=f"req_composite_matrix_{case.workflow_id}",
        )
    )
    assert session_response.status_code == 200
    session_body = session_response.json()
    assert session_body["status"] == "completed"
    assert session_body["current_checkpoint_id"] == RESULT_READY_CHECKPOINT_ID
    assert session_body["result_artifact_id"] == processed.result_artifact_id

    with transaction_boundary(session_factory) as session:
        action_runs = list(
            session.execute(
                sa.select(action_runs_table)
                .where(action_runs_table.c.job_id == started["job_id"])
                .order_by(action_runs_table.c.created_at, action_runs_table.c.id)
            ).mappings()
        )
        provider_calls = list(
            session.execute(
                sa.select(provider_calls_table).where(
                    provider_calls_table.c.job_id == started["job_id"]
                )
            ).mappings()
        )
        artifacts = list(
            session.execute(
                sa.select(artifacts_table)
                .where(artifacts_table.c.job_id == started["job_id"])
                .order_by(artifacts_table.c.created_at, artifacts_table.c.id)
            ).mappings()
        )
        events = list(
            session.execute(
                sa.select(event_log_table)
                .where(event_log_table.c.scenario_session_id == started["scenario_session_id"])
                .order_by(event_log_table.c.timestamp, event_log_table.c.event_id)
            ).mappings()
        )

    # Step order: the action_runs row sequence for this job matches the workflow's declared
    # step order exactly -- proving real composition, not just eventual completion.
    actual_steps = tuple(
        (run["step_id"], run["action_type"], run["action_config_id"]) for run in action_runs
    )
    assert actual_steps == case.expected_steps

    # Provider-call correlation: exactly one provider_calls row per action_run.
    provider_calls_by_action_run: dict[str, list[dict[str, Any]]] = {}
    for call in provider_calls:
        provider_calls_by_action_run.setdefault(call["action_run_id"], []).append(call)
    for run in action_runs:
        assert len(provider_calls_by_action_run.get(run["id"], [])) == 1
        assert provider_calls_by_action_run[run["id"]][0]["job_id"] == started["job_id"]

    # Artifact lineage: every step has its own output artifact...
    step_output_artifact_ids = {run["id"]: run["output_artifact_id"] for run in action_runs}
    for artifact_id in step_output_artifact_ids.values():
        assert artifact_id is not None
        assert any(artifact["id"] == artifact_id for artifact in artifacts)

    # ...and the job's canonical result artifact is a *separate* row (workflows/runner.py's
    # _create_final_artifact always creates a fresh artifact with action_run_id=None from
    # context.workflow_output -- it never reuses any step's own output_artifact_id), whose
    # content matches the last step's real output payload.
    result_artifact = next(
        artifact for artifact in artifacts if artifact["id"] == processed.result_artifact_id
    )
    assert result_artifact["action_run_id"] is None
    assert processed.result_artifact_id not in step_output_artifact_ids.values()
    last_step_action_config_id = case.expected_steps[-1][2]
    assert result_artifact["content_json"] == _fixture_response_json(last_step_action_config_id)

    # Event coverage + per-step action.started/succeeded ordering. action.* event rows carry
    # action_run_id/action_config_id/timestamp but no step_id of their own, so per-step
    # identity is resolved by joining action_run_id back to the ordered action_runs rows above.
    event_types = {event_row["event_type"] for event_row in events}
    assert _EXPECTED_EVENT_TYPES.issubset(event_types)
    for event_row in events:
        if event_row["job_id"] is not None:
            assert event_row["job_id"] == started["job_id"]

    step_id_by_action_run_id = {run["id"]: run["step_id"] for run in action_runs}
    expected_step_order = [step_id for step_id, _action_type, _config_id in case.expected_steps]
    for event_type in _ACTION_EVENT_TYPES:
        matching_events = [row for row in events if row["event_type"] == event_type]
        step_ids_in_event_order = [
            step_id_by_action_run_id[row["action_run_id"]] for row in matching_events
        ]
        assert step_ids_in_event_order == expected_step_order, (event_type, step_ids_in_event_order)

    result_response = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/results/{processed.result_artifact_id}",
            request_id=f"req_composite_matrix_result_{case.workflow_id}",
        )
    )
    assert result_response.status_code == 200
    result_body = result_response.json()
    assert result_body["schema_ref"] == case.expected_output_schema_ref
    assert result_body["output"] == _fixture_response_json(last_step_action_config_id)


@pytest.mark.parametrize("case", COMPOSITE_MATRIX, ids=lambda c: c.workflow_id)
def test_composite_workflow_matrix(session_factory: SessionFactory, case: CompositeCase) -> None:
    app = _create_test_app(session_factory)
    _run_composite_scenario_and_assert_full_path(app, session_factory, case)


def test_composite_workflow_matrix_reports_three_of_three() -> None:
    assert len(COMPOSITE_MATRIX) == 3

    covered_action_types = {
        action_type
        for case in COMPOSITE_MATRIX
        for _step_id, action_type, _action_config_id in case.expected_steps
    }
    assert covered_action_types == _EXPECTED_ACTION_TYPES
