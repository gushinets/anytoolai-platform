"""ANY-231 quick-check-covered evidence for the task_finder product bundle.

1. The product loads through anytoolai_platform_api.bootstrap.build_runtime()'s real default
   bundle set, with the exact action-type sequence (A11 -> A02).
2. Its input and output schemas are non-permissive, and the output schema binds the verdict to
   the delta statuses.
3. A real scenario start + one worker pass runs both steps against the fake provider and the
   artifact equals the deterministic fixtures -- happy path and weak input -- with per-step
   input-payload assertions; invalid input fails before any provider call.

`session_factory`/`platform_api_app_factory`/`request_platform_api` (SQLite-backed) come from
apps/platform-api/tests/conftest.py, shared with the other product bundle tests.
"""

from __future__ import annotations

import asyncio
import functools
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
GUEST_ID = "guest_task_finder"

FIT = "task_finder.fit_v1"
COMPARE = "task_finder.compare_v1"
SCORE = "task_finder.score_v1"
INPUT_SCHEMA_REF = "task_finder.fit_input_v1"
OUTPUT_SCHEMA_REF = "task_finder.fit_output_v1"
CRITERION_IDS = ["skills_fit", "experience_fit", "scope_fit", "constraints_fit"]

TASK_TEXT = (
    "Rebuild our analytics dashboard in React and TypeScript, and add a mobile app. Six-week "
    "timeline, fixed budget."
)
PROFILE_TEXT = (
    "Front-end developer: React and TypeScript, five years building dashboards. Web only, no "
    "mobile apps. Available part time from next month."
)
WEAK_TASK_TEXT = "Need some website help."
WEAK_PROFILE_TEXT = "I do web stuff."
WEAK_SCORE_CEILING = 50


def _fixture(key: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / f"{key}.json").read_text(encoding="utf-8"))["response_json"]


def _expected_output(task: str, profile: str, suffix: str = "") -> dict[str, Any]:
    return {
        "task_text": task,
        "freelancer_positioning": profile,
        "comparison": _fixture(COMPARE + suffix),
        "match": _fixture(SCORE + suffix),
    }


@functools.cache
def _schema_cache(schema_ref: str) -> str:
    # One runtime load per schema, not per case; JSON text so callers cannot mutate the cache.
    definition = build_runtime(config_root=CONFIG_ROOT).config_registry.get_schema(schema_ref)
    assert definition is not None
    return json.dumps(normalize_schema_mapping(definition.schema))


def _schema(schema_ref: str) -> dict[str, Any]:
    return json.loads(_schema_cache(schema_ref))


def _validator(schema_ref: str) -> Any:
    schema = _schema(schema_ref)
    return jsonschema.validators.validator_for(schema)(schema)


def _mutated(valid: dict[str, Any], mutate: Any) -> dict[str, Any]:
    candidate = json.loads(json.dumps(valid))
    mutate(candidate)
    return candidate


def test_task_finder_loads_through_the_real_default_bundle_set() -> None:
    result = build_runtime(config_root=CONFIG_ROOT)

    assert "freelancer_suite" in result.loaded_bundles
    product = result.config_registry.products["task_finder"]
    assert set(product.scenarios) == {FIT}

    scenario = result.config_registry.get_scenario(FIT)
    assert scenario is not None
    assert scenario.workflow_id == FIT
    workflow = result.config_registry.get_workflow(FIT)
    assert workflow is not None
    assert workflow.input_schema_ref == INPUT_SCHEMA_REF
    assert workflow.output_schema_ref == OUTPUT_SCHEMA_REF
    assert tuple(step.action_config_id for step in workflow.steps) == (COMPARE, SCORE)
    assert tuple(
        result.config_registry.get_action_configuration(step.action_config_id).action_type
        for step in workflow.steps
    ) == ("text.compare_and_classify", "text.score_match_by_rubric")


@pytest.mark.parametrize(
    "invalid_input",
    [
        {},
        {"task_text": TASK_TEXT},
        {"freelancer_positioning": PROFILE_TEXT},
        {"task_text": "", "freelancer_positioning": PROFILE_TEXT},
        {"task_text": "   ", "freelancer_positioning": PROFILE_TEXT},
        {"task_text": " padded", "freelancer_positioning": PROFILE_TEXT},
        {"task_text": TASK_TEXT, "freelancer_positioning": "trailing newline\n"},
        {"task_text": "x" * 4001, "freelancer_positioning": PROFILE_TEXT},
        {"task_text": TASK_TEXT, "freelancer_positioning": "y" * 4001},
        {"task_text": TASK_TEXT, "freelancer_positioning": PROFILE_TEXT, "tone": "warm"},
    ],
)
def test_input_schema_is_non_permissive(invalid_input: dict[str, Any]) -> None:
    schema = _schema(INPUT_SCHEMA_REF)

    jsonschema.validate({"task_text": TASK_TEXT, "freelancer_positioning": PROFILE_TEXT}, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_input, schema)


def test_input_schema_accepts_legitimate_edge_cases() -> None:
    schema = _schema(INPUT_SCHEMA_REF)

    jsonschema.validate({"task_text": "x" * 4000, "freelancer_positioning": "y" * 4000}, schema)
    jsonschema.validate(
        {"task_text": "Line one.\nLine two.", "freelancer_positioning": "a"}, schema
    )


@pytest.mark.parametrize("suffix", ["", ".weak_input"])
def test_fixtures_satisfy_the_output_schema(suffix: str) -> None:
    jsonschema.validate(
        _expected_output(TASK_TEXT, PROFILE_TEXT, suffix), _schema(OUTPUT_SCHEMA_REF)
    )


def _invalid_outputs(valid: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "unknown_top_level_key": _mutated(valid, lambda o: o.update(extra=1)),
        "missing_task_text": _mutated(valid, lambda o: o.pop("task_text")),
        "missing_profile": _mutated(valid, lambda o: o.pop("freelancer_positioning")),
        "missing_comparison": _mutated(valid, lambda o: o.pop("comparison")),
        "missing_match": _mutated(valid, lambda o: o.pop("match")),
        "unknown_verdict": _mutated(valid, lambda o: o["comparison"].update(verdict="maybe")),
        "confidence_above_one": _mutated(valid, lambda o: o["comparison"].update(confidence=1.5)),
        "unknown_comparison_key": _mutated(valid, lambda o: o["comparison"].update(extra=1)),
        "three_deltas": _mutated(valid, lambda o: o["comparison"]["deltas"].pop()),
        "five_deltas": _mutated(
            valid, lambda o: o["comparison"]["deltas"].append(o["comparison"]["deltas"][0])
        ),
        "duplicate_delta_id": _mutated(
            valid, lambda o: o["comparison"]["deltas"][1].update(criterion_id="skills_fit")
        ),
        "unknown_delta_id": _mutated(
            valid, lambda o: o["comparison"]["deltas"][1].update(criterion_id="invented")
        ),
        "duplicate_score_id": _mutated(
            valid, lambda o: o["match"]["criterion_scores"][1].update(criterion_id="skills_fit")
        ),
        "unknown_delta_status": _mutated(
            valid, lambda o: o["comparison"]["deltas"][0].update(status="maybe")
        ),
        "empty_delta_evidence": _mutated(
            valid, lambda o: o["comparison"]["deltas"][0].update(evidence="")
        ),
        "long_rationale": _mutated(valid, lambda o: o["comparison"].update(rationale="x" * 501)),
        "three_scores": _mutated(valid, lambda o: o["match"]["criterion_scores"].pop()),
        "score_above_100": _mutated(valid, lambda o: o["match"].update(score=101)),
        "criterion_score_negative": _mutated(
            valid, lambda o: o["match"]["criterion_scores"][0].update(score=-1)
        ),
        "empty_gap": _mutated(valid, lambda o: o["match"]["gaps"].append("")),
        "unknown_match_key": _mutated(valid, lambda o: o["match"].update(extra=1)),
        "task_text_too_long": _mutated(valid, lambda o: o.update(task_text="x" * 4001)),
    }


def test_output_schema_does_not_depend_on_criterion_order() -> None:
    """The atoms' cross-validators check id coverage, not array order, so the product schema must
    accept any order too; a stricter schema would fail live runs after both calls are paid."""
    output = _expected_output(TASK_TEXT, PROFILE_TEXT)
    output["comparison"]["deltas"].reverse()
    output["match"]["criterion_scores"].reverse()

    jsonschema.validate(output, _schema(OUTPUT_SCHEMA_REF))


def test_output_schema_rejects_malformed_results() -> None:
    validator = _validator(OUTPUT_SCHEMA_REF)

    for name, candidate in _invalid_outputs(_expected_output(TASK_TEXT, PROFILE_TEXT)).items():
        assert not validator.is_valid(candidate), name


def _output_with(verdict: str, statuses: list[str]) -> dict[str, Any]:
    output = _expected_output(TASK_TEXT, PROFILE_TEXT)
    output["comparison"]["verdict"] = verdict
    for delta, status in zip(output["comparison"]["deltas"], statuses, strict=True):
        delta["status"] = status
    return output


@pytest.mark.parametrize(
    ("verdict", "statuses"),
    [
        ("strong_fit", ["match"] * 4),
        ("partial_fit", ["match", "match", "match", "partial"]),
        ("partial_fit", ["partial"] * 4),
        ("weak_fit", ["match", "match", "match", "mismatch"]),
        ("weak_fit", ["partial", "mismatch", "match", "partial"]),
    ],
)
def test_verdict_that_follows_from_the_delta_statuses_is_valid(
    verdict: str, statuses: list[str]
) -> None:
    jsonschema.validate(_output_with(verdict, statuses), _schema(OUTPUT_SCHEMA_REF))


@pytest.mark.parametrize(
    ("verdict", "statuses"),
    [
        ("strong_fit", ["match", "match", "match", "partial"]),
        ("strong_fit", ["match", "match", "match", "mismatch"]),
        ("partial_fit", ["match"] * 4),
        ("partial_fit", ["match", "partial", "mismatch", "match"]),
        ("weak_fit", ["match"] * 4),
        ("weak_fit", ["partial"] * 4),
    ],
)
def test_verdict_that_contradicts_the_delta_statuses_is_rejected(
    verdict: str, statuses: list[str]
) -> None:
    """A11's cross-validator checks only category membership and criterion coverage; the product
    schema is the last guard: all match => strong, any mismatch => weak, otherwise partial."""
    assert not _validator(OUTPUT_SCHEMA_REF).is_valid(_output_with(verdict, statuses))


@pytest.fixture
def app(platform_api_app_factory):
    return platform_api_app_factory(guest_id=GUEST_ID)


def _start(app: Any, request_platform_api, input_payload: dict[str, Any]) -> httpx.Response:
    return asyncio.run(
        request_platform_api(
            app,
            "POST",
            f"/v1/products/task_finder/scenarios/{FIT}/start",
            json={"frontend_id": "web_mirror", "guest_id": GUEST_ID, "input": input_payload},
            request_id="req_task_finder_start",
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
    input_payload: dict[str, Any],
    adapter: FakeProviderAdapter,
) -> tuple[dict[str, Any], dict[str, Any]]:
    started = _start(app, request_platform_api, input_payload).json()
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
            request_id="req_task_finder_session",
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
            request_id="req_task_finder_result",
        )
    )
    assert result.status_code == HTTPStatus.OK
    body = result.json()
    assert body["schema_ref"] == OUTPUT_SCHEMA_REF
    return started, body["output"]


def test_happy_path_composes_the_two_step_result(
    app: Any, request_platform_api, session_factory: SessionFactory
) -> None:
    adapter = RecordingProviderAdapter(FIXTURE_ROOT)
    started, output = _run_to_result(
        app,
        request_platform_api,
        session_factory,
        {"task_text": TASK_TEXT, "freelancer_positioning": PROFILE_TEXT},
        adapter,
    )

    assert tuple(call.action_config_id for call in adapter.calls) == (COMPARE, SCORE)
    assert tuple(call.step_id for call in adapter.calls) == ("compare", "score")
    assert output == _expected_output(TASK_TEXT, PROFILE_TEXT)

    compare_input, score_input = adapter.input_payload(0), adapter.input_payload(1)
    assert compare_input["subject_text"] == PROFILE_TEXT  # the party being judged
    assert compare_input["reference_text"] == TASK_TEXT  # what it is judged against
    assert compare_input["categories"] == ["strong_fit", "partial_fit", "weak_fit"]
    assert [c["id"] for c in compare_input["criteria"]] == CRITERION_IDS
    assert score_input["text_a"] == TASK_TEXT  # A02 scores how well text_b fits text_a
    assert score_input["text_b"] == PROFILE_TEXT
    assert score_input["rubric"] == compare_input["criteria"]
    assert all(c["weight"] > 0 for c in score_input["rubric"])

    # The one next action this product allows is recorded through the generic endpoint.
    response = asyncio.run(
        request_platform_api(
            app,
            "POST",
            f"/v1/scenario-sessions/{started['scenario_session_id']}/next-actions/copy_result",
            json={"checkpoint_id": RESULT_READY_CHECKPOINT_ID},
            request_id="req_task_finder_next_action",
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


def test_weak_input_fixtures_are_reachable_end_to_end(
    app: Any, request_platform_api, session_factory: SessionFactory
) -> None:
    """Weak fixtures are only reachable through the test adapter's variant switch. A vague task
    and profile are a valid low-score result, not a failure."""
    adapter = RecordingProviderAdapter(
        FIXTURE_ROOT, variants={step: ".weak_input" for step in (COMPARE, SCORE)}
    )
    _, output = _run_to_result(
        app,
        request_platform_api,
        session_factory,
        {"task_text": WEAK_TASK_TEXT, "freelancer_positioning": WEAK_PROFILE_TEXT},
        adapter,
    )

    assert output == _expected_output(WEAK_TASK_TEXT, WEAK_PROFILE_TEXT, ".weak_input")
    assert output["comparison"]["verdict"] == "weak_fit"
    assert output["match"]["score"] < WEAK_SCORE_CEILING


@pytest.mark.parametrize(
    "input_payload",
    [
        {"task_text": "", "freelancer_positioning": PROFILE_TEXT},
        {"task_text": " padded ", "freelancer_positioning": PROFILE_TEXT},
        {"task_text": TASK_TEXT},
        {"task_text": TASK_TEXT, "freelancer_positioning": PROFILE_TEXT, "extra": "x"},
    ],
    ids=["empty", "untrimmed", "missing_profile", "extra_field"],
)
def test_invalid_input_fails_the_job_before_any_provider_call(
    app: Any, request_platform_api, session_factory: SessionFactory, input_payload: dict[str, Any]
) -> None:
    started = _start(app, request_platform_api, input_payload).json()

    adapter = RecordingProviderAdapter(FIXTURE_ROOT)
    processed = _run_worker(session_factory, adapter)

    assert processed is not None
    assert processed.status is JobStatus.failed
    assert processed.error_code == "workflow_input_validation_failed"
    assert processed.result_artifact_id is None
    assert adapter.calls == []
    assert _provider_call_count(session_factory, job_id=started["job_id"]) == 0
