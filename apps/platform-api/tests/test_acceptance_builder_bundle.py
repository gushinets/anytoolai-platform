"""ANY-228 quick-check-covered evidence for the acceptance_builder product bundle.

1. The product loads through anytoolai_platform_api.bootstrap.build_runtime()'s real default
   bundle set, with A01, A04 and conditional A05 for draft_v1 and A01 -> A11 for check_v1.
2. Its input and composed-output schemas are non-permissive.
3. A real scenario start + one worker pass runs every step against the fake provider and the
   composed artifact equals the deterministic fixtures -- happy path and weak input, per scenario
   -- with per-step input-payload assertions so a swapped mapping or step order fails here.

`session_factory`/`platform_api_app_factory`/`request_platform_api` (SQLite-backed) come from
apps/platform-api/tests/conftest.py, shared with the other product bundle tests.
"""

from __future__ import annotations

import asyncio
import copy
import json
import re
from dataclasses import replace
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx
import jsonschema
import pytest
import sqlalchemy as sa
from anytoolai_platform_actions.structured_llm.cross_validation import extract_structured_fields
from anytoolai_platform_api.bootstrap import build_runtime
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.common.authored_text import has_authored_text
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.scenarios.checkpoints import RESULT_READY_CHECKPOINT_ID
from anytoolai_platform_core.storage.db import event_log_table, provider_calls_table
from anytoolai_platform_core.storage.transactions import SessionFactory, transaction_boundary
from anytoolai_platform_core.structured_output.errors import StructuredOutputSchemaMismatchError
from anytoolai_platform_core.structured_output.schemas import (
    normalize_schema_mapping,
    publication_schema,
)
from anytoolai_platform_core.structured_output.validator import validate_structured_output_value
from anytoolai_platform_core.workflows.models import JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from anytoolai_platform_core.workflows.runner import SequentialWorkflowRunner
from anytoolai_platform_worker.composition import build_worker

from tests.support.brief_language import CANONICAL, golden_cases, write_provider_fixtures
from tests.support.fake_provider_recording import RecordingProviderAdapter

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "provider" / "fake_provider_outputs"
GUEST_ID = "guest_acceptance_builder"

DRAFT = "acceptance_builder.draft_v1"
CHECK = "acceptance_builder.check_v1"
EXTRACT = "acceptance_builder.extract_v1"
COMPARE = "acceptance_builder.compare_v1"
DETECT = "acceptance_builder.detect_issues_v1"
QUESTIONS = "acceptance_builder.generate_questions_v1"
STEPS = {
    DRAFT: (EXTRACT, DETECT, QUESTIONS),
    CHECK: (EXTRACT, COMPARE),
}
ACTION_TYPES = {
    DRAFT: (
        "text.extract_structured_fields",
        "text.detect_issues_by_taxonomy",
        "text.generate_clarifying_questions",
    ),
    CHECK: (
        "text.extract_structured_fields",
        "text.compare_and_classify",
    ),
}
INPUT_SCHEMA_REFS = {
    DRAFT: "acceptance_builder.draft_input_v1",
    CHECK: "acceptance_builder.check_input_v1",
}
OUTPUT_SCHEMA_REFS = {
    DRAFT: "acceptance_builder.draft_output_v1",
    CHECK: "acceptance_builder.check_output_v1",
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
    comparison = A11 output whole (check_v1 only)."""
    output: dict[str, Any] = {"extracted": _fixture(EXTRACT + suffix)}
    if scenario_id == CHECK:
        output["comparison"] = _fixture(COMPARE + suffix)
    else:
        output.update(_fixture(DETECT + suffix))
        output["questions"] = _fixture(QUESTIONS + suffix)["questions"] if output["issues"] else []
    return output


def _schema(schema_ref: str) -> dict[str, Any]:
    definition = build_runtime(config_root=CONFIG_ROOT).config_registry.get_schema(schema_ref)
    assert definition is not None
    return normalize_schema_mapping(definition.schema)


@pytest.mark.parametrize("scenario_id", [DRAFT, CHECK])
@pytest.mark.parametrize("suffix", ["", ".weak_input"])
def test_canonical_language_tags_match_the_client_contract(scenario_id: str, suffix: str) -> None:
    tags = json.loads(
        (REPO_ROOT / "tests/fixtures/brief_language_eval/language_tags.json").read_text(
            encoding="utf-8"
        )
    )
    schema = _schema(OUTPUT_SCHEMA_REFS[scenario_id])
    output = _expected_output(scenario_id, suffix)
    for tag in tags["accepted"]:
        output["extracted"]["values"]["analysis_language"] = tag
        validated = validate_structured_output_value(output, schema=schema)
        assert validated.normalized_output == output
    for tag in tags["rejected"]:
        output["extracted"]["values"]["analysis_language"] = tag
        with pytest.raises(StructuredOutputSchemaMismatchError):
            validate_structured_output_value(output, schema=schema)


def test_acceptance_builder_loads_through_the_real_default_bundle_set() -> None:
    result = build_runtime(config_root=CONFIG_ROOT)

    assert "freelancer_suite" in result.loaded_bundles
    product = result.config_registry.products["acceptance_builder"]
    assert set(product.scenarios) == {DRAFT, CHECK}

    for scenario_id in (DRAFT, CHECK):
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

    return {
        "unknown_top_level_key": _mutated(valid, lambda o: o.update(extra=1)),
        "independent_document": _mutated(valid, lambda o: o.update(document={"summary": "false"})),
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
    }


@pytest.mark.parametrize("scenario_id", [DRAFT, CHECK])
def test_output_schema_accepts_the_fixtures_and_rejects_open_shapes(scenario_id: str) -> None:
    schema = _schema(OUTPUT_SCHEMA_REFS[scenario_id])
    validator = jsonschema.validators.validator_for(schema)(schema)
    for suffix in ("", ".weak_input"):
        jsonschema.validate(_expected_output(scenario_id, suffix), schema)

    valid = _expected_output(scenario_id)
    invalid = _shared_invalid_outputs(valid)
    if scenario_id == CHECK:
        invalid.update(_comparison_mutations(valid))
    else:
        question = _fixture(QUESTIONS)["questions"][0]
        jsonschema.validate({"extracted": valid["extracted"]}, schema)
        invalid["missing_issues"] = _mutated(valid, lambda o: o.pop("issues"))
        invalid["missing_questions"] = _mutated(valid, lambda o: o.pop("questions"))
        invalid["unknown_question_key"] = dict(valid, questions=[dict(question, extra=True)])
        invalid["too_many_questions"] = dict(valid, questions=[question] * 6)
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
        "rationale_too_long": _mutated(
            valid, lambda o: o["comparison"].update(rationale="x" * 501)
        ),
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


def _check_output_with(verdict: str, statuses: list[str]) -> dict[str, Any]:
    """Control only verdict/status values to isolate the structured consistency rule."""
    output = _expected_output(CHECK)
    output["comparison"]["verdict"] = verdict
    for delta, status in zip(output["comparison"]["deltas"], statuses, strict=True):
        delta["status"] = status
    return output


@pytest.mark.parametrize(
    ("verdict", "statuses"),
    [
        ("meets_expectations", ["match"] * 4),
        ("partially_meets", ["match", "match", "match", "partial"]),
        ("partially_meets", ["partial"] * 4),
        ("does_not_meet", ["match", "match", "match", "mismatch"]),
        ("does_not_meet", ["mismatch"] * 4),
        ("does_not_meet", ["partial", "mismatch", "match", "partial"]),
    ],
)
def test_verdict_that_follows_from_the_delta_statuses_is_valid(
    verdict: str, statuses: list[str]
) -> None:
    jsonschema.validate(_check_output_with(verdict, statuses), _schema(OUTPUT_SCHEMA_REFS[CHECK]))


@pytest.mark.parametrize(
    ("verdict", "statuses"),
    [
        ("meets_expectations", ["match", "match", "match", "partial"]),
        ("meets_expectations", ["match", "match", "match", "mismatch"]),
        ("partially_meets", ["match"] * 4),
        ("partially_meets", ["match", "partial", "mismatch", "match"]),
        ("partially_meets", ["mismatch"] * 4),
        ("does_not_meet", ["match"] * 4),
        ("does_not_meet", ["partial"] * 4),
    ],
)
def test_verdict_that_contradicts_the_delta_statuses_is_rejected(
    verdict: str, statuses: list[str]
) -> None:
    """A11's cross-validator checks only category membership and criterion coverage; the product
    schema is the last guard, so the verdict must be the partition of the statuses: all match =>
    meets, any mismatch => does not meet, otherwise partially meets."""
    schema = _schema(OUTPUT_SCHEMA_REFS[CHECK])
    validator = jsonschema.validators.validator_for(schema)(schema)

    assert not validator.is_valid(_check_output_with(verdict, statuses))


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


def test_draft_happy_path_composes_the_structured_result(
    app: Any, request_platform_api, session_factory: SessionFactory
) -> None:
    adapter = RecordingProviderAdapter(FIXTURE_ROOT)
    started, output = _run_to_result(
        app, request_platform_api, session_factory, DRAFT, {"brief_text": BRIEF_TEXT}, adapter
    )

    assert tuple(call.action_config_id for call in adapter.calls) == (EXTRACT, DETECT)
    assert tuple(call.step_id for call in adapter.calls) == ("extract", "detect_issues")
    assert output == _expected_output(DRAFT)

    extract_input = adapter.input_payload(0)
    assert extract_input["source_text"] == BRIEF_TEXT
    assert extract_input["strict"] is True
    assert [field["name"] for field in extract_input["fields"]] == [
        "acceptance_criteria",
        "assumptions",
        "deliverables",
        "analysis_language",
    ]

    # Verify the Draft-specific policy was actually sent to A01.
    descriptions = {field["name"]: field["description"] for field in extract_input["fields"]}
    assert "omit acceptance_criteria from values" in descriptions["acceptance_criteria"]
    assert "keep the independently checkable conditions" in descriptions["acceptance_criteria"]
    assert "omit assumptions and list it in missing_fields" in descriptions["assumptions"]

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


@pytest.mark.parametrize("stored_text", [None, "\ufeff", "\u200b"])
def test_result_api_reopens_persisted_draft_v1(
    app: Any, request_platform_api, session_factory: SessionFactory, stored_text: str | None
) -> None:
    started, _ = _run_to_result(
        app,
        request_platform_api,
        session_factory,
        DRAFT,
        {"brief_text": BRIEF_TEXT},
        RecordingProviderAdapter(FIXTURE_ROOT),
    )
    evidence_path = (
        REPO_ROOT / "tests/fixtures/acceptance_builder_eval/any-894-pre-fix.evidence.json"
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    legacy_output = evidence["runs"][0]["output"]
    if stored_text is not None:
        legacy_output = _expected_output(DRAFT, ".weak_input")
        legacy_output["questions"][0]["question"] = stored_text
    with transaction_boundary(session_factory) as session:
        jobs = JobRepository(session)
        job = jobs.get(started["job_id"])
        assert job is not None and job.result_artifact_id is not None
        assert job.workflow_version == 1
        artifacts = ArtifactRepository(session)
        artifact = artifacts.get(job.result_artifact_id)
        assert artifact is not None
        artifacts.update(replace(artifact, content_json=legacy_output))

    response = asyncio.run(
        request_platform_api(
            app, "GET", f"/v1/results/{artifact.id}", request_id="req_legacy_draft_result"
        )
    )
    assert response.status_code == HTTPStatus.OK, response.text
    result = response.json()
    assert result["workflow_version"] == 1
    assert result["schema_ref"] == OUTPUT_SCHEMA_REFS[DRAFT]
    assert result["schema_version"] == 1
    assert result["output"] == legacy_output


def test_check_happy_path_composes_the_structured_result(
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
    )
    assert output == _expected_output(CHECK)

    extract_input, compare_input = (adapter.input_payload(i) for i in range(2))
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
    assert tuple(call.action_config_id for call in draft_adapter.calls) == STEPS[DRAFT]
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
    ("action", "field", "invalid", "recover"),
    [
        (EXTRACT, "deliverables", [], True),
        (EXTRACT, "deliverables", ["  "], True),
        (EXTRACT, "analysis_language", "ru_RU", True),
        (EXTRACT, "acceptance_criteria", ["\u200b"], True),
        (DETECT, "evidence", "\u2067\u2069", True),
        (QUESTIONS, "rationale", "\U000e0100", False),
        (DETECT, "description", " ", True),
        (DETECT, "evidence", "\t", True),
        (QUESTIONS, "question", "\n", True),
        (QUESTIONS, "rationale", " \t\n", True),
        (EXTRACT, "deliverables", ["\ufeff"], True),
        (DETECT, "description", "\ufeff", True),
        (QUESTIONS, "question", "\ufeff", True),
        (QUESTIONS, "question", " \ufeff\u0085", False),
        (QUESTIONS, "question", "  ", False),
    ],
)
def test_draft_retries_invalid_atom_before_publishing(
    app, request_platform_api, session_factory, action, field, invalid, recover
):
    class InvalidOutputAdapter(RecordingProviderAdapter):
        async def complete(self, request):
            response = await super().complete(request)
            if request.action_config_id == action and (
                request.semantic_attempt_index == 1 or not recover
            ):
                output = json.loads(response.output_text)
                value = (
                    output["values"]
                    if action == EXTRACT
                    else output["issues" if action == DETECT else "questions"][0]
                )
                value[field] = invalid
                return replace(response, output_text=json.dumps(output))
            return response

    registry = app.state.runtime.config_registry
    fake = registry.provider_policies["default_fake_provider_v1"]
    live_retry = registry.provider_policies["sol_text_generation_v1"].retry_policy
    policies = {
        **registry.provider_policies,
        fake.provider_policy_ref: replace(fake, retry_policy=live_retry),
    }
    suffix = "" if field == "acceptance_criteria" else ".weak_input"
    brief = WEAK_BRIEF_TEXT if suffix else BRIEF_TEXT
    adapter = InvalidOutputAdapter(FIXTURE_ROOT, variants={step: suffix for step in STEPS[DRAFT]})
    worker = build_worker(
        session_factory=session_factory,
        config_root=CONFIG_ROOT,
        config_registry=replace(registry, provider_policies=policies),
        provider_adapters={"fake": adapter},
    )
    started = _start(app, request_platform_api, DRAFT, {"brief_text": brief}).json()
    try:
        job = asyncio.run(worker.process_job(started["job_id"]))
    finally:
        worker.dispose()
    assert [c.semantic_attempt_index for c in adapter.calls if c.action_config_id == action] == [
        1,
        2,
    ]
    if recover:
        assert job.status is JobStatus.succeeded
        response = asyncio.run(
            request_platform_api(
                app,
                "GET",
                f"/v1/results/{job.result_artifact_id}",
                request_id="req_recovered_draft",
            )
        )
        assert response.status_code == HTTPStatus.OK
        assert response.json()["output"] == _expected_output(DRAFT, suffix)
    else:
        assert job.status is JobStatus.failed
        assert job.result_artifact_id is None


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
def test_invalid_input_is_rejected_at_start_before_any_job_or_provider_call(
    app: Any,
    request_platform_api,
    session_factory: SessionFactory,
    scenario_id: str,
    input_payload: dict[str, Any],
) -> None:
    # Code review finding (ANY-601): start_session() now validates the input against the
    # workflow's input schema, so an invalid payload is rejected at /start (422) before any
    # job is queued or quota consumed -- it no longer reaches the worker at all.
    response = _start(app, request_platform_api, scenario_id, input_payload)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert response.json()["error"]["code"] == "scenario_input_invalid"

    adapter = RecordingProviderAdapter(FIXTURE_ROOT)
    assert _run_worker(session_factory, adapter) is None  # no job was queued
    assert adapter.calls == []
    with transaction_boundary(session_factory) as session:
        count = session.execute(sa.select(sa.func.count()).select_from(provider_calls_table))
        assert count.scalar_one() == 0


@pytest.mark.parametrize("case", golden_cases("acceptance_builder"), ids=lambda case: case["id"])
def test_multilingual_canonical_output_and_original_language_source(
    app: Any,
    request_platform_api,
    session_factory: SessionFactory,
    tmp_path: Path,
    case: dict[str, Any],
) -> None:
    expected = write_provider_fixtures(tmp_path, case)
    adapter = RecordingProviderAdapter(tmp_path)
    _, output = _run_to_result(
        app, request_platform_api, session_factory, case["scenario_id"], case["input"], adapter
    )
    assert output == expected  # Includes summary, evidence, rationale and every section.
    source = case["input"]["brief_text"]
    assert adapter.input_payload(0)["source_text"] == source
    if case["scenario_id"] == DRAFT:
        assert adapter.input_payload(1)["source_text"] == source
    else:
        assert adapter.input_payload(1)["reference_text"] == source
        assert adapter.input_payload(1)["subject_text"] == case["input"]["deliverable_text"]


@pytest.mark.parametrize("language", ["RU", "ES"])
@pytest.mark.parametrize("scenario", ["D", "C"])
def test_output_rejects_independent_contradictory_recap(language, scenario):
    output = copy.deepcopy(CANONICAL[f"ANY761-AB-{scenario}-{language}-basic"])
    assert "document" not in output
    mode = DRAFT if scenario == "D" else CHECK
    schema = _schema(OUTPUT_SCHEMA_REFS[mode])
    jsonschema.validate(output, schema)
    output["document"] = {
        "summary": "Все три списка отсутствуют" if language == "RU" else "Faltan las tres listas",
        "sections": [
            {
                "id": "verdict",
                "content": "Соответствует ожиданиям"
                if language == "RU"
                else "Cumple las expectativas",
            }
        ],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(output, schema)


def test_python_and_published_authored_text_match_for_every_code_point():
    schema = _schema(OUTPUT_SCHEMA_REFS[DRAFT])
    pattern = re.compile(schema["$defs"]["authoredText"]["pattern"])
    for code in range(0x110000):
        character = chr(code)
        assert has_authored_text(character) == bool(pattern.search(character)), hex(code)


@pytest.mark.parametrize(
    ("schema_name", "section", "fields"),
    [
        ("issue_detection_output", "issues", ("description", "evidence")),
        ("generate_questions_input", "issues", ("description", "evidence")),
        ("generate_questions_output", "questions", ("question", "rationale")),
        ("draft", "questions", ("question", "rationale")),
    ],
)
def test_atom_and_publication_text_contracts_share_the_unicode_boundary(
    schema_name, section, fields
):
    fixture = REPO_ROOT / "tests/fixtures/acceptance_builder_eval/authored_text.json"
    vectors = json.loads(fixture.read_text(encoding="utf-8"))
    draft = _expected_output(DRAFT, ".weak_input")
    if schema_name == "draft":
        schema = _schema(OUTPUT_SCHEMA_REFS[DRAFT])
        payload = draft
    else:
        path = CONFIG_ROOT / f"schemas/{schema_name}.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        payload = {section: draft[section]}
        if schema_name == "generate_questions_input":
            payload.update(context="brief", target_audience="client")
    validator = jsonschema.Draft202012Validator(publication_schema(schema))
    first, *rest = payload[section]
    for kind, samples in vectors.items():
        expected = kind == "text"
        for sample in samples:
            assert extract_structured_fields._nonblank_string(sample) == expected
            for field in fields:
                modified = {**payload, section: [{**first, field: sample}, *rest]}
                assert validator.is_valid(modified) == expected, (field, ascii(sample))


def test_workflow_refuses_to_publish_blank_text_from_final_mapping(
    app, request_platform_api, session_factory, monkeypatch
):
    select_output = SequentialWorkflowRunner._select_final_output

    def select_with_blank_text(runner, state):
        payload, source = select_output(runner, state)
        payload["extracted"]["values"]["deliverables"][0] = "\u200b"
        return payload, source

    monkeypatch.setattr(SequentialWorkflowRunner, "_select_final_output", select_with_blank_text)
    started = _start(app, request_platform_api, DRAFT, {"brief_text": BRIEF_TEXT}).json()
    job = _run_worker(session_factory, RecordingProviderAdapter(FIXTURE_ROOT))
    assert job.id == started["job_id"]
    assert job.status is JobStatus.failed
    assert job.error_code == "workflow_output_validation_failed"
    assert job.result_artifact_id is None
