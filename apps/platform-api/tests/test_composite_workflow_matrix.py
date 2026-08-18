"""ANY-219: proves all 11 generic action types compose through real, config-declared
multi-step workflows over the production-shaped API -> session -> job -> worker path.

Sibling of test_atom_runtime_matrix.py (ANY-218's standalone 11/11 proof); this file proves
the same 11 action types compose across three separate multi-step workflows, not merely run
independently, and not as a single artificial 11-step chain.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Iterator

import pytest
import sqlalchemy as sa
from anytoolai_platform_core.config.loader import ConfigLoader
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
    ATOM_MATRIX,
    _EXPECTED_EVENT_TYPES,
    _fixture_response_json,
)
from test_scenario_runtime_api import CONFIG_ROOT, FIXTURE_ROOT, _create_test_app, _request

from tests.db_support import provision_database

# Deliberately NOT a module-level pytestmark: test_composite_workflow_matrix_reports_three_of_three
# below does no DB I/O and must keep running under quick-check's "not slow" pytest subset -- only
# the parametrized DB-backed test needs postgresql/slow (mirrors test_atom_runtime_matrix.py).

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


class _RecordingFakeProviderAdapter(FakeProviderAdapter):
    """Wraps FakeProviderAdapter to keep every resolved provider request it was asked to
    complete, so a test can assert what a step's *actual* rendered prompt contained (proving a
    mapped prior-step output really flowed into this step's request), not just that a
    provider_calls row exists -- provider_calls_table has no request-payload column."""

    def __init__(self, fixture_root: Any) -> None:
        super().__init__(fixture_root)
        self.requests: list[Any] = []

    async def complete(self, request: Any) -> Any:
        self.requests.append(request)
        return await super().complete(request)


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
    # (dependent_step_id, source_step_id, field_path): proves the dependent step's provider
    # request actually carries the source step's mapped output -- field_path is the field
    # consumed from the source step's output (e.g. "rationale"), or None if the whole output
    # object is consumed (e.g. context: steps.generate_gap_rewrites.output).
    expected_step_dependencies: tuple[tuple[str, str, str | None], ...] = field(
        default_factory=tuple
    )


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
        expected_step_dependencies=(
            ("generate_questions", "detect_issues", "issues"),
            ("generate_report", "extract", None),
            ("generate_report", "detect_issues", None),
            ("generate_report", "generate_questions", None),
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
        expected_step_dependencies=(
            ("score_match_by_rubric", "compare_and_classify", "rationale"),
            ("score_multidimensional_axes", "compare_and_classify", "rationale"),
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
        expected_step_dependencies=(
            ("generate_gap_rewrites", "synthesize_angle", "rationale"),
            ("compose_persuasive_text", "generate_gap_rewrites", None),
            ("compose_reply", "compose_persuasive_text", "text"),
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

    recording_adapter = _RecordingFakeProviderAdapter(FIXTURE_ROOT)
    worker = build_worker(
        session_factory=session_factory,
        config_root=CONFIG_ROOT,
        provider_adapters={"fake": recording_adapter},
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

    # scenario_session_id correlation: every action_run/provider_call/artifact row for this job
    # carries this run's scenario_session_id, not just job_id.
    for label, rows in (
        ("action_runs", action_runs),
        ("provider_calls", provider_calls),
        ("artifacts", artifacts),
    ):
        for row in rows:
            assert row["scenario_session_id"] == started["scenario_session_id"], label

    # Provider-call correlation: exactly one provider_calls row per action_run.
    provider_calls_by_action_run: dict[str, list[dict[str, Any]]] = {}
    for call in provider_calls:
        provider_calls_by_action_run.setdefault(call["action_run_id"], []).append(call)
    for run in action_runs:
        assert len(provider_calls_by_action_run.get(run["id"], [])) == 1
        assert provider_calls_by_action_run[run["id"]][0]["job_id"] == started["job_id"]

    # Mapping proof: for every step whose input_mapping consumes a preceding step's output
    # (steps.<id>.output[.field]), assert the *actual* rendered provider request for that step
    # carries the preceding step's real fixture output -- not just that a provider_calls row
    # exists. provider_calls_table has no request-payload column, so this reads from the
    # recording fake adapter; StructuredLlmActionExecutor._render_prompt embeds
    # json.dumps(dict(input_payload), sort_keys=True) verbatim in the rendered prompt.
    action_config_id_by_step_id = {
        step_id: action_config_id for step_id, _action_type, action_config_id in case.expected_steps
    }
    requests_by_step_id = {request.step_id: request for request in recording_adapter.requests}
    for dependent_step_id, source_step_id, field_path in case.expected_step_dependencies:
        source_output = _fixture_response_json(action_config_id_by_step_id[source_step_id])
        expected_value = source_output if field_path is None else source_output[field_path]
        expected_fragment = json.dumps(expected_value, sort_keys=True)
        assert expected_fragment in requests_by_step_id[dependent_step_id].prompt, (
            dependent_step_id,
            source_step_id,
            field_path,
        )

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

    # Flatten action.started/action.succeeded into a single trace ordered by timestamp (events
    # is already ordered that way) and resolve each row to its step via action_run_id. This
    # proves real interleaving -- started(step1), succeeded(step1), started(step2), ... -- not
    # just that each event type's own sub-sequence independently matches step order (which
    # would miss e.g. step2's action.started landing before step1's action.succeeded).
    step_id_by_action_run_id = {run["id"]: run["step_id"] for run in action_runs}
    expected_step_order = [step_id for step_id, _action_type, _config_id in case.expected_steps]
    expected_trace = [
        (step_id, event_type)
        for step_id in expected_step_order
        for event_type in _ACTION_EVENT_TYPES
    ]
    actual_trace = [
        (step_id_by_action_run_id[row["action_run_id"]], row["event_type"])
        for row in events
        if row["event_type"] in _ACTION_EVENT_TYPES
    ]
    assert actual_trace == expected_trace

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


@pytest.mark.postgresql
@pytest.mark.slow
@pytest.mark.parametrize("case", COMPOSITE_MATRIX, ids=lambda c: c.workflow_id)
def test_composite_workflow_matrix(session_factory: SessionFactory, case: CompositeCase) -> None:
    app = _create_test_app(session_factory)
    _run_composite_scenario_and_assert_full_path(app, session_factory, case)


def test_composite_workflow_matrix_reports_three_of_three() -> None:
    """Binds COMPOSITE_MATRIX to the real ConfigLoader registry (scenario -> workflow -> step
    -> action_config_id -> action_type), not just the in-file literal, so a YAML/scenario
    mismatch fails this instead of silently reporting 3/3 -- mirrors
    test_atom_runtime_matrix.py::test_atom_runtime_matrix_reports_eleven_of_eleven. No DB I/O,
    so (like that sibling) this is deliberately not postgresql/slow-marked and keeps running
    under quick-check's "not slow" pytest subset."""
    assert len(COMPOSITE_MATRIX) == 3

    covered_action_types = {
        action_type
        for case in COMPOSITE_MATRIX
        for _step_id, action_type, _action_config_id in case.expected_steps
    }
    assert covered_action_types == {case.action_type for case in ATOM_MATRIX}

    registry = ConfigLoader(CONFIG_ROOT).load()
    for case in COMPOSITE_MATRIX:
        scenario_definition = registry.get_scenario(case.scenario_id)
        assert scenario_definition is not None, f"missing scenario definition for {case.scenario_id}"
        assert scenario_definition.workflow_id == case.workflow_id

        workflow_definition = registry.get_workflow(case.workflow_id)
        assert workflow_definition is not None, f"missing workflow definition for {case.workflow_id}"
        assert workflow_definition.output_schema_ref == case.expected_output_schema_ref

        actual_steps = []
        for step in workflow_definition.steps:
            action_configuration = registry.get_action_configuration(step.action_config_id)
            assert action_configuration is not None, (
                f"missing action configuration for {step.action_config_id}"
            )
            actual_steps.append((step.step_id, action_configuration.action_type, step.action_config_id))
        assert tuple(actual_steps) == case.expected_steps
