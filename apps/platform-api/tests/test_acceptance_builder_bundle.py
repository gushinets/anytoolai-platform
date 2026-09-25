"""ANY-228 quick-check-covered evidence for the acceptance_builder product bundle.

1. The product loads through anytoolai_platform_api.bootstrap.build_runtime()'s real default
   bundle set, with exact per-scenario action-type sequences (A01 -> A10 for draft_v1,
   A01 -> A11 -> A10 for check_v1, A10 alone for draft_from_brief_v1, the Brief Decoder handoff
   target).
2. Its input and composed-output schemas are non-permissive.
3. A real scenario start + one worker pass runs every step against the fake provider and the
   composed artifact equals the deterministic fixtures -- happy path and weak input, per scenario
   -- with per-step input-payload assertions so a swapped mapping or step order fails here.

`session_factory`/`platform_api_app_factory`/`request_platform_api` (SQLite-backed) come from
apps/platform-api/tests/conftest.py, shared with the other product bundle tests.
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
GUEST_ID = "guest_acceptance_builder"

DRAFT = "acceptance_builder.draft_v1"
CHECK = "acceptance_builder.check_v1"
FROM_BRIEF = "acceptance_builder.draft_from_brief_v1"
EXTRACT = "acceptance_builder.extract_v1"
COMPARE = "acceptance_builder.compare_v1"
DRAFT_DOCUMENT = "acceptance_builder.draft_document_v1"
CHECK_DOCUMENT = "acceptance_builder.check_document_v1"
FROM_BRIEF_DOCUMENT = "acceptance_builder.draft_from_brief_document_v1"
BRIEF_DECODER_EXTRACT = "brief_decoder.extract_brief_v1"
STEPS = {
    DRAFT: (EXTRACT, DRAFT_DOCUMENT),
    CHECK: (EXTRACT, COMPARE, CHECK_DOCUMENT),
    FROM_BRIEF: (FROM_BRIEF_DOCUMENT,),
}
ACTION_TYPES = {
    DRAFT: ("text.extract_structured_fields", "document.generate_from_template"),
    CHECK: (
        "text.extract_structured_fields",
        "text.compare_and_classify",
        "document.generate_from_template",
    ),
    FROM_BRIEF: ("document.generate_from_template",),
}
INPUT_SCHEMA_REFS = {
    DRAFT: "acceptance_builder.draft_input_v1",
    CHECK: "acceptance_builder.check_input_v1",
    FROM_BRIEF: "acceptance_builder.draft_from_brief_input_v1",
}
OUTPUT_SCHEMA_REFS = {
    DRAFT: "acceptance_builder.draft_output_v1",
    CHECK: "acceptance_builder.check_output_v1",
    FROM_BRIEF: "acceptance_builder.draft_from_brief_output_v1",
}

BRIEF_TEXT = (
    "We run an online course platform and need a certificate generator. Goal: students receive a "
    "PDF certificate automatically after finishing a course. Deliverables: a certificate "
    "template in our brand colors, an automated PDF generation service, and an email that "
    "delivers the certificate. It must work for all existing courses. We assume the completion "
    "data already exists in our database. Delivery is expected in six weeks."
)
DELIVERABLE_TEXT = (
    "The certificate generator is live. Students receive a PDF certificate by email right after "
    "they finish a course. The template uses our brand colors. Certificates work for the 12 "
    "courses in the new catalog; the 5 legacy courses are not connected yet."
)
WEAK_BRIEF_TEXT = "Need a certificate thing for my courses."
WEAK_DELIVERABLE_TEXT = "Done, works."


def _fixture(key: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / f"{key}.json").read_text(encoding="utf-8"))["response_json"]


def _expected_output(scenario_id: str, suffix: str = "") -> dict[str, Any]:
    """The composed workflow output the fixtures must produce: extracted = A01 output whole,
    comparison = A11 output whole (check_v1 only), document = A10."""
    if scenario_id == FROM_BRIEF:
        return {"document": _fixture(FROM_BRIEF_DOCUMENT + suffix)}
    output: dict[str, Any] = {"extracted": _fixture(EXTRACT + suffix)}
    if scenario_id == CHECK:
        output["comparison"] = _fixture(COMPARE + suffix)
        output["document"] = _fixture(CHECK_DOCUMENT + suffix)
    else:
        output["document"] = _fixture(DRAFT_DOCUMENT + suffix)
    return output


def _schema(schema_ref: str) -> dict[str, Any]:
    definition = build_runtime(config_root=CONFIG_ROOT).config_registry.get_schema(schema_ref)
    assert definition is not None
    return normalize_schema_mapping(definition.schema)


def test_acceptance_builder_loads_through_the_real_default_bundle_set() -> None:
    result = build_runtime(config_root=CONFIG_ROOT)

    assert "freelancer_suite" in result.loaded_bundles
    product = result.config_registry.products["acceptance_builder"]
    assert set(product.scenarios) == {DRAFT, CHECK, FROM_BRIEF}

    for scenario_id in (DRAFT, CHECK, FROM_BRIEF):
        scenario = result.config_registry.get_scenario(scenario_id)
        assert scenario is not None
        assert scenario.workflow_id == scenario_id
        workflow = result.config_registry.get_workflow(scenario_id)
        assert workflow is not None
        assert workflow.input_schema_ref == INPUT_SCHEMA_REFS[scenario_id]
        assert workflow.output_schema_ref == OUTPUT_SCHEMA_REFS[scenario_id]
        assert (
            tuple(
                result.config_registry.get_action_configuration(step.action_config_id).action_type
                for step in workflow.steps
            )
            == ACTION_TYPES[scenario_id]
        )
        assert tuple(step.action_config_id for step in workflow.steps) == STEPS[scenario_id]


@pytest.mark.parametrize(
    ("scenario_id", "invalid_input"),
    [
        (DRAFT, {}),
        (DRAFT, {"brief_text": ""}),
        (DRAFT, {"brief_text": "   "}),
        (DRAFT, {"brief_text": " leading space"}),
        (DRAFT, {"brief_text": "trailing newline\n"}),
        (DRAFT, {"brief_text": "x" * 8001}),
        (DRAFT, {"brief_text": BRIEF_TEXT, "deliverable_text": DELIVERABLE_TEXT}),
        (CHECK, {"brief_text": BRIEF_TEXT}),
        (CHECK, {"deliverable_text": DELIVERABLE_TEXT}),
        (CHECK, {"brief_text": BRIEF_TEXT, "deliverable_text": ""}),
        (CHECK, {"brief_text": BRIEF_TEXT, "deliverable_text": " padded "}),
        (CHECK, {"brief_text": BRIEF_TEXT, "deliverable_text": "y" * 8001}),
        (CHECK, {"brief_text": BRIEF_TEXT, "deliverable_text": DELIVERABLE_TEXT, "tone": "warm"}),
    ],
)
def test_input_schemas_are_non_permissive(scenario_id: str, invalid_input: dict[str, Any]) -> None:
    schema = _schema(INPUT_SCHEMA_REFS[scenario_id])
    valid = {"brief_text": BRIEF_TEXT}
    if scenario_id == CHECK:
        valid["deliverable_text"] = DELIVERABLE_TEXT

    jsonschema.validate(valid, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_input, schema)


def _brief_decoder_brief(suffix: str = "") -> dict[str, Any]:
    """Brief Decoder's real `brief` output part (its A01 fixture is that part whole)."""
    return _fixture(BRIEF_DECODER_EXTRACT + suffix)


@pytest.mark.parametrize(
    "invalid_input",
    [
        {},
        {"brief_text": BRIEF_TEXT},
        {"brief": {}},
        {"brief": {"values": {}}},
        {"brief": {"values": {"budget": ""}, "missing_fields": []}},
        {"brief": {"values": {"deliverables": []}, "missing_fields": []}},
        {"brief": {"values": {"invented": "x"}, "missing_fields": []}},
        {"brief": {"values": {}, "missing_fields": ["invented"]}},
        {"brief": {"values": {}, "missing_fields": []}},  # every field in neither values nor missing
        {"brief": _brief_decoder_brief(), "extra": 1},
    ],
)
def test_draft_from_brief_input_schema_is_non_permissive(invalid_input: dict[str, Any]) -> None:
    schema = _schema(INPUT_SCHEMA_REFS[FROM_BRIEF])

    jsonschema.validate({"brief": _brief_decoder_brief()}, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_input, schema)


@pytest.mark.parametrize("suffix", ["", ".weak_input", ".no_issues"])
def test_draft_from_brief_accepts_every_real_brief_decoder_brief(suffix: str) -> None:
    jsonschema.validate(
        {"brief": _brief_decoder_brief(suffix)}, _schema(INPUT_SCHEMA_REFS[FROM_BRIEF])
    )


def test_input_schemas_accept_legitimate_edge_cases() -> None:
    schema = _schema(INPUT_SCHEMA_REFS[CHECK])

    jsonschema.validate({"brief_text": "x" * 8000, "deliverable_text": "y" * 8000}, schema)
    jsonschema.validate({"brief_text": "Line one.\nLine two.", "deliverable_text": "a\nb"}, schema)


def _mutated(valid: dict[str, Any], mutate: Any) -> dict[str, Any]:
    candidate = json.loads(json.dumps(valid))
    mutate(candidate)
    return candidate


def _shared_invalid_outputs(valid: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Mutations that must be rejected by both output schemas."""

    def swap_first_two_sections(o: dict[str, Any]) -> None:
        sections = o["document"]["sections"]
        sections[0], sections[1] = sections[1], sections[0]

    return {
        "unknown_top_level_key": _mutated(valid, lambda o: o.update(extra=1)),
        "missing_document": _mutated(valid, lambda o: o.pop("document")),
        "missing_extracted": _mutated(valid, lambda o: o.pop("extracted")),
        "unknown_extracted_value": _mutated(
            valid, lambda o: o["extracted"]["values"].update(invented=["x"])
        ),
        "extracted_value_not_a_list": _mutated(
            valid, lambda o: o["extracted"]["values"].update(assumptions="x")
        ),
        "empty_extracted_list": _mutated(
            valid, lambda o: o["extracted"]["values"].update(deliverables=[])
        ),
        "whitespace_extracted_item": _mutated(
            valid, lambda o: o["extracted"]["values"].update(deliverables=[" "])
        ),
        "unknown_missing_field": _mutated(
            valid, lambda o: o["extracted"]["missing_fields"].append("invented")
        ),
        "field_both_present_and_missing": _mutated(
            valid, lambda o: o["extracted"]["missing_fields"].append("assumptions")
        ),
        "field_absent_from_values_and_missing_fields": _mutated(
            valid, lambda o: o["extracted"]["values"].pop("assumptions")
        ),
        "duplicate_missing_field": _mutated(
            valid,
            lambda o: (
                o["extracted"]["values"].pop("assumptions"),
                o["extracted"]["missing_fields"].extend(["assumptions", "assumptions"]),
            ),
        ),
        "confidence_for_unpopulated_field": _mutated(
            valid,
            lambda o: (
                o["extracted"]["values"].pop("assumptions"),
                o["extracted"]["missing_fields"].append("assumptions"),
                o["extracted"]["confidence"].update(assumptions=0.5),
            ),
        ),
        "document_section_with_arbitrary_id": _mutated(
            valid, lambda o: o["document"]["sections"][0].update(id="random", title="Random")
        ),
        "document_missing_a_section": _mutated(valid, lambda o: o["document"]["sections"].pop()),
        "document_sections_reordered": _mutated(valid, swap_first_two_sections),
        "empty_summary": _mutated(valid, lambda o: o["document"].update(summary=" ")),
    }


def test_draft_from_brief_output_schema_rejects_open_shapes() -> None:
    schema = _schema(OUTPUT_SCHEMA_REFS[FROM_BRIEF])
    validator = jsonschema.validators.validator_for(schema)(schema)
    valid = _expected_output(FROM_BRIEF)
    for suffix in ("", ".weak_input"):
        jsonschema.validate(_expected_output(FROM_BRIEF, suffix), schema)

    invalid = {
        "unknown_top_level_key": _mutated(valid, lambda o: o.update(extra=1)),
        "missing_document": _mutated(valid, lambda o: o.pop("document")),
        "extracted_is_not_part_of_this_output": _mutated(valid, lambda o: o.update(extracted={})),
        "document_missing_a_section": _mutated(valid, lambda o: o["document"]["sections"].pop()),
        "document_extra_section": _mutated(
            valid, lambda o: o["document"]["sections"].append(o["document"]["sections"][0])
        ),
        "document_section_with_arbitrary_id": _mutated(
            valid, lambda o: o["document"]["sections"][0].update(id="random", title="Random")
        ),
        "list_section_missing_metadata": _mutated(
            valid, lambda o: o["document"]["sections"][0].pop("metadata")
        ),
        "list_section_wrong_kind": _mutated(
            valid, lambda o: o["document"]["sections"][1].update(metadata={"kind": "table"})
        ),
        "blank_section_content": _mutated(
            valid, lambda o: o["document"]["sections"][2].update(content=" ")
        ),
        "empty_summary": _mutated(valid, lambda o: o["document"].update(summary=" ")),
    }
    for name, candidate in invalid.items():
        assert not validator.is_valid(candidate), name


@pytest.mark.parametrize("scenario_id", [DRAFT, CHECK])
def test_output_schema_accepts_the_fixtures_and_rejects_open_shapes(scenario_id: str) -> None:
    schema = _schema(OUTPUT_SCHEMA_REFS[scenario_id])
    validator = jsonschema.validators.validator_for(schema)(schema)
    for suffix in ("", ".weak_input"):
        jsonschema.validate(_expected_output(scenario_id, suffix), schema)

    valid = _expected_output(scenario_id)
    invalid = _shared_invalid_outputs(valid)
    # The list sections must carry metadata.kind = list (the prompts require it).
    list_section = 1 if scenario_id == CHECK else 0
    invalid["list_section_missing_metadata"] = _mutated(
        valid, lambda o: o["document"]["sections"][list_section].pop("metadata")
    )
    invalid["list_section_wrong_kind"] = _mutated(
        valid,
        lambda o: o["document"]["sections"][list_section].update(metadata={"kind": "table"}),
    )
    if scenario_id == CHECK:
        invalid.update(_comparison_mutations(valid))
    for name, candidate in invalid.items():
        assert not validator.is_valid(candidate), name


def _comparison_mutations(valid: dict[str, Any]) -> dict[str, dict[str, Any]]:
    def set_status(index: int, status: str) -> Any:
        return lambda o: o["comparison"]["deltas"][index].update(status=status)

    def swap_first_two_deltas(o: dict[str, Any]) -> None:
        deltas = o["comparison"]["deltas"]
        deltas[0], deltas[1] = deltas[1], deltas[0]

    return {
        "missing_comparison": _mutated(valid, lambda o: o.pop("comparison")),
        "unknown_comparison_key": _mutated(valid, lambda o: o["comparison"].update(extra=1)),
        "verdict_outside_categories": _mutated(
            valid, lambda o: o["comparison"].update(verdict="meets_bar")
        ),
        "confidence_out_of_range": _mutated(valid, lambda o: o["comparison"].update(confidence=2)),
        "rationale_too_long": _mutated(valid, lambda o: o["comparison"].update(rationale="x" * 501)),
        "missing_a_delta": _mutated(valid, lambda o: o["comparison"]["deltas"].pop()),
        "extra_delta": _mutated(
            valid, lambda o: o["comparison"]["deltas"].append(o["comparison"]["deltas"][0])
        ),
        "deltas_reordered": _mutated(valid, swap_first_two_deltas),
        "unknown_criterion_id": _mutated(
            valid, lambda o: o["comparison"]["deltas"][0].update(criterion_id="tone")
        ),
        "delta_status_outside_enum": _mutated(valid, set_status(0, "unknown")),
        "blank_delta_evidence": _mutated(
            valid, lambda o: o["comparison"]["deltas"][0].update(evidence=" ")
        ),
        # A11's cross-validator does not relate verdict to deltas; the product schema does.
        "does_not_meet_without_a_mismatch": _mutated(
            valid,
            lambda o: (
                o["comparison"].update(verdict="does_not_meet"),
                [d.update(status="match") for d in o["comparison"]["deltas"]],
            ),
        ),
        "does_not_meet_with_only_partial_deltas": _mutated(
            valid,
            lambda o: (
                o["comparison"].update(verdict="does_not_meet"),
                [d.update(status="partial") for d in o["comparison"]["deltas"]],
            ),
        ),
        "meets_expectations_with_a_mismatch": _mutated(
            valid,
            lambda o: (
                o["comparison"].update(verdict="meets_expectations"),
                o["comparison"]["deltas"][0].update(status="mismatch"),
            ),
        ),
    }


def test_does_not_meet_with_a_mismatch_is_valid() -> None:
    schema = _schema(OUTPUT_SCHEMA_REFS[CHECK])
    output = _expected_output(CHECK, ".weak_input")
    assert output["comparison"]["verdict"] == "does_not_meet"
    output["comparison"]["deltas"][1]["status"] = "partial"  # one mismatch left is enough

    jsonschema.validate(output, schema)


def test_meets_expectations_without_mismatch_is_valid() -> None:
    schema = _schema(OUTPUT_SCHEMA_REFS[CHECK])
    output = _expected_output(CHECK)
    output["comparison"]["verdict"] = "meets_expectations"
    for delta in output["comparison"]["deltas"]:
        delta["status"] = "match"

    jsonschema.validate(output, schema)


@pytest.fixture
def app(platform_api_app_factory):
    return platform_api_app_factory(guest_id=GUEST_ID)


def _start(
    app: Any, request_platform_api, scenario_id: str, input_payload: dict[str, Any]
) -> httpx.Response:
    return asyncio.run(
        request_platform_api(
            app,
            "POST",
            f"/v1/products/acceptance_builder/scenarios/{scenario_id}/start",
            json={"frontend_id": "web_mirror", "guest_id": GUEST_ID, "input": input_payload},
            request_id="req_acceptance_builder_start",
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
    scenario_id: str,
    input_payload: dict[str, Any],
    adapter: FakeProviderAdapter,
) -> tuple[dict[str, Any], dict[str, Any]]:
    started = _start(app, request_platform_api, scenario_id, input_payload).json()
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
            request_id="req_acceptance_builder_session",
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
            request_id="req_acceptance_builder_result",
        )
    )
    assert result.status_code == HTTPStatus.OK
    body = result.json()
    assert body["schema_ref"] == OUTPUT_SCHEMA_REFS[scenario_id]
    return started, body["output"]


def test_draft_happy_path_composes_the_two_step_result(
    app: Any, request_platform_api, session_factory: SessionFactory
) -> None:
    adapter = RecordingProviderAdapter(FIXTURE_ROOT)
    started, output = _run_to_result(
        app, request_platform_api, session_factory, DRAFT, {"brief_text": BRIEF_TEXT}, adapter
    )

    assert tuple(call.action_config_id for call in adapter.calls) == STEPS[DRAFT]
    assert tuple(call.step_id for call in adapter.calls) == ("extract", "generate_document")
    assert output == _expected_output(DRAFT)

    extract_input, document_input = adapter.input_payload(0), adapter.input_payload(1)
    assert extract_input["source_text"] == BRIEF_TEXT
    assert extract_input["strict"] is False
    assert [field["name"] for field in extract_input["fields"]] == [
        "acceptance_criteria",
        "assumptions",
        "deliverables",
    ]
    assert document_input["template_ref"] == DRAFT
    assert document_input["data"] == {"extracted": _fixture(EXTRACT)}

    # The one next action this product allows is recorded through the generic endpoint.
    response = asyncio.run(
        request_platform_api(
            app,
            "POST",
            f"/v1/scenario-sessions/{started['scenario_session_id']}/next-actions/copy_result",
            json={"checkpoint_id": RESULT_READY_CHECKPOINT_ID},
            request_id="req_acceptance_builder_next_action",
        )
    )
    assert response.status_code == HTTPStatus.OK
    with transaction_boundary(session_factory) as session:
        event = (
            session.execute(
                sa.select(event_log_table).where(
                    event_log_table.c.event_type == "client.next_action_clicked"
                )
            )
            .mappings()
            .one()
        )
    assert event["scenario_session_id"] == started["scenario_session_id"]
    assert event["properties"] == {
        "checkpoint_id": RESULT_READY_CHECKPOINT_ID,
        "next_action_id": "copy_result",
    }


def test_check_happy_path_composes_the_three_step_result(
    app: Any, request_platform_api, session_factory: SessionFactory
) -> None:
    adapter = RecordingProviderAdapter(FIXTURE_ROOT)
    _, output = _run_to_result(
        app,
        request_platform_api,
        session_factory,
        CHECK,
        {"brief_text": BRIEF_TEXT, "deliverable_text": DELIVERABLE_TEXT},
        adapter,
    )

    assert tuple(call.action_config_id for call in adapter.calls) == STEPS[CHECK]
    assert tuple(call.step_id for call in adapter.calls) == (
        "extract",
        "compare",
        "generate_document",
    )
    assert output == _expected_output(CHECK)

    extract_input, compare_input, document_input = (adapter.input_payload(i) for i in range(3))
    assert extract_input["source_text"] == BRIEF_TEXT
    assert compare_input["subject_text"] == DELIVERABLE_TEXT  # the work under review
    assert compare_input["reference_text"] == BRIEF_TEXT  # the expectations
    assert compare_input["categories"] == ["meets_expectations", "partially_meets", "does_not_meet"]
    assert [criterion["id"] for criterion in compare_input["criteria"]] == [
        "scope_coverage",
        "requirement_fit",
        "completeness",
        "clarity",
    ]
    assert document_input["template_ref"] == CHECK
    assert document_input["data"] == {
        "extracted": _fixture(EXTRACT),
        "comparison": _fixture(COMPARE),
    }


def test_weak_input_fixtures_are_reachable_end_to_end(
    app: Any, request_platform_api, session_factory: SessionFactory
) -> None:
    """Weak fixtures are only reachable through the test adapter's variant switch."""
    draft_adapter = RecordingProviderAdapter(
        FIXTURE_ROOT, variants={step: ".weak_input" for step in STEPS[DRAFT]}
    )
    _, draft_output = _run_to_result(
        app,
        request_platform_api,
        session_factory,
        DRAFT,
        {"brief_text": WEAK_BRIEF_TEXT},
        draft_adapter,
    )
    assert draft_output == _expected_output(DRAFT, ".weak_input")
    assert draft_output["extracted"]["missing_fields"]  # a vague brief reports gaps, not a failure

    check_adapter = RecordingProviderAdapter(
        FIXTURE_ROOT, variants={step: ".weak_input" for step in STEPS[CHECK]}
    )
    _, check_output = _run_to_result(
        app,
        request_platform_api,
        session_factory,
        CHECK,
        {"brief_text": WEAK_BRIEF_TEXT, "deliverable_text": WEAK_DELIVERABLE_TEXT},
        check_adapter,
    )
    assert check_output == _expected_output(CHECK, ".weak_input")
    assert check_output["comparison"]["verdict"] == "does_not_meet"


@pytest.mark.parametrize(
    ("scenario_id", "input_payload"),
    [
        (DRAFT, {"brief_text": ""}),
        (DRAFT, {"brief_text": " padded "}),
        (DRAFT, {"brief_text": BRIEF_TEXT, "deliverable_text": DELIVERABLE_TEXT}),
        (CHECK, {"brief_text": BRIEF_TEXT}),
        (CHECK, {"brief_text": BRIEF_TEXT, "deliverable_text": ""}),
    ],
    ids=["draft_empty", "draft_untrimmed", "draft_extra_field", "check_missing", "check_empty"],
)
def test_invalid_input_fails_the_job_before_any_provider_call(
    app: Any,
    request_platform_api,
    session_factory: SessionFactory,
    scenario_id: str,
    input_payload: dict[str, Any],
) -> None:
    started = _start(app, request_platform_api, scenario_id, input_payload).json()

    adapter = RecordingProviderAdapter(FIXTURE_ROOT)
    processed = _run_worker(session_factory, adapter)

    assert processed is not None
    assert processed.status is JobStatus.failed
    assert processed.error_code == "workflow_input_validation_failed"
    assert processed.result_artifact_id is None
    assert adapter.calls == []
    assert _provider_call_count(session_factory, job_id=started["job_id"]) == 0


@pytest.mark.parametrize(
    ("suffix", "adapter_variants"),
    [("", {}), (".weak_input", {FROM_BRIEF_DOCUMENT: ".weak_input"})],
)
def test_draft_from_brief_runs_on_a_real_brief_decoder_brief(
    app: Any,
    request_platform_api,
    session_factory: SessionFactory,
    suffix: str,
    adapter_variants: dict[str, str],
) -> None:
    """The handoff target consumes Brief Decoder's own `brief` output: the payload the provider
    sees carries that brief unchanged, and the document is the fixture grounded in it."""
    brief = _brief_decoder_brief(suffix)
    adapter = RecordingProviderAdapter(FIXTURE_ROOT, variants=adapter_variants)
    _, output = _run_to_result(
        app, request_platform_api, session_factory, FROM_BRIEF, {"brief": brief}, adapter
    )

    assert tuple(call.action_config_id for call in adapter.calls) == STEPS[FROM_BRIEF]
    assert adapter.calls[0].step_id == "generate_document"
    document_input = adapter.input_payload(0)
    assert document_input["template_ref"] == FROM_BRIEF
    assert document_input["data"] == {"brief": brief}
    assert output == _expected_output(FROM_BRIEF, suffix)


@pytest.mark.parametrize(
    "input_payload",
    [{"brief_text": BRIEF_TEXT}, {"brief": {"values": {}, "missing_fields": []}}],
    ids=["text_input_for_structured_scenario", "brief_with_field_in_neither_list"],
)
def test_invalid_draft_from_brief_input_fails_before_any_provider_call(
    app: Any, request_platform_api, session_factory: SessionFactory, input_payload: dict[str, Any]
) -> None:
    started = _start(app, request_platform_api, FROM_BRIEF, input_payload).json()

    adapter = RecordingProviderAdapter(FIXTURE_ROOT)
    processed = _run_worker(session_factory, adapter)

    assert processed is not None
    assert processed.status is JobStatus.failed
    assert processed.error_code == "workflow_input_validation_failed"
    assert adapter.calls == []
    assert _provider_call_count(session_factory, job_id=started["job_id"]) == 0
