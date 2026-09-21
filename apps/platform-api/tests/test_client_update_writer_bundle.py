"""ANY-413 quick-check-covered evidence for the client_update_writer product bundle.

Three kinds of proof, all DB-free except the last (which uses the SQLite runtime harness, not
Postgres, so it stays inside quick-check's "not slow" pytest subset -- see
apps/platform-api/tests/test_demo_api.py for the same SQLite pattern):

1. The product loads through anytoolai_platform_api.bootstrap.build_runtime()'s real default
   bundle set (FreelancerSuiteBundle -- no test-only fixture bundle involved), proving the
   composition boundary actually wires client_update_writer in, mirrors
   apps/platform-api/tests/test_bundle_composition.py's approach for the ANY-32 loader itself.
2. Each mode's product-owned input schema rejects malformed input (missing required field,
   invalid tone enum), and the shared compose_reply output schema rejects a malformed output --
   proving schemas are non-permissive, not just present.
3. An end-to-end scenario-start + worker step-run happy path for *all three* modes using the fake
   provider, asserting the produced artifact matches the deterministic fixture -- PrepaidRequest's
   two-step compose_persuasive_text -> compose_reply chain runs for real here too, not just at the
   config/schema level, so a wiring regression in that composition (wrong step order, a broken
   mapping, a dropped step) actually fails a test instead of only showing up at runtime.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx
import jsonschema
import pytest
import sqlalchemy as sa
from anytoolai_platform_api.bootstrap import RuntimeStorageDependencies, build_runtime
from anytoolai_platform_api.main import create_app
from anytoolai_platform_core.identity.models import GuestIdentityRecord
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.providers.models import ProviderResponse, ResolvedProviderRequest
from anytoolai_platform_core.scenarios.checkpoints import RESULT_READY_CHECKPOINT_ID
from anytoolai_platform_core.storage.db import (
    action_runs_table,
    artifacts_table,
    event_log_table,
    provider_calls_table,
)
from anytoolai_platform_core.storage.transactions import SessionFactory, transaction_boundary
from anytoolai_platform_core.structured_output.schemas import normalize_schema_mapping
from anytoolai_platform_core.workflows.models import JobStatus
from anytoolai_platform_worker.composition import build_worker
from test_atom_runtime_matrix import _EXPECTED_EVENT_TYPES

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "provider" / "fake_provider_outputs"
GUEST_ID = "guest_client_update_writer"
REQUEST_ID = "req_client_update_writer_test"

# action.started/action.succeeded, the two event types whose ordering (per action_run_id) proves
# real step-by-step interleaving rather than just "two rows of each type exist somewhere" --
# mirrors test_composite_workflow_matrix.py's own constant of the same name/shape.
_ACTION_EVENT_TYPES = ("action.started", "action.succeeded")


_MODE_WORKFLOWS = {
    "update": (
        "client_update_writer.update_v1",
        "client_update_writer.update_input_v1",
        ("text.compose_reply",),
    ),
    "prepaid_request": (
        "client_update_writer.prepaid_request_v1",
        "client_update_writer.prepaid_request_input_v1",
        ("text.compose_persuasive_text", "text.compose_reply"),
    ),
    "reply_draft": (
        "client_update_writer.reply_draft_v1",
        "client_update_writer.reply_draft_input_v1",
        ("text.compose_reply",),
    ),
}

# Full (step_id, action_type, action_config_id) triples per mode, in declared workflow order --
# code review finding: the existing per-mode evidence only correlated job_id -> processed job and
# scenario_session_id -> result artifact; it never proved that action_run/provider_call/artifact/
# event rows for a run are correctly linked to each other and to the run's own identifiers,
# especially PrepaidRequest's two-step chain (each step needs its own correctly-linked
# action_run + provider_call, not just "two of something exist").
_MODE_EXPECTED_STEPS = {
    "update": (("compose_reply", "text.compose_reply", "client_update_writer.update_compose_reply_v1"),),
    "reply_draft": (
        ("compose_reply", "text.compose_reply", "client_update_writer.reply_draft_compose_reply_v1"),
    ),
    "prepaid_request": (
        (
            "compose_persuasive_text",
            "text.compose_persuasive_text",
            "client_update_writer.prepaid_request_compose_persuasive_text_v1",
        ),
        ("compose_reply", "text.compose_reply", "client_update_writer.prepaid_request_compose_reply_v1"),
    ),
}


def test_client_update_writer_loads_through_the_real_default_bundle_set() -> None:
    result = build_runtime(config_root=CONFIG_ROOT)

    assert "freelancer_suite" in result.loaded_bundles
    assert "client_update_writer" in result.config_registry.products

    product = result.config_registry.products["client_update_writer"]
    assert set(product.scenarios) == {
        "client_update_writer.update_v1",
        "client_update_writer.prepaid_request_v1",
        "client_update_writer.reply_draft_v1",
    }

    for mode, (workflow_id, input_schema_ref, expected_action_types) in _MODE_WORKFLOWS.items():
        scenario = result.config_registry.get_scenario(workflow_id)
        assert scenario is not None, mode
        assert scenario.workflow_id == workflow_id

        workflow = result.config_registry.get_workflow(workflow_id)
        assert workflow is not None, mode
        assert workflow.input_schema_ref == input_schema_ref
        assert workflow.output_schema_ref == "kernel.schemas.compose_reply_output_v1"

        # Exact per-step action_type sequence, not membership -- a step wired to the wrong atom
        # (e.g. two compose_reply steps instead of persuasive-text-then-reply) must fail here.
        actual_action_types = tuple(
            result.config_registry.get_action_configuration(step.action_config_id).action_type
            for step in workflow.steps
        )
        assert actual_action_types == expected_action_types, mode


@pytest.mark.parametrize(
    ("schema_ref", "valid_input", "invalid_input"),
    [
        (
            "client_update_writer.update_input_v1",
            {"progress_notes": "Homepage is done.", "tone": "warm"},
            {"tone": "warm"},  # missing required progress_notes
        ),
        (
            "client_update_writer.update_input_v1",
            {"progress_notes": "Homepage is done.", "tone": "warm"},
            {"progress_notes": "Homepage is done.", "tone": "furious"},  # invalid enum
        ),
        (
            "client_update_writer.reply_draft_input_v1",
            {
                "client_message": "When will this ship?",
                "reply_goal": "Give a concrete date.",
                "tone": "neutral",
            },
            {"client_message": "When will this ship?", "tone": "neutral"},  # missing reply_goal
        ),
        (
            "client_update_writer.prepaid_request_input_v1",
            {
                "billing_context": {"notes": "Phase 2 kickoff.", "amount": "$500"},
                "tone": "firm",
            },
            {"tone": "firm"},  # missing required billing_context
        ),
        (
            "client_update_writer.prepaid_request_input_v1",
            {
                "billing_context": {"notes": "Phase 2 kickoff.", "amount": "$500"},
                "tone": "firm",
            },
            {
                "billing_context": {"notes": "Phase 2 kickoff."},  # missing required amount
                "tone": "firm",
            },
        ),
    ],
    ids=[
        "update_missing_progress_notes",
        "update_invalid_tone_enum",
        "reply_draft_missing_reply_goal",
        "prepaid_request_missing_billing_context",
        "prepaid_request_billing_context_missing_amount",
    ],
)
def test_mode_input_schemas_are_non_permissive(
    schema_ref: str,
    valid_input: dict[str, Any],
    invalid_input: dict[str, Any],
) -> None:
    registry = build_runtime(config_root=CONFIG_ROOT).config_registry
    schema_definition = registry.get_schema(schema_ref)
    assert schema_definition is not None, schema_ref

    schema = normalize_schema_mapping(schema_definition.schema)
    jsonschema.validate(valid_input, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_input, schema)


def test_compose_reply_output_schema_rejects_malformed_output() -> None:
    registry = build_runtime(config_root=CONFIG_ROOT).config_registry
    schema_definition = registry.get_schema("kernel.schemas.compose_reply_output_v1")
    assert schema_definition is not None
    schema = normalize_schema_mapping(schema_definition.schema)

    jsonschema.validate({"text": "Thanks for the update."}, schema)
    with pytest.raises(jsonschema.ValidationError):
        # Missing the required `text` field.
        jsonschema.validate({"call_to_action": "Reply by Friday."}, schema)
    with pytest.raises(jsonschema.ValidationError):
        # Unknown field -- additionalProperties: false.
        jsonschema.validate(
            {"text": "Thanks for the update.", "unexpected_field": "nope"},
            schema,
        )


# `session_factory`/`platform_api_app_factory`/`request_platform_api` (SQLite-backed) come from
# apps/platform-api/tests/conftest.py, shared with test_demo_api.py and test_proposal_ai_bundle.py
# (ANY-414 code review finding: this file's own `app` fixture and `_request()` helper were a
# verbatim duplicate of test_proposal_ai_bundle.py's).


@pytest.fixture
def app(session_factory: SessionFactory):
    with transaction_boundary(session_factory) as session:
        GuestIdentityRepository(session).create(
            GuestIdentityRecord(
                id="guest_client_update_writer",
                tenant_id="anytoolai",
                region="default",
            )
        )
    application = create_app(config_root=CONFIG_ROOT)
    application.state.runtime = replace(
        application.state.runtime,
        storage=RuntimeStorageDependencies(session_factory=session_factory),
    )
    return application


async def _request(
    app: Any,
    method: str,
    path: str,
    *,
    json: Any | None = None,
    request_id: str = "req_client_update_writer_test",
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(
            method,
            path,
            json=json,
            headers={"X-Request-ID": request_id},
        )


_MODE_HAPPY_PATH_CASES = {
    "update": (
        {
            "progress_notes": (
                "Homepage redesign is done and ready for review by Friday. Checkout flow work "
                "is in progress, no blockers so far."
            ),
            "tone": "warm",
        },
        {
            "text": (
                "Quick update: the homepage redesign is done and ready for review by Friday. "
                "Checkout flow work is in progress, no blockers so far."
            ),
            "call_to_action": "Let me know if you'd like any changes to the homepage.",
        },
    ),
    "reply_draft": (
        {
            "client_message": "When will this ship?",
            "reply_goal": (
                "State that the revised delivery date is next Wednesday, which covers both the "
                "copy edits and the final review pass."
            ),
            "tone": "neutral",
        },
        {
            "text": (
                "Thanks for the question about the timeline. The revised delivery date is next "
                "Wednesday, which covers both the copy edits and the final review pass."
            ),
        },
    ),
    "prepaid_request": (
        {
            "billing_context": {
                "notes": "The approved design phase wraps up this week; phase 2 (development) starts next.",
                "amount": "$500",
                "due_date": "Friday",
            },
            "tone": "firm",
            "constraints": {"language": "en", "max_length": 500, "output_format": "plain_text"},
        },
        {
            "text": (
                "Now that the approved design phase is wrapping up this week and phase 2 "
                "(development) is starting next, could you send the $500 prepayment for phase 2 "
                "by Friday?"
            ),
            "call_to_action": "Let me know once it's on its way.",
        },
    ),
}


@pytest.mark.parametrize(
    ("mode", "start_input", "expected_output"),
    [(mode, *case) for mode, case in _MODE_HAPPY_PATH_CASES.items()],
    ids=_MODE_HAPPY_PATH_CASES.keys(),
)
def test_mode_happy_path_produces_the_deterministic_fixture_result(
    app: Any,
    request_platform_api,
    session_factory: SessionFactory,
    mode: str,
    start_input: dict[str, Any],
    expected_output: dict[str, Any],
) -> None:
    # scenario_id and workflow_id are the same string by this product's own design (one
    # scenario per mode, 1:1 with its workflow) -- reusing _MODE_WORKFLOWS here instead of a
    # second literal keeps that id defined in exactly one place.
    scenario_id = _MODE_WORKFLOWS[mode][0]
    started = asyncio.run(
        _request(
            app,
            "POST",
            f"/v1/products/client_update_writer/scenarios/{scenario_id}/start",
            json={
                "frontend_id": "web_mirror",
                "guest_id": GUEST_ID,
                "input": start_input,
            },
            request_id=REQUEST_ID,
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
            request_id=REQUEST_ID,
        )
    )
    assert session_response.status_code == HTTPStatus.OK
    session_body = session_response.json()
    assert session_body["status"] == "completed"
    assert session_body["current_checkpoint_id"] == RESULT_READY_CHECKPOINT_ID
    assert session_body["allowed_next_actions"] == ["copy_result"]
    assert session_body["result_artifact_id"] == processed.result_artifact_id

    result_response = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/results/{processed.result_artifact_id}",
            request_id=REQUEST_ID,
        )
    )
    assert result_response.status_code == HTTPStatus.OK
    result_body = result_response.json()
    assert result_body["schema_ref"] == "kernel.schemas.compose_reply_output_v1"
    assert result_body["output"] == expected_output

    # Code review finding: prove session/job/action/provider/artifact/event correlation across the
    # real pipeline, not just that the final output matches -- especially PrepaidRequest's two-step
    # chain, where each step needs its own correctly-linked action_run/provider_call row.
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
                sa.select(provider_calls_table).where(provider_calls_table.c.job_id == started["job_id"])
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

    # Step order: the action_runs row sequence matches the workflow's declared step order exactly
    # -- for PrepaidRequest, this is what actually distinguishes "both steps really ran, in order"
    # from "the job merely succeeded".
    actual_steps = tuple((run["step_id"], run["action_type"], run["action_config_id"]) for run in action_runs)
    assert actual_steps == _MODE_EXPECTED_STEPS[mode]

    # scenario_session_id correlation: every action_run/provider_call/artifact row for this job
    # carries this run's scenario_session_id, not just job_id.
    for label, rows in (("action_runs", action_runs), ("provider_calls", provider_calls), ("artifacts", artifacts)):
        for row in rows:
            assert row["scenario_session_id"] == started["scenario_session_id"], label

    # Provider-call correlation: exactly one provider_calls row per action_run -- proves
    # PrepaidRequest's two steps each made their own provider call, not one call shared/skipped.
    provider_calls_by_action_run: dict[str, list[dict[str, Any]]] = {}
    for call in provider_calls:
        provider_calls_by_action_run.setdefault(call["action_run_id"], []).append(call)
    for run in action_runs:
        assert len(provider_calls_by_action_run.get(run["id"], [])) == 1
        assert provider_calls_by_action_run[run["id"]][0]["job_id"] == started["job_id"]

    # Artifact lineage: every step has its own output artifact, and the job's canonical result
    # artifact is a separate row (action_run_id is None), never reusing a step's own artifact id.
    step_output_artifact_ids = {run["id"]: run["output_artifact_id"] for run in action_runs}
    for artifact_id in step_output_artifact_ids.values():
        assert artifact_id is not None
        assert any(artifact["id"] == artifact_id for artifact in artifacts)
    result_artifact = next(artifact for artifact in artifacts if artifact["id"] == processed.result_artifact_id)
    assert result_artifact["action_run_id"] is None
    assert processed.result_artifact_id not in step_output_artifact_ids.values()

    # Event coverage, plus per-step action.started/action.succeeded ordering: flattens those two
    # event types into one trace ordered by timestamp and resolves each row to its step via
    # action_run_id, proving real interleaving (started(step1), succeeded(step1), started(step2),
    # ...) rather than each event type's own sub-sequence independently matching step order.
    event_types = {event_row["event_type"] for event_row in events}
    assert _EXPECTED_EVENT_TYPES.issubset(event_types)
    for event_row in events:
        if event_row["job_id"] is not None:
            assert event_row["job_id"] == started["job_id"]

    step_id_by_action_run_id = {run["id"]: run["step_id"] for run in action_runs}
    expected_step_order = [step_id for step_id, _action_type, _config_id in _MODE_EXPECTED_STEPS[mode]]
    expected_trace = [
        (step_id, event_type) for step_id in expected_step_order for event_type in _ACTION_EVENT_TYPES
    ]
    actual_trace = [
        (step_id_by_action_run_id[row["action_run_id"]], row["event_type"])
        for row in events
        if row["event_type"] in _ACTION_EVENT_TYPES
    ]
    assert actual_trace == expected_trace

    # Code review finding (xhigh #5): amount/due_date only reach the client through the
    # persuasive-text step's free-text `situation` (A07's compose_reply schema has no dedicated
    # field for them, and the mapping DSL has no string interpolation), so nothing structurally
    # guarantees they survive a future prompt/fixture edit -- several earlier rounds each caught
    # one way they'd been dropped or altered. Assert directly against this test's own
    # `start_input`, independent of `expected_output`'s hardcoded string, so a future edit that
    # updates the fixture and `expected_output` together but drops a fact still fails here.
    if mode == "prepaid_request":
        billing_context = start_input["billing_context"]
        assert billing_context["amount"] in result_body["output"]["text"]
        assert billing_context["due_date"] in result_body["output"]["text"]

    # Code review finding (me #13): the happy path stopped at asserting `copy_result` is
    # *allowed* -- it never actually called the next-action endpoint or checked that the
    # activation event this product's own contract promises actually gets recorded.
    next_action_response = asyncio.run(
        _request(
            app,
            "POST",
            f"/v1/scenario-sessions/{started['scenario_session_id']}/next-actions/copy_result",
            json={"checkpoint_id": RESULT_READY_CHECKPOINT_ID},
        )
    )
    assert next_action_response.status_code == HTTPStatus.OK

    with transaction_boundary(session_factory) as session:
        event_row = session.execute(
            sa.select(event_log_table).where(
                event_log_table.c.event_type == "client.next_action_clicked"
            )
        ).mappings().one()

    assert event_row["scenario_session_id"] == started["scenario_session_id"]
    assert event_row["job_id"] == started["job_id"]
    assert event_row["properties"] == {
        "checkpoint_id": RESULT_READY_CHECKPOINT_ID,
        "next_action_id": "copy_result",
    }


class _WeakInputProviderAdapter(FakeProviderAdapter):
    """Forces every provider call in a worker run to resolve `<action_config_id>.weak_input`
    instead of the happy-path `<action_config_id>` fixture. FakeProviderAdapter only ever falls
    back to a call's own action_config_id, so nothing else proves a checked-in `.weak_input.json`
    fixture is actually reachable through the real pipeline (it could be schema-valid but
    unreachable, or simply wrong, while every other test still passed). Test-only -- no
    product/platform runtime change; generalizes apps/platform-api/tests/test_proposal_ai_bundle.py's
    single-fixed-key `_FixedFixtureProviderAdapter` to a multi-step workflow, where each step needs
    its own weak fixture rather than one shared key."""

    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse:
        return await super().complete(
            replace(request, fixture_key=f"{request.action_config_id}.weak_input")
        )


_MODE_WEAK_INPUT_CASES = {
    "update": (
        {"progress_notes": "Still working on it.", "tone": "neutral"},
        "client_update_writer.update_compose_reply_v1",
    ),
    "reply_draft": (
        {
            "client_message": "Any update?",
            "reply_goal": "Acknowledge and say more soon.",
            "tone": "neutral",
        },
        "client_update_writer.reply_draft_compose_reply_v1",
    ),
    "prepaid_request": (
        {
            "billing_context": {"notes": "Work is ongoing.", "amount": "the agreed amount"},
            "tone": "neutral",
        },
        "client_update_writer.prepaid_request_compose_reply_v1",
    ),
}


@pytest.mark.parametrize(
    ("mode", "start_input", "final_action_config_id"),
    [(mode, *case) for mode, case in _MODE_WEAK_INPUT_CASES.items()],
    ids=_MODE_WEAK_INPUT_CASES.keys(),
)
def test_weak_input_fixture_is_reachable_end_to_end(
    app: Any,
    request_platform_api,
    session_factory: SessionFactory,
    mode: str,
    start_input: dict[str, Any],
    final_action_config_id: str,
) -> None:
    scenario_id = _MODE_WORKFLOWS[mode][0]
    expected_output = json.loads(
        (FIXTURE_ROOT / f"{final_action_config_id}.weak_input.json").read_text(encoding="utf-8")
    )["response_json"]

    started = asyncio.run(
        _request(
            app,
            "POST",
            f"/v1/products/client_update_writer/scenarios/{scenario_id}/start",
            json={
                "frontend_id": "web_mirror",
                "guest_id": GUEST_ID,
                "input": start_input,
            },
            request_id=REQUEST_ID,
        )
    ).json()

    worker = build_worker(
        session_factory=session_factory,
        config_root=CONFIG_ROOT,
        provider_adapters={"fake": _WeakInputProviderAdapter(FIXTURE_ROOT)},
    )
    processed = asyncio.run(worker.process_next_job())
    worker.dispose()

    assert processed is not None
    assert processed.status is JobStatus.succeeded, (
        processed.error_code,
        processed.error_message_safe,
    )
    assert processed.result_artifact_id is not None

    result_response = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/results/{processed.result_artifact_id}",
            request_id=REQUEST_ID,
        )
    )
    assert result_response.status_code == HTTPStatus.OK
    result_body = result_response.json()
    assert result_body["schema_ref"] == "kernel.schemas.compose_reply_output_v1"
    assert result_body["output"] == expected_output
