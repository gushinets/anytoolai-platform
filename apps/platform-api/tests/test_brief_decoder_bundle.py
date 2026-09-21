"""ANY-232 quick-check-covered evidence for the brief_decoder product bundle.

1. The product loads through anytoolai_platform_api.bootstrap.build_runtime()'s real default
   bundle set, with the exact A01 -> A04 -> A05 -> A10 action-type sequence.
2. Its input and composed-output schemas are non-permissive.
3. A real scenario start + one worker pass runs all four steps against the fake provider and the
   composed {brief, issues, questions, document} artifact equals the deterministic fixtures --
   happy path, weak input, and the empty-issues path (A04 finds nothing, so A05 is skipped instead
   of failing on its `minItems: 1` input).

Same SQLite harness as test_client_update_writer_bundle.py (`session_factory` from conftest.py).
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
from anytoolai_platform_core.storage.db import event_log_table
from anytoolai_platform_core.storage.transactions import SessionFactory, transaction_boundary
from anytoolai_platform_core.structured_output.schemas import normalize_schema_mapping
from anytoolai_platform_core.workflows.models import JobStatus
from anytoolai_platform_worker.composition import build_worker

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "provider" / "fake_provider_outputs"

SCENARIO_ID = "brief_decoder.decode_v1"
INPUT_SCHEMA_REF = "brief_decoder.decode_input_v1"
OUTPUT_SCHEMA_REF = "brief_decoder.decode_output_v1"

EXTRACT = "brief_decoder.extract_brief_v1"
DETECT = "brief_decoder.detect_issues_v1"
QUESTIONS = "brief_decoder.generate_questions_v1"
SUMMARY = "brief_decoder.generate_summary_v1"
STEP_ORDER = (EXTRACT, DETECT, QUESTIONS, SUMMARY)

BRIEF_TEXT = (
    "We are a small bakery and need a new website. Goal: let customers order cakes online. It "
    "needs a menu page, an order form and a contact page. We want it live before the holiday "
    "season. Budget is around $3,000. Should look modern but also traditional."
)
WEAK_BRIEF_TEXT = "Need a website. Make it nice."


def _fixture(key: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / f"{key}.json").read_text(encoding="utf-8"))["response_json"]


def _expected_output(suffix: str = "", *, questions: bool = True) -> dict[str, Any]:
    """The composed workflow output the fixtures must produce: brief = A01 output whole, issues =
    A04's `issues`, questions = A05's `questions` (or [] when A05 is skipped), document = A10."""
    return {
        "brief": _fixture(EXTRACT + suffix),
        "issues": _fixture(DETECT + suffix)["issues"],
        "questions": _fixture(QUESTIONS + suffix)["questions"] if questions else [],
        "document": _fixture(SUMMARY + suffix),
    }


class _RecordingProviderAdapter(FakeProviderAdapter):
    """Records every provider call's action_config_id and can redirect chosen calls to a
    fixture variant: `variants` maps action_config_id -> fixture-key suffix, e.g. ".weak_input".
    Test-only; FakeProviderAdapter alone only ever resolves a call's own action_config_id."""

    def __init__(self, fixture_root: Path, variants: dict[str, str] | None = None) -> None:
        super().__init__(fixture_root)
        self.variants = variants or {}
        self.calls: list[str] = []

    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse:
        self.calls.append(request.action_config_id)
        suffix = self.variants.get(request.action_config_id)
        if suffix is not None:
            request = replace(request, fixture_key=f"{request.action_config_id}{suffix}")
        return await super().complete(request)


def test_brief_decoder_loads_through_the_real_default_bundle_set() -> None:
    result = build_runtime(config_root=CONFIG_ROOT)

    assert "freelancer_suite" in result.loaded_bundles
    product = result.config_registry.products["brief_decoder"]
    assert set(product.scenarios) == {SCENARIO_ID}

    scenario = result.config_registry.get_scenario(SCENARIO_ID)
    assert scenario is not None
    assert scenario.workflow_id == SCENARIO_ID

    workflow = result.config_registry.get_workflow(SCENARIO_ID)
    assert workflow is not None
    assert workflow.input_schema_ref == INPUT_SCHEMA_REF
    assert workflow.output_schema_ref == OUTPUT_SCHEMA_REF
    # Exact per-step sequence, not membership: A01 + A04 -> A05, composed through A10.
    assert tuple(
        result.config_registry.get_action_configuration(step.action_config_id).action_type
        for step in workflow.steps
    ) == (
        "text.extract_structured_fields",
        "text.detect_issues_by_taxonomy",
        "text.generate_clarifying_questions",
        "document.generate_from_template",
    )
    assert tuple(step.action_config_id for step in workflow.steps) == STEP_ORDER


@pytest.mark.parametrize(
    "invalid_input",
    [
        {},
        {"brief_text": ""},
        {"brief_text": "   "},
        {"brief_text": " leading space"},
        {"brief_text": "x" * 8001},
        {"brief_text": BRIEF_TEXT, "tone": "warm"},
    ],
    ids=["missing", "empty", "whitespace", "untrimmed", "too_long", "extra_field"],
)
def test_input_schema_is_non_permissive(invalid_input: dict[str, Any]) -> None:
    registry = build_runtime(config_root=CONFIG_ROOT).config_registry
    definition = registry.get_schema(INPUT_SCHEMA_REF)
    assert definition is not None
    schema = normalize_schema_mapping(definition.schema)

    jsonschema.validate({"brief_text": BRIEF_TEXT}, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_input, schema)


def test_output_schema_accepts_the_fixtures_and_rejects_open_shapes() -> None:
    registry = build_runtime(config_root=CONFIG_ROOT).config_registry
    definition = registry.get_schema(OUTPUT_SCHEMA_REF)
    assert definition is not None
    schema = normalize_schema_mapping(definition.schema)

    for suffix in ("", ".weak_input"):
        jsonschema.validate(_expected_output(suffix), schema)
    jsonschema.validate(_expected_output(questions=False), schema)

    valid = _expected_output()

    def mutated(mutate: Any) -> dict[str, Any]:
        candidate = json.loads(json.dumps(valid))
        mutate(candidate)
        return candidate

    invalid_outputs = {
        "unknown_top_level_key": mutated(lambda o: o.update(extra=1)),
        "missing_part": mutated(lambda o: o.pop("document")),
        "unknown_brief_value": mutated(lambda o: o["brief"]["values"].update(invented="x")),
        "wrong_brief_value_type": mutated(lambda o: o["brief"]["values"].update(deliverables="x")),
        "unknown_missing_field": mutated(lambda o: o["brief"]["missing_fields"].append("invented")),
        "category_outside_taxonomy": mutated(lambda o: o["issues"][0].update(category="other")),
        "unknown_question_key": mutated(lambda o: o["questions"][0].update(extra=1)),
        "empty_document": mutated(lambda o: o["document"].update(sections=[])),
    }
    validator = jsonschema.validators.validator_for(schema)(schema)
    for name, candidate in invalid_outputs.items():
        assert not validator.is_valid(candidate), name


@pytest.fixture
def app(session_factory: SessionFactory):
    with transaction_boundary(session_factory) as session:
        GuestIdentityRepository(session).create(
            GuestIdentityRecord(id="guest_brief_decoder", tenant_id="anytoolai", region="default")
        )
    application = create_app(config_root=CONFIG_ROOT)
    application.state.runtime = replace(
        application.state.runtime,
        storage=RuntimeStorageDependencies(session_factory=session_factory),
    )
    return application


async def _request(
    app: Any, method: str, path: str, *, json: Any | None = None
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(
            method, path, json=json, headers={"X-Request-ID": "req_brief_decoder_test"}
        )


def _start(app: Any, brief_text: str) -> httpx.Response:
    return asyncio.run(
        _request(
            app,
            "POST",
            f"/v1/products/brief_decoder/scenarios/{SCENARIO_ID}/start",
            json={
                "frontend_id": "web_mirror",
                "guest_id": "guest_brief_decoder",
                "input": {"brief_text": brief_text},
            },
        )
    )


def _run_worker(session_factory: SessionFactory, adapter: FakeProviderAdapter) -> Any:
    worker = build_worker(
        session_factory=session_factory,
        config_root=CONFIG_ROOT,
        provider_adapters={"fake": adapter},
    )
    processed = asyncio.run(worker.process_next_job())
    worker.dispose()
    return processed


def _run_to_result(
    app: Any,
    session_factory: SessionFactory,
    brief_text: str,
    adapter: FakeProviderAdapter,
) -> tuple[dict[str, Any], dict[str, Any]]:
    started = _start(app, brief_text).json()
    processed = _run_worker(session_factory, adapter)
    assert processed is not None
    assert processed.id == started["job_id"]
    assert processed.status is JobStatus.succeeded, (
        processed.error_code,
        processed.error_message_safe,
    )
    assert processed.result_artifact_id is not None

    session_body = asyncio.run(
        _request(app, "GET", f"/v1/scenario-sessions/{started['scenario_session_id']}")
    ).json()
    assert session_body["status"] == "completed"
    assert session_body["current_checkpoint_id"] == RESULT_READY_CHECKPOINT_ID
    assert session_body["allowed_next_actions"] == ["copy_result"]

    result = asyncio.run(_request(app, "GET", f"/v1/results/{processed.result_artifact_id}"))
    assert result.status_code == HTTPStatus.OK
    body = result.json()
    assert body["schema_ref"] == OUTPUT_SCHEMA_REF
    return started, body["output"]


def test_happy_path_composes_the_four_step_result(app: Any, session_factory: SessionFactory) -> None:
    adapter = _RecordingProviderAdapter(FIXTURE_ROOT)
    started, output = _run_to_result(app, session_factory, BRIEF_TEXT, adapter)

    assert tuple(adapter.calls) == STEP_ORDER
    assert output == _expected_output()

    # The one next action this product allows is recorded through the generic endpoint.
    response = asyncio.run(
        _request(
            app,
            "POST",
            f"/v1/scenario-sessions/{started['scenario_session_id']}/next-actions/copy_result",
            json={"checkpoint_id": RESULT_READY_CHECKPOINT_ID},
        )
    )
    assert response.status_code == HTTPStatus.OK
    with transaction_boundary(session_factory) as session:
        event = session.execute(
            sa.select(event_log_table).where(
                event_log_table.c.event_type == "client.next_action_clicked"
            )
        ).mappings().one()
    assert event["scenario_session_id"] == started["scenario_session_id"]
    assert event["properties"] == {
        "checkpoint_id": RESULT_READY_CHECKPOINT_ID,
        "next_action_id": "copy_result",
    }


def test_weak_input_fixtures_are_reachable_end_to_end(
    app: Any, session_factory: SessionFactory
) -> None:
    adapter = _RecordingProviderAdapter(
        FIXTURE_ROOT, variants={step: ".weak_input" for step in STEP_ORDER}
    )
    _, output = _run_to_result(app, session_factory, WEAK_BRIEF_TEXT, adapter)

    assert tuple(adapter.calls) == STEP_ORDER
    assert output == _expected_output(".weak_input")
    assert output["brief"]["missing_fields"]  # a vague brief reports gaps instead of failing


def test_no_issues_skips_question_generation_and_still_produces_the_document(
    app: Any, session_factory: SessionFactory
) -> None:
    """A04's `issues` may be empty but A05's input requires at least one: the `when` guard on
    the questions step must skip it (not fail the run) and leave the seeded `questions: []`."""
    adapter = _RecordingProviderAdapter(FIXTURE_ROOT, variants={DETECT: ".no_issues"})
    _, output = _run_to_result(app, session_factory, BRIEF_TEXT, adapter)

    assert tuple(adapter.calls) == (EXTRACT, DETECT, SUMMARY)
    assert output["issues"] == []
    assert output["questions"] == []
    assert output["brief"] == _fixture(EXTRACT)
    assert output["document"] == _fixture(SUMMARY)


@pytest.mark.parametrize("brief_text", ["", "   ", " padded "], ids=["empty", "blank", "untrimmed"])
def test_invalid_brief_text_fails_the_job_before_any_provider_call(
    app: Any, session_factory: SessionFactory, brief_text: str
) -> None:
    _start(app, brief_text)

    adapter = _RecordingProviderAdapter(FIXTURE_ROOT)
    processed = _run_worker(session_factory, adapter)

    assert processed is not None
    assert processed.status is JobStatus.failed
    assert processed.error_code == "workflow_input_validation_failed"
    assert adapter.calls == []
