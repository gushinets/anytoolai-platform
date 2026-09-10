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
from dataclasses import replace
from http import HTTPStatus
from pathlib import Path
from typing import Any, Iterator

import httpx
import jsonschema
import pytest
from anytoolai_platform_api.bootstrap import RuntimeStorageDependencies, build_runtime
from anytoolai_platform_api.main import create_app
from anytoolai_platform_core.identity.models import GuestIdentityRecord
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.scenarios.checkpoints import RESULT_READY_CHECKPOINT_ID
from anytoolai_platform_core.storage.db import runtime_metadata
from anytoolai_platform_core.storage.transactions import (
    SessionFactory,
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.structured_output.schemas import normalize_schema_mapping
from anytoolai_platform_core.workflows.models import JobStatus
from anytoolai_platform_worker.composition import build_worker

from tests.support.sqlite_harness import build_sqlite_runtime_engine

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "provider" / "fake_provider_outputs"


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


@pytest.fixture
def session_factory(tmp_path: Path) -> Iterator[SessionFactory]:
    engine = build_sqlite_runtime_engine(
        tmp_path / "main.sqlite3",
        tmp_path / "platform.sqlite3",
    )
    runtime_metadata.create_all(engine)
    try:
        yield build_session_factory(engine)
    finally:
        engine.dispose()


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
            "call_to_action": "Let me know by Friday if you'd like any changes to the homepage.",
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
                "Wednesday, and that covers both the copy edits and the final review pass you "
                "asked about."
            ),
            "call_to_action": "Let me know if Wednesday works, or if you need it sooner.",
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
                "The design phase you approved wraps up this week, and getting the prepayment "
                "in now keeps development starting on schedule right after. Could you send the "
                "$500 prepayment for phase 2 before Friday?"
            ),
            "call_to_action": "Please send the $500 prepayment and reply once it's on its way.",
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
                "guest_id": "guest_client_update_writer",
                "input": start_input,
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
        )
    )
    assert result_response.status_code == HTTPStatus.OK
    result_body = result_response.json()
    assert result_body["schema_ref"] == "kernel.schemas.compose_reply_output_v1"
    assert result_body["output"] == expected_output
