"""ANY-232 quick-check-covered evidence for the brief_decoder product bundle.

1. The product loads through anytoolai_platform_api.bootstrap.build_runtime()'s real default
   bundle set, with the exact A01 -> A04 -> A05 -> A10 action-type sequence.
2. Its input and composed-output schemas are non-permissive.
3. A real scenario start + one worker pass runs all four steps against the fake provider and the
   composed {brief, issues, questions, document} artifact equals the deterministic fixtures --
   happy path, weak input, and the empty-issues path (A04 finds nothing, so A05 is skipped instead
   of failing on its `minItems: 1` input) -- with per-step input-payload assertions so a swapped
   mapping, prompt_ref, or step order fails here, not just a wrong final artifact.

`session_factory`/`platform_api_app_factory`/`request_platform_api` (SQLite-backed) come from
apps/platform-api/tests/conftest.py, shared with test_proposal_ai_bundle.py and
test_client_update_writer_bundle.py.
"""

from __future__ import annotations

import asyncio
import json
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx
import jsonschema
import pytest
import sqlalchemy as sa
from anytoolai_platform_api.bootstrap import build_runtime
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.scenarios.checkpoints import RESULT_READY_CHECKPOINT_ID
from anytoolai_platform_core.storage.db import event_log_table, provider_calls_table
from anytoolai_platform_core.storage.transactions import SessionFactory, transaction_boundary
from anytoolai_platform_core.structured_output.schemas import normalize_schema_mapping
from anytoolai_platform_core.workflows.models import JobStatus
from anytoolai_platform_worker.composition import build_worker

from tests.support.fake_provider_recording import RecordingProviderAdapter

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "provider" / "fake_provider_outputs"
GUEST_ID = "guest_brief_decoder"

SCENARIO_ID = "brief_decoder.decode_v1"
INPUT_SCHEMA_REF = "brief_decoder.decode_input_v1"
OUTPUT_SCHEMA_REF = "brief_decoder.decode_output_v1"

EXTRACT = "brief_decoder.extract_brief_v1"
DETECT = "brief_decoder.detect_issues_v1"
QUESTIONS = "brief_decoder.generate_questions_v1"
SUMMARY = "brief_decoder.generate_summary_v1"
STEP_ORDER = (EXTRACT, DETECT, QUESTIONS, SUMMARY)
MAX_QUESTIONS = 5  # workflows.yaml passes it to A05 explicitly; decode_output_v1 caps at it

BRIEF_TEXT = (
    "We are a small bakery and need a new website. Goal: let customers order cakes online. It "
    "needs a menu page, an order form and a contact page. We want it live before the holiday "
    "season. Budget is around $3,000. Should look modern but also traditional."
)
WEAK_BRIEF_TEXT = "Need a website. Make it nice."
# Code review finding (me #5): the no_issues test used to send the ambiguous BRIEF_TEXT above --
# the same text the happy-path A04 fixture already flags with 3 issues -- to a scenario whose
# fixtures claim a clean, complete brief. A dedicated, genuinely unambiguous text is required for
# the no_issues fixtures (extract_brief_v1.no_issues.json et al.) to be a faithful A01/A04
# extraction rather than a self-consistent but ungrounded fabrication: it states every A01 field
# explicitly, closes the ambiguity/scope questions BRIEF_TEXT leaves open, and gives a concrete
# deadline and an already-approved budget.
CLEAN_BRIEF_TEXT = (
    "We are a small bakery. We want a website so customers can browse our menu and place cake "
    "orders online; checkout will go through a third-party payment processor, so we are not "
    "building our own payment system. Deliverables: a menu page, an online order form with "
    "checkout, and a contact page. The website must launch by 2026-11-02, in time for the "
    "holiday season. The budget is a fixed $3,000, already approved. The target audience is "
    "local families and small offices in our town who order celebration cakes for birthdays "
    "and other events. Style: clean and minimal, using our existing logo colors of navy and "
    "cream; no other design direction is needed."
)


def _fixture(key: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / f"{key}.json").read_text(encoding="utf-8"))["response_json"]


def _expected_output(suffix: str = "") -> dict[str, Any]:
    """The composed workflow output the fixtures must produce: brief = A01 output whole, issues =
    A04's `issues`, questions = A05's `questions`, document = A10."""
    return {
        "brief": _fixture(EXTRACT + suffix),
        "issues": _fixture(DETECT + suffix)["issues"],
        "questions": _fixture(QUESTIONS + suffix)["questions"],
        "document": _fixture(SUMMARY + suffix),
    }


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
        {"brief_text": "trailing space "},
        {"brief_text": "trailing newline\n"},
        {"brief_text": "\nleading newline"},
        {"brief_text": "x" * 8001},
        {"brief_text": BRIEF_TEXT, "tone": "warm"},
    ],
    ids=[
        "missing",
        "empty",
        "whitespace",
        "leading_space",
        "trailing_space",
        "trailing_newline",
        "leading_newline",
        "too_long",
        "extra_field",
    ],
)
def test_input_schema_is_non_permissive(invalid_input: dict[str, Any]) -> None:
    registry = build_runtime(config_root=CONFIG_ROOT).config_registry
    definition = registry.get_schema(INPUT_SCHEMA_REF)
    assert definition is not None
    schema = normalize_schema_mapping(definition.schema)

    jsonschema.validate({"brief_text": BRIEF_TEXT}, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_input, schema)


@pytest.mark.parametrize(
    "valid_input",
    [
        "x" * 8000,  # exactly at the max-length boundary
        "Line one of the brief.\nLine two of the brief.",  # a legal internal newline
        BRIEF_TEXT,
    ],
    ids=["max_length_boundary", "internal_newline", "typical"],
)
def test_input_schema_accepts_legitimate_edge_cases(valid_input: str) -> None:
    registry = build_runtime(config_root=CONFIG_ROOT).config_registry
    definition = registry.get_schema(INPUT_SCHEMA_REF)
    assert definition is not None
    schema = normalize_schema_mapping(definition.schema)

    jsonschema.validate({"brief_text": valid_input}, schema)


def test_output_schema_accepts_the_fixtures_and_rejects_open_shapes() -> None:
    registry = build_runtime(config_root=CONFIG_ROOT).config_registry
    definition = registry.get_schema(OUTPUT_SCHEMA_REF)
    assert definition is not None
    schema = normalize_schema_mapping(definition.schema)

    for suffix in ("", ".weak_input"):
        jsonschema.validate(_expected_output(suffix), schema)
    no_issues_output = {
        "brief": _fixture(EXTRACT + ".no_issues"),
        "issues": [],
        "questions": [],
        "document": _fixture(SUMMARY + ".no_issues"),
    }
    jsonschema.validate(no_issues_output, schema)

    valid = _expected_output()

    def mutated(mutate: Any) -> dict[str, Any]:
        candidate = json.loads(json.dumps(valid))
        mutate(candidate)
        return candidate

    def _swap_first_two_sections(candidate: dict[str, Any]) -> None:
        sections = candidate["document"]["sections"]
        sections[0], sections[1] = sections[1], sections[0]

    invalid_outputs = {
        "unknown_top_level_key": mutated(lambda o: o.update(extra=1)),
        "missing_part": mutated(lambda o: o.pop("document")),
        "unknown_brief_value": mutated(lambda o: o["brief"]["values"].update(invented="x")),
        "wrong_brief_value_type": mutated(lambda o: o["brief"]["values"].update(deliverables="x")),
        "empty_string_brief_value": mutated(lambda o: o["brief"]["values"].update(budget="")),
        "empty_array_brief_value": mutated(lambda o: o["brief"]["values"].update(deliverables=[])),
        "unknown_missing_field": mutated(lambda o: o["brief"]["missing_fields"].append("invented")),
        "category_outside_taxonomy": mutated(lambda o: o["issues"][0].update(category="other")),
        "unknown_question_key": mutated(lambda o: o["questions"][0].update(extra=1)),
        "question_category_outside_taxonomy": mutated(
            lambda o: o["questions"][0].update(category="other")
        ),
        # Code review finding (me #8): stored results are re-validated against this schema only,
        # not A01's/A05's cross-validators, so their invariants must hold here too.
        "field_both_present_and_missing": mutated(
            lambda o: o["brief"]["missing_fields"].append("budget")
        ),
        "duplicate_missing_field": mutated(
            lambda o: o["brief"]["missing_fields"].append("target_audience")
        ),
        "field_absent_from_values_and_missing_fields": mutated(
            lambda o: o["brief"].update(missing_fields=[])
        ),
        "confidence_for_unpopulated_field": mutated(
            lambda o: o["brief"]["confidence"].update(target_audience=0.5)
        ),
        "questions_without_issues": mutated(lambda o: o.update(issues=[])),
        "too_many_questions": mutated(
            lambda o: o.update(questions=[o["questions"][0]] * (MAX_QUESTIONS + 1))
        ),
        "empty_document": mutated(lambda o: o["document"].update(sections=[])),
        # Code review finding (me #1): document.sections must be exactly the product's own four
        # sections, in order, with fixed ids/titles -- not an open-ended array A10 has no
        # cross-validator for.
        "document_section_with_arbitrary_id": mutated(
            lambda o: o["document"]["sections"][0].update(id="random", title="Random")
        ),
        "document_missing_a_section": mutated(lambda o: o["document"]["sections"].pop()),
        "document_sections_reordered": mutated(_swap_first_two_sections),
        # Code review finding (me #5): generate_summary.v1.md requires metadata.kind = "list" on
        # key-details and next-steps unconditionally -- the schema used to leave metadata
        # optional and, when present, open to any of the 5 kind values.
        # Code review finding (me #6): free-form canonical strings were `minLength: 1` only, so a
        # whitespace-only value passed -- A01/A04/A05 and their validators don't reject it either.
        "whitespace_brief_value": mutated(lambda o: o["brief"]["values"].update(budget="   ")),
        "whitespace_deliverable_item": mutated(
            lambda o: o["brief"]["values"].update(deliverables=[" "])
        ),
        "whitespace_issue_description": mutated(
            lambda o: o["issues"][0].update(description=" ")
        ),
        "whitespace_issue_evidence": mutated(lambda o: o["issues"][0].update(evidence="\n")),
        "whitespace_question": mutated(lambda o: o["questions"][0].update(question="  ")),
        "whitespace_question_rationale": mutated(
            lambda o: o["questions"][0].update(rationale=" ")
        ),
        "key_details_missing_metadata": mutated(
            lambda o: o["document"]["sections"][1].pop("metadata")
        ),
        "key_details_wrong_kind": mutated(
            lambda o: o["document"]["sections"][1].update(metadata={"kind": "table"})
        ),
        "next_steps_missing_metadata": mutated(
            lambda o: o["document"]["sections"][3].pop("metadata")
        ),
        "next_steps_wrong_kind": mutated(
            lambda o: o["document"]["sections"][3].update(metadata={"kind": "note"})
        ),
    }
    validator = jsonschema.validators.validator_for(schema)(schema)
    for name, candidate in invalid_outputs.items():
        assert not validator.is_valid(candidate), name


@pytest.fixture
def app(platform_api_app_factory):
    return platform_api_app_factory(guest_id=GUEST_ID)


def _start(app: Any, request_platform_api, brief_text: str) -> httpx.Response:
    return asyncio.run(
        request_platform_api(
            app,
            "POST",
            f"/v1/products/brief_decoder/scenarios/{SCENARIO_ID}/start",
            json={
                "frontend_id": "web_mirror",
                "guest_id": GUEST_ID,
                "input": {"brief_text": brief_text},
            },
            request_id="req_brief_decoder_start",
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


def _provider_call_count(session_factory: SessionFactory, *, job_id: str) -> int:
    with transaction_boundary(session_factory) as session:
        return session.execute(
            sa.select(sa.func.count())
            .select_from(provider_calls_table)
            .where(provider_calls_table.c.job_id == job_id)
        ).scalar_one()


def _run_to_result(
    app: Any,
    request_platform_api,
    session_factory: SessionFactory,
    brief_text: str,
    adapter: FakeProviderAdapter,
) -> tuple[dict[str, Any], dict[str, Any]]:
    started = _start(app, request_platform_api, brief_text).json()
    processed = _run_worker(session_factory, adapter)
    assert processed is not None
    assert processed.id == started["job_id"]
    assert processed.status is JobStatus.succeeded, (
        processed.error_code,
        processed.error_message_safe,
    )
    assert processed.result_artifact_id is not None

    session_body = asyncio.run(
        request_platform_api(
            app,
            "GET",
            f"/v1/scenario-sessions/{started['scenario_session_id']}",
            request_id="req_brief_decoder_session",
        )
    ).json()
    assert session_body["status"] == "completed"
    assert session_body["current_checkpoint_id"] == RESULT_READY_CHECKPOINT_ID
    assert session_body["allowed_next_actions"] == ["copy_result"]

    result = asyncio.run(
        request_platform_api(
            app,
            "GET",
            f"/v1/results/{processed.result_artifact_id}",
            request_id="req_brief_decoder_result",
        )
    )
    assert result.status_code == HTTPStatus.OK
    body = result.json()
    assert body["schema_ref"] == OUTPUT_SCHEMA_REF
    return started, body["output"]


def test_happy_path_composes_the_four_step_result(
    app: Any, request_platform_api, session_factory: SessionFactory
) -> None:
    adapter = RecordingProviderAdapter(FIXTURE_ROOT)
    started, output = _run_to_result(
        app, request_platform_api, session_factory, BRIEF_TEXT, adapter
    )

    assert tuple(call.action_config_id for call in adapter.calls) == STEP_ORDER
    assert tuple(call.step_id for call in adapter.calls) == (
        "extract",
        "detect_issues",
        "generate_questions",
        "generate_document",
    )
    assert output == _expected_output()

    # Code review finding (round #1 xhigh #2): the call sequence alone doesn't prove each step
    # received the *right* data -- a mapping swapped between steps could still leave every
    # fixture output valid. Assert the resolved input payload per step instead.
    extract_input, detect_input, questions_input, document_input = (
        adapter.input_payload(i) for i in range(4)
    )
    assert extract_input["source_text"] == BRIEF_TEXT
    assert extract_input["strict"] is False
    assert detect_input["source_text"] == BRIEF_TEXT  # not steps.extract.output -- order-only
    detected_issues = _fixture(DETECT)["issues"]
    assert questions_input["issues"] == detected_issues
    assert questions_input["context"] == BRIEF_TEXT
    assert questions_input["max_questions"] == MAX_QUESTIONS
    assert document_input["data"]["brief"] == _fixture(EXTRACT)
    assert document_input["data"]["issues"] == detected_issues
    assert document_input["data"]["questions"] == _fixture(QUESTIONS)["questions"]

    # The one next action this product allows is recorded through the generic endpoint.
    response = asyncio.run(
        request_platform_api(
            app,
            "POST",
            f"/v1/scenario-sessions/{started['scenario_session_id']}/next-actions/copy_result",
            json={"checkpoint_id": RESULT_READY_CHECKPOINT_ID},
            request_id="req_brief_decoder_next_action",
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
    app: Any, request_platform_api, session_factory: SessionFactory
) -> None:
    adapter = RecordingProviderAdapter(
        FIXTURE_ROOT, variants={step: ".weak_input" for step in STEP_ORDER}
    )
    _, output = _run_to_result(
        app, request_platform_api, session_factory, WEAK_BRIEF_TEXT, adapter
    )

    assert tuple(call.action_config_id for call in adapter.calls) == STEP_ORDER
    assert output == _expected_output(".weak_input")
    assert output["brief"]["missing_fields"]  # a vague brief reports gaps instead of failing


def test_no_issues_skips_question_generation_and_still_produces_a_consistent_document(
    app: Any, request_platform_api, session_factory: SessionFactory
) -> None:
    """A04's `issues` may be empty but A05's input requires at least one: the `when` guard on
    the questions step must skip it (not fail the run) and leave the seeded `questions: []`.

    Code review finding (round #1 xhigh #3): the document must come from a fixture that is
    itself consistent with an empty `issues`/`questions` pair (not the happy-path document,
    which narrates 3 issues and 3 questions that don't exist in this run's artifact).

    Code review finding (me #4): this scenario must be a genuinely complete brief, not just an
    A04-clean one -- reusing the happy path's A01 fixture (`missing_fields: ["target_audience"]`)
    here meant the run certified "no issues, no questions, but a known gap nothing can ask about"
    (A05 only ever derives from A04's `issues`, never from A01's `missing_fields`), while
    `detect_issues.v1.md` itself lists `missing_information` as a taxonomy category A04 should
    have caught in the same source text.

    Code review finding (me #5): fixing that by adding a `.no_issues` A01 fixture wasn't enough
    on its own -- it still ran against `BRIEF_TEXT`, the same ambiguous text the happy-path A04
    fixture already flags with 3 issues for this exact input, so the fixtures were self-consistent
    but not grounded in what was actually sent. Uses `CLEAN_BRIEF_TEXT` instead, a dedicated brief
    that states every A01 field explicitly and closes the ambiguity/scope gaps `BRIEF_TEXT` leaves
    open, and asserts the resolved `source_text` payload matches it (mirroring the happy-path
    test's own input-payload assertions)."""
    adapter = RecordingProviderAdapter(
        FIXTURE_ROOT,
        variants={EXTRACT: ".no_issues", DETECT: ".no_issues", SUMMARY: ".no_issues"},
    )
    _, output = _run_to_result(
        app, request_platform_api, session_factory, CLEAN_BRIEF_TEXT, adapter
    )

    assert tuple(call.action_config_id for call in adapter.calls) == (EXTRACT, DETECT, SUMMARY)
    extract_input, detect_input, _ = (adapter.input_payload(i) for i in range(3))
    assert extract_input["source_text"] == CLEAN_BRIEF_TEXT
    assert detect_input["source_text"] == CLEAN_BRIEF_TEXT
    assert output["issues"] == []
    assert output["questions"] == []
    assert output["brief"] == _fixture(EXTRACT + ".no_issues")
    assert output["brief"]["missing_fields"] == []
    assert output["document"] == _fixture(SUMMARY + ".no_issues")
    # The empty-issues document must not narrate the happy path's issues/questions, which do not
    # exist in this run's artifact.
    happy_document_text = json.dumps(_fixture(SUMMARY))
    no_issues_document_text = json.dumps(output["document"])
    assert no_issues_document_text != happy_document_text

    # A brief with no issues and nothing missing is the one case generate_summary.v1.md's
    # readiness rule actually allows to claim the brief is ready.
    summary = output["document"]["summary"].lower()
    assert "ready" in summary
    assert "not ready" not in summary and "not fully ready" not in summary


@pytest.mark.parametrize("brief_text", ["", "   ", " padded "], ids=["empty", "blank", "untrimmed"])
def test_invalid_brief_text_fails_the_job_before_any_provider_call(
    app: Any, request_platform_api, session_factory: SessionFactory, brief_text: str
) -> None:
    started = _start(app, request_platform_api, brief_text).json()

    adapter = RecordingProviderAdapter(FIXTURE_ROOT)
    processed = _run_worker(session_factory, adapter)

    assert processed is not None
    assert processed.status is JobStatus.failed
    assert processed.error_code == "workflow_input_validation_failed"
    assert processed.result_artifact_id is None
    assert adapter.calls == []
    assert _provider_call_count(session_factory, job_id=started["job_id"]) == 0
