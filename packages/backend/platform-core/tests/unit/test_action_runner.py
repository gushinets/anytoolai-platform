from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterator

import pytest
import sqlalchemy as sa
from action_runner import (
    AlwaysFailFakeAdapter,
    CancelledFakeAdapter,
    CompareAndClassifyOutOfCategoriesThenValidAdapter,
    ComposeReplyOverLimitThenValidAdapter,
    CountingFakeAdapter,
    EmptyQuestionsFakeAdapter,
    GapRewritesCountMismatchThenValidAdapter,
    GenericExecutor,
    InvalidStructuredOutputAdapter,
    ScoreMultidimensionalAxesDominantMismatchThenValidAdapter,
    SynthesizeAngleOutOfOptionsThenValidAdapter,
    SynthesizeAngleSecondaryOutOfOptionsThenValidAdapter,
)
from anytoolai_platform_actions.structured_llm.cross_validation import (
    CompareAndClassifyCrossValidator,
    CompareAndClassifyInputValidator,
    ComposeReplyCrossValidator,
    DetectIssuesByTaxonomyCrossValidator,
    ExtractStructuredFieldsCrossValidator,
    ExtractStructuredFieldsInputValidator,
    GapRewritesCrossValidator,
    GenerateClarifyingQuestionsCrossValidator,
    PersuasiveTextCrossValidator,
    ScoreMultidimensionalAxesCrossValidator,
    ScoreMultidimensionalAxesInputValidator,
    SynthesizeAngleCrossValidator,
)
from anytoolai_platform_actions.structured_llm.executor import StructuredLlmActionExecutor
from anytoolai_platform_core.actions.models import ActionRunRecord, ActionRunStatus
from anytoolai_platform_core.actions.repository import ActionRunRepository
from anytoolai_platform_core.actions.runner import (
    ActionInputValidationError,
    ActionRunner,
    ActionRunService,
    _recover_action_events_after_rollback,
    _recover_failed_action_run_row_after_rollback,
)
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.artifacts.service import ArtifactService
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.providers.gateway import (
    ProviderGateway,
    ProviderGatewayExecutionError,
)
from anytoolai_platform_core.providers.models import (
    ProviderCallStatus,
    ProviderRetryHardLimits,
    ProviderValidationRetryPolicy,
)
from anytoolai_platform_core.providers.policies import ProviderPolicyResolver
from anytoolai_platform_core.providers.repository import ProviderCallRepository
from anytoolai_platform_core.storage.db import (
    action_runs_table,
    artifacts_table,
    event_log_table,
    provider_calls_table,
)
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.structured_output.errors import StructuredOutputValidationError

from tests.db_support import provision_database

REPO_ROOT = Path(__file__).resolve().parents[5]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "provider" / "fake_provider_outputs"
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


@pytest.fixture
def session_factory() -> Iterator[sa.orm.sessionmaker[sa.orm.Session]]:
    with provision_database(
        database_name_prefix="anytoolai_action_runner_test",
        skip_reason="PostgreSQL action runner coverage",
    ) as (engine, _alembic_config, _database_url):
        yield build_session_factory(engine)


def _context(
    *,
    step_id: str,
    action_type: str,
    action_config_id: str,
    workflow_version: int | None = 1,
) -> ExecutionContext:
    return ExecutionContext(
        tenant_id="tenant_demo",
        region="eu-central",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_session_id="scenario_session_demo",
        job_id="job_demo",
        workflow_id="kernel_demo.extract_detect_report_v1",
        workflow_version=workflow_version,
        step_id=step_id,
        guest_id="guest_demo",
        user_id="user_demo",
        action_type=action_type,
        action_config_id=action_config_id,
    )


def _event_rows(session: sa.orm.Session) -> list[dict[str, Any]]:
    return list(
        session.execute(
            sa.select(event_log_table).order_by(
                event_log_table.c.timestamp,
                event_log_table.c.event_id,
            )
        ).mappings()
    )


def _event_counts(rows: list[dict[str, Any]]) -> Counter[str]:
    return Counter(str(row["event_type"]) for row in rows)


def _event_by_type(rows: list[dict[str, Any]], event_type: str) -> dict[str, Any]:
    matches = [row for row in rows if row["event_type"] == event_type]
    assert len(matches) == 1
    return matches[0]


def _build_runner(
    session: sa.orm.Session,
    *,
    fake_adapter: Any | None = None,
) -> ActionRunner:
    registry = build_config_registry(CONFIG_ROOT)
    emitter = EventEmitter(EventLogRepository(session))
    artifact_service = ArtifactService(ArtifactRepository(session), emitter)
    gateway = ProviderGateway(
        {"fake": fake_adapter or FakeProviderAdapter(FIXTURE_ROOT)},
        policy_resolver=ProviderPolicyResolver(registry),
        provider_call_repository=ProviderCallRepository(session),
        event_emitter=emitter,
    )
    executor = StructuredLlmActionExecutor(
        config_registry=registry,
        provider_gateway=gateway,
        artifact_service=artifact_service,
        output_cross_validators={
            "text.extract_structured_fields": ExtractStructuredFieldsCrossValidator(),
            "text.detect_issues_by_taxonomy": DetectIssuesByTaxonomyCrossValidator(),
            "text.generate_gap_rewrites": GapRewritesCrossValidator(),
            "text.compose_reply": ComposeReplyCrossValidator(),
            "text.generate_clarifying_questions": GenerateClarifyingQuestionsCrossValidator(),
            "text.synthesize_angle": SynthesizeAngleCrossValidator(),
            "text.compose_persuasive_text": PersuasiveTextCrossValidator(),
            "text.compare_and_classify": CompareAndClassifyCrossValidator(),
            "text.score_multidimensional_axes": ScoreMultidimensionalAxesCrossValidator(),
        },
    )
    return ActionRunner(
        session=session,
        config_registry=registry,
        action_run_service=ActionRunService(ActionRunRepository(session), emitter),
        executors={executor.executor_id: executor},
        artifact_repository=ArtifactRepository(session),
        input_validators={
            "text.extract_structured_fields": ExtractStructuredFieldsInputValidator(),
            "text.compare_and_classify": CompareAndClassifyInputValidator(),
            "text.score_multidimensional_axes": ScoreMultidimensionalAxesInputValidator(),
        },
    )


def test_action_runner_executes_extract_structured_fields_and_persists_context(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session)

        result = asyncio.run(
            runner.run(
                "text.extract_structured_fields",
                "kernel_demo.extract_structured_fields_v1",
                {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS},
                _context(
                    step_id="extract",
                    action_type="text.extract_structured_fields",
                    action_config_id="kernel_demo.extract_structured_fields_v1",
                ),
            )
        )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        artifact = session.execute(sa.select(artifacts_table)).mappings().one()
        provider_call = session.execute(sa.select(provider_calls_table)).mappings().one()
        events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert result.output_payload == {
        "values": {
            "deadline": "next Friday",
            "budget": "$5,000",
            "deliverables": ["logo", "landing page"],
        },
        "missing_fields": [],
        "confidence": {"deadline": 0.9, "budget": 0.8, "deliverables": 0.7},
    }
    assert result.output_artifact_id == artifact["id"]
    assert action_run["status"].value == "succeeded"
    assert action_run["output_artifact_id"] == artifact["id"]
    assert action_run["metadata"]["workflow_version"] == 1
    assert action_run["metadata"]["guest_id"] == "guest_demo"
    assert action_run["metadata"]["user_id"] == "user_demo"
    assert artifact["action_run_id"] == action_run["id"]
    assert artifact["metadata"]["schema_ref"] == "kernel.schemas.extract_output_v1"
    assert provider_call["action_run_id"] == action_run["id"]
    assert provider_call["workflow_version"] == 1
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 1,
            "provider.request_succeeded": 1,
            "artifact.created": 1,
            "action.succeeded": 1,
        }
    )
    assert all(row["tenant_id"] == "tenant_demo" for row in events)
    assert all(row["region"] == "eu-central" for row in events)
    action_started = _event_by_type(events, "action.started")
    provider_started = _event_by_type(events, "provider.request_started")
    provider_succeeded = _event_by_type(events, "provider.request_succeeded")
    artifact_created = _event_by_type(events, "artifact.created")
    action_succeeded = _event_by_type(events, "action.succeeded")
    assert action_started["guest_id"] == "guest_demo"
    assert action_started["user_id"] == "user_demo"
    assert action_started["workflow_version"] == 1
    assert action_started["action_run_id"] == action_run["id"]
    assert provider_started["provider_policy_ref"] == "default_fake_provider_v1"
    assert provider_started["provider_call_id"] == provider_call["id"]
    assert provider_started["action_run_id"] == action_run["id"]
    assert provider_succeeded["provider_call_id"] == provider_call["id"]
    assert provider_succeeded["action_run_id"] == action_run["id"]
    assert artifact_created["artifact_id"] == artifact["id"]
    assert artifact_created["action_run_id"] == action_run["id"]
    assert action_succeeded["action_run_id"] == action_run["id"]


def test_action_runner_executes_detect_issues_atom_through_generic_path(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session)

        result = asyncio.run(
            runner.run(
                "text.detect_issues_by_taxonomy",
                "kernel_demo.detect_issues_v1",
                {
                    "source_text": "We need this soon.",
                    "taxonomy": ["timeline", "scope", "requirements"],
                },
                _context(
                    step_id="detect_issues",
                    action_type="text.detect_issues_by_taxonomy",
                    action_config_id="kernel_demo.detect_issues_v1",
                ),
            )
        )

    assert result.status.value == "succeeded"
    assert result.output_payload == {
        "issues": [
            {
                "category": "timeline",
                "description": "Timeline is underspecified",
                "severity": "high",
                "evidence": "We need this soon.",
            }
        ]
    }


def test_action_runner_executes_generate_clarifying_questions_from_a04_issue_artifact(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    """Feeds the finalized A04 `issue_detection_output` shape (category/description/severity)
    straight into A05's `issues` input, proving the direct workflow mapping the ticket requires
    without any adapter step in between."""
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session)

        result = asyncio.run(
            runner.run(
                "text.generate_clarifying_questions",
                "kernel_demo.generate_clarifying_questions_v1",
                {
                    "issues": [
                        {
                            "category": "timeline",
                            "description": "Delivery date not specified",
                            "severity": "high",
                            "evidence": "We need this soon.",
                        },
                        {
                            "category": "scope",
                            "description": "Deliverables list is incomplete",
                            "severity": "medium",
                        },
                    ],
                    "context": "Client project kickoff conversation.",
                    "target_audience": "client stakeholder",
                },
                _context(
                    step_id="generate_clarifying_questions",
                    action_type="text.generate_clarifying_questions",
                    action_config_id="kernel_demo.generate_clarifying_questions_v1",
                ),
            )
        )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        artifact = session.execute(sa.select(artifacts_table)).mappings().one()
        provider_call = session.execute(sa.select(provider_calls_table)).mappings().one()
        events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert result.output_payload == {
        "questions": [
            {
                "question": "What is the exact delivery date the client is expecting?",
                "rationale": "The timeline issue has no concrete date to plan around.",
                "priority": "high",
                "category": "timeline",
                "source_issue_index": 0,
            },
        ]
    }
    assert result.output_artifact_id == artifact["id"]
    assert action_run["status"].value == "succeeded"
    assert action_run["output_artifact_id"] == artifact["id"]
    assert artifact["action_run_id"] == action_run["id"]
    assert artifact["metadata"]["schema_ref"] == "kernel.schemas.generate_questions_output_v1"
    assert provider_call["action_run_id"] == action_run["id"]
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 1,
            "provider.request_succeeded": 1,
            "artifact.created": 1,
            "action.succeeded": 1,
        }
    )
    action_started = _event_by_type(events, "action.started")
    artifact_created = _event_by_type(events, "artifact.created")
    action_succeeded = _event_by_type(events, "action.succeeded")
    assert action_started["action_run_id"] == action_run["id"]
    assert artifact_created["artifact_id"] == artifact["id"]
    assert action_succeeded["action_run_id"] == action_run["id"]


def test_action_runner_executes_generate_clarifying_questions_with_empty_output_when_no_issue_is_actionable(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    """Ticket-required successful empty-output behavior: when no supplied issue is
    actionable, `questions: []` must go through the real fake-provider/ActionRunner path as a
    succeeded run with full artifact/event lineage, not just pass schema/cross-validator unit
    checks in isolation."""
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session, fake_adapter=EmptyQuestionsFakeAdapter())

        result = asyncio.run(
            runner.run(
                "text.generate_clarifying_questions",
                "kernel_demo.generate_clarifying_questions_v1",
                {
                    "issues": [
                        {
                            "category": "context",
                            "description": "Purely informational note, nothing to resolve.",
                            "severity": "low",
                        }
                    ],
                    "context": "Client project kickoff conversation.",
                    "target_audience": "client stakeholder",
                },
                _context(
                    step_id="generate_clarifying_questions",
                    action_type="text.generate_clarifying_questions",
                    action_config_id="kernel_demo.generate_clarifying_questions_v1",
                ),
            )
        )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        artifact = session.execute(sa.select(artifacts_table)).mappings().one()
        provider_call = session.execute(sa.select(provider_calls_table)).mappings().one()
        events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert result.output_payload == {"questions": []}
    assert result.output_artifact_id == artifact["id"]
    assert action_run["status"].value == "succeeded"
    assert action_run["output_artifact_id"] == artifact["id"]
    assert artifact["action_run_id"] == action_run["id"]
    assert artifact["metadata"]["schema_ref"] == "kernel.schemas.generate_questions_output_v1"
    assert provider_call["action_run_id"] == action_run["id"]
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 1,
            "provider.request_succeeded": 1,
            "artifact.created": 1,
            "action.succeeded": 1,
        }
    )
    action_started = _event_by_type(events, "action.started")
    artifact_created = _event_by_type(events, "artifact.created")
    action_succeeded = _event_by_type(events, "action.succeeded")
    assert action_started["action_run_id"] == action_run["id"]
    assert artifact_created["artifact_id"] == artifact["id"]
    assert action_succeeded["action_run_id"] == action_run["id"]


def test_action_runner_executes_generate_document_atom_and_persists_event_lineage(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session)

        result = asyncio.run(
            runner.run(
                "document.generate_from_template",
                "kernel_demo.generate_report_v1",
                {
                    "template_ref": "kernel_demo.report_v1",
                    "data": {
                        "source_text": "deadline budget deliverables",
                        "extracted": {"values": {"deadline": "next Friday"}, "missing_fields": []},
                        "issues": {"issues": []},
                    },
                },
                _context(
                    step_id="generate_report",
                    action_type="document.generate_from_template",
                    action_config_id="kernel_demo.generate_report_v1",
                ),
            )
        )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        artifact = session.execute(sa.select(artifacts_table)).mappings().one()
        provider_call = session.execute(sa.select(provider_calls_table)).mappings().one()
        events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert result.output_payload == {
        "sections": [
            {
                "id": "overview",
                "title": "Overview",
                "content": "The project is on track with a deadline of next Friday and a budget of $5,000.",
            },
            {
                "id": "risks",
                "title": "Risks",
                "content": (
                    "Timeline is underspecified: the requester says the work is needed soon "
                    "without a firm date."
                ),
                "metadata": {"kind": "note"},
            },
        ],
        "summary": "Scope and budget are set, but the timeline needs to be confirmed before work starts.",
    }
    assert result.output_artifact_id == artifact["id"]
    assert action_run["status"].value == "succeeded"
    assert action_run["output_artifact_id"] == artifact["id"]
    assert artifact["action_run_id"] == action_run["id"]
    assert artifact["metadata"]["schema_ref"] == "kernel.schemas.generate_document_output_v1"
    assert provider_call["action_run_id"] == action_run["id"]
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 1,
            "provider.request_succeeded": 1,
            "artifact.created": 1,
            "action.succeeded": 1,
        }
    )
    action_started = _event_by_type(events, "action.started")
    artifact_created = _event_by_type(events, "artifact.created")
    action_succeeded = _event_by_type(events, "action.succeeded")
    assert action_started["action_run_id"] == action_run["id"]
    assert artifact_created["artifact_id"] == artifact["id"]
    assert action_succeeded["action_run_id"] == action_run["id"]


def test_action_runner_executes_compose_persuasive_text_atom_and_persists_event_lineage(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session)

        result = asyncio.run(
            runner.run(
                "text.compose_persuasive_text",
                "kernel_demo.compose_persuasive_text_v1",
                {
                    "context": {"product": "Widget Pro", "deadline": "March"},
                    "objective": "Convince the reader to upgrade before March.",
                },
                _context(
                    step_id="compose_persuasive_text",
                    action_type="text.compose_persuasive_text",
                    action_config_id="kernel_demo.compose_persuasive_text_v1",
                ),
            )
        )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        artifact = session.execute(sa.select(artifacts_table)).mappings().one()
        provider_call = session.execute(sa.select(provider_calls_table)).mappings().one()
        events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert result.output_payload == {
        "text": (
            "Upgrading to Widget Pro now keeps you ahead of the March deadline you "
            "flagged, so don't wait to make the move."
        ),
    }
    assert result.output_artifact_id == artifact["id"]
    assert action_run["status"].value == "succeeded"
    assert action_run["output_artifact_id"] == artifact["id"]
    assert artifact["action_run_id"] == action_run["id"]
    assert artifact["metadata"]["schema_ref"] == "kernel.schemas.compose_persuasive_text_output_v1"
    assert provider_call["action_run_id"] == action_run["id"]
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 1,
            "provider.request_succeeded": 1,
            "artifact.created": 1,
            "action.succeeded": 1,
        }
    )
    action_started = _event_by_type(events, "action.started")
    artifact_created = _event_by_type(events, "artifact.created")
    action_succeeded = _event_by_type(events, "action.succeeded")
    assert action_started["action_run_id"] == action_run["id"]
    assert artifact_created["artifact_id"] == artifact["id"]
    assert action_succeeded["action_run_id"] == action_run["id"]


def test_action_runner_executes_synthesize_angle_atom_through_generic_path(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session)

        result = asyncio.run(
            runner.run(
                "text.synthesize_angle",
                "kernel_demo.synthesize_angle_v1",
                {
                    "signals": [
                        {
                            "id": "timeline_gap",
                            "label": "Timeline gap",
                            "value": "unconfirmed deadline",
                            "evidence": "We haven't heard back on dates.",
                        }
                    ],
                    "objective": "Win the deal",
                    "options": [
                        "Lead with the timeline risk to create urgency",
                        "Anchor on budget flexibility as a fallback",
                    ],
                },
                _context(
                    step_id="synthesize_angle",
                    action_type="text.synthesize_angle",
                    action_config_id="kernel_demo.synthesize_angle_v1",
                ),
            )
        )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        artifact = session.execute(sa.select(artifacts_table)).mappings().one()
        provider_call = session.execute(sa.select(provider_calls_table)).mappings().one()
        events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert result.output_payload == {
        "angle": "Lead with the timeline risk to create urgency",
        "rationale": (
            "Signal timeline_gap shows the deadline is unconfirmed, which directly "
            "threatens the objective; surfacing it first motivates fast action."
        ),
        "secondary_angle": "Anchor on budget flexibility as a fallback",
    }
    assert result.output_artifact_id == artifact["id"]
    assert action_run["status"].value == "succeeded"
    assert action_run["output_artifact_id"] == artifact["id"]
    assert artifact["action_run_id"] == action_run["id"]
    assert artifact["metadata"]["schema_ref"] == "kernel.schemas.synthesize_angle_output_v1"
    assert provider_call["action_run_id"] == action_run["id"]
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 1,
            "provider.request_succeeded": 1,
            "artifact.created": 1,
            "action.succeeded": 1,
        }
    )
    action_started = _event_by_type(events, "action.started")
    artifact_created = _event_by_type(events, "artifact.created")
    action_succeeded = _event_by_type(events, "action.succeeded")
    assert action_started["action_run_id"] == action_run["id"]
    assert artifact_created["artifact_id"] == artifact["id"]
    assert action_succeeded["action_run_id"] == action_run["id"]


def test_action_runner_retries_synthesize_angle_cross_validation_through_real_ledger(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    """A09: proves the options-membership cross-validation retry through the real
    ProviderGateway/ActionRunner path (not an in-memory spy) - an out-of-options angle
    followed by success must create two physical provider_calls rows with the expected
    semantic/physical indexes, provider events, and final artifact lineage."""
    adapter = SynthesizeAngleOutOfOptionsThenValidAdapter()
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session, fake_adapter=adapter)
        # default_fake_provider_v1 allows 1 validation attempt / 1 physical call per action;
        # widen both so the semantic retry this test drives can actually reach a 2nd
        # physical call through the real ProviderGateway hard-limit check, not just PydanticAI.
        executor = runner._executors["structured_llm"]
        base_policy = executor._require_provider_policy("default_fake_provider_v1")
        patched_policy = replace(
            base_policy,
            retry_policy=replace(
                base_policy.retry_policy,
                validation=ProviderValidationRetryPolicy(
                    owner=base_policy.retry_policy.validation.owner,
                    max_attempts=2,
                ),
                hard_limits=ProviderRetryHardLimits(max_physical_provider_calls_per_action=2),
            ),
        )
        executor._require_provider_policy = lambda _provider_policy_ref: patched_policy
        executor._provider_gateway._policy_resolver.resolve = lambda _provider_policy_ref: patched_policy

        result = asyncio.run(
            runner.run(
                "text.synthesize_angle",
                "kernel_demo.synthesize_angle_v1",
                {
                    "signals": [{"id": "s1", "label": "Timeline gap", "value": "unconfirmed"}],
                    "objective": "Win the deal",
                    "options": ["Lead with urgency"],
                },
                _context(
                    step_id="synthesize_angle",
                    action_type="text.synthesize_angle",
                    action_config_id="kernel_demo.synthesize_angle_v1",
                ),
            )
        )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        artifact = session.execute(sa.select(artifacts_table)).mappings().one()
        provider_calls = list(
            session.execute(
                sa.select(provider_calls_table).order_by(
                    provider_calls_table.c.created_at, provider_calls_table.c.id
                )
            ).mappings()
        )
        events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert result.output_payload == {"angle": "Lead with urgency", "rationale": "r"}
    assert result.output_artifact_id == artifact["id"]
    assert adapter.call_count == 2
    assert len(provider_calls) == 2
    assert [row["semantic_attempt_index"] for row in provider_calls] == [1, 2]
    # physical_call_index tracks the action-wide physical-call budget, not a per-semantic-
    # attempt counter, so it keeps climbing across semantic attempts too.
    assert [row["physical_call_index"] for row in provider_calls] == [1, 2]
    assert all(row["action_run_id"] == action_run["id"] for row in provider_calls)
    assert action_run["status"].value == "succeeded"
    assert action_run["output_artifact_id"] == artifact["id"]
    assert artifact["action_run_id"] == action_run["id"]
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 2,
            "provider.request_succeeded": 2,
            "artifact.created": 1,
            "action.succeeded": 1,
        }
    )
    artifact_created = _event_by_type(events, "artifact.created")
    assert artifact_created["artifact_id"] == artifact["id"]


def test_action_runner_retries_synthesize_angle_secondary_cross_validation_through_real_ledger(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    """A09: proves the options-membership cross-validation retry for `secondary_angle`
    (not just `angle`) through the real ProviderGateway/ActionRunner path - a valid `angle`
    paired with an out-of-options `secondary_angle` followed by a fully valid reply must
    create two physical provider_calls rows with the expected semantic/physical indexes,
    provider events, and final artifact lineage."""
    adapter = SynthesizeAngleSecondaryOutOfOptionsThenValidAdapter()
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session, fake_adapter=adapter)
        # default_fake_provider_v1 allows 1 validation attempt / 1 physical call per action;
        # widen both so the semantic retry this test drives can actually reach a 2nd
        # physical call through the real ProviderGateway hard-limit check, not just PydanticAI.
        executor = runner._executors["structured_llm"]
        base_policy = executor._require_provider_policy("default_fake_provider_v1")
        patched_policy = replace(
            base_policy,
            retry_policy=replace(
                base_policy.retry_policy,
                validation=ProviderValidationRetryPolicy(
                    owner=base_policy.retry_policy.validation.owner,
                    max_attempts=2,
                ),
                hard_limits=ProviderRetryHardLimits(max_physical_provider_calls_per_action=2),
            ),
        )
        executor._require_provider_policy = lambda _provider_policy_ref: patched_policy
        executor._provider_gateway._policy_resolver.resolve = lambda _provider_policy_ref: patched_policy

        result = asyncio.run(
            runner.run(
                "text.synthesize_angle",
                "kernel_demo.synthesize_angle_v1",
                {
                    "signals": [{"id": "s1", "label": "Timeline gap", "value": "unconfirmed"}],
                    "objective": "Win the deal",
                    "options": ["Lead with urgency", "Anchor on budget"],
                },
                _context(
                    step_id="synthesize_angle",
                    action_type="text.synthesize_angle",
                    action_config_id="kernel_demo.synthesize_angle_v1",
                ),
            )
        )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        artifact = session.execute(sa.select(artifacts_table)).mappings().one()
        provider_calls = list(
            session.execute(
                sa.select(provider_calls_table).order_by(
                    provider_calls_table.c.created_at, provider_calls_table.c.id
                )
            ).mappings()
        )
        events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert result.output_payload == {
        "angle": "Lead with urgency",
        "rationale": "r",
        "secondary_angle": "Anchor on budget",
    }
    assert result.output_artifact_id == artifact["id"]
    assert adapter.call_count == 2
    assert len(provider_calls) == 2
    assert [row["semantic_attempt_index"] for row in provider_calls] == [1, 2]
    # physical_call_index tracks the action-wide physical-call budget, not a per-semantic-
    # attempt counter, so it keeps climbing across semantic attempts too.
    assert [row["physical_call_index"] for row in provider_calls] == [1, 2]
    assert all(row["action_run_id"] == action_run["id"] for row in provider_calls)
    assert action_run["status"].value == "succeeded"
    assert action_run["output_artifact_id"] == artifact["id"]
    assert artifact["action_run_id"] == action_run["id"]
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 2,
            "provider.request_succeeded": 2,
            "artifact.created": 1,
            "action.succeeded": 1,
        }
    )
    artifact_created = _event_by_type(events, "artifact.created")
    assert artifact_created["artifact_id"] == artifact["id"]


def test_action_runner_executes_generate_gap_rewrites_atom_and_persists_event_lineage(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session)

        result = asyncio.run(
            runner.run(
                "text.generate_gap_rewrites",
                "kernel_demo.generate_gap_rewrites_v1",
                {
                    "source_text": "We will deliver the project soon.",
                    "gap": "No concrete delivery date is given.",
                    "style": "moderate",
                },
                _context(
                    step_id="generate_gap_rewrites",
                    action_type="text.generate_gap_rewrites",
                    action_config_id="kernel_demo.generate_gap_rewrites_v1",
                ),
            )
        )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        artifact = session.execute(sa.select(artifacts_table)).mappings().one()
        provider_call = session.execute(sa.select(provider_calls_table)).mappings().one()
        events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert result.output_payload == {
        "rewrites": [
            {
                "text": "The proposal includes a fixed delivery date of March 15.",
                "explanation": (
                    "States a concrete delivery date to close the timeline gap directly."
                ),
                "change_made": "Added an explicit delivery date.",
            },
            {
                "text": (
                    "Delivery is targeted for mid-March, with the final date confirmed "
                    "within one week."
                ),
                "explanation": (
                    "Commits to a narrow window while flagging when the exact date follows."
                ),
                "change_made": "Added a target window and a confirmation deadline.",
            },
            {
                "text": (
                    "We will deliver by March 15, guaranteed, or issue a full refund for "
                    "the delay."
                ),
                "explanation": (
                    "Backs the delivery date with a guarantee, removing any timeline "
                    "ambiguity."
                ),
                "change_made": "Added a delivery date plus a guarantee clause.",
            },
        ],
        "best_pick": 2,
    }
    assert result.output_artifact_id == artifact["id"]
    assert action_run["status"].value == "succeeded"
    assert action_run["output_artifact_id"] == artifact["id"]
    assert artifact["action_run_id"] == action_run["id"]
    assert artifact["metadata"]["schema_ref"] == "kernel.schemas.generate_gap_rewrites_output_v1"
    assert provider_call["action_run_id"] == action_run["id"]
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 1,
            "provider.request_succeeded": 1,
            "artifact.created": 1,
            "action.succeeded": 1,
        }
    )
    action_started = _event_by_type(events, "action.started")
    artifact_created = _event_by_type(events, "artifact.created")
    action_succeeded = _event_by_type(events, "action.succeeded")
    assert action_started["action_run_id"] == action_run["id"]
    assert artifact_created["artifact_id"] == artifact["id"]
    assert action_succeeded["action_run_id"] == action_run["id"]


def test_action_runner_generate_gap_rewrites_fails_safely_for_non_default_n(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    """A08: the kernel_demo fake-provider fixture always returns 3 rewrites (the schema's
    declared default n), and no action_config/workflow pins n=3 — a caller is free to request
    any n in the schema's 1-5 range. Against the demo fixture, any n other than 3 is
    unsatisfiable, and default_fake_provider_v1 allows exactly 1 physical call
    (hard_limits.max_physical_provider_calls_per_action: 1), so this must surface as a single
    clean, safe StructuredOutputValidationError — the "define validation failure rather than
    silently returning fewer alternatives" contract requirement — not a silent success, a
    retry hang, or an unhandled crash."""
    counting_adapter = CountingFakeAdapter(FakeProviderAdapter(FIXTURE_ROOT))
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session, fake_adapter=counting_adapter)

        with pytest.raises(StructuredOutputValidationError) as exc_info:
            asyncio.run(
                runner.run(
                    "text.generate_gap_rewrites",
                    "kernel_demo.generate_gap_rewrites_v1",
                    {
                        "source_text": "We will deliver the project soon.",
                        "gap": "No concrete delivery date is given.",
                        "n": 2,
                        "style": "moderate",
                    },
                    _context(
                        step_id="generate_gap_rewrites",
                        action_type="text.generate_gap_rewrites",
                        action_config_id="kernel_demo.generate_gap_rewrites_v1",
                    ),
                )
            )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()

    assert exc_info.value.code == "structured_output_validation_failed"
    assert exc_info.value.reason == "rewrite_count_mismatch:3!=2"
    assert action_run["status"].value == "failed"
    assert counting_adapter.call_count == 1


def test_action_runner_retries_generate_gap_rewrites_cross_validation_through_real_ledger(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    """A08: proves the rewrite-count cross-validation retry through the real
    ProviderGateway/ActionRunner path (not an in-memory spy) - a rewrite-count mismatch
    followed by a matching-count success must create two physical provider_calls rows with
    the expected semantic/physical indexes, provider events, and final artifact lineage."""
    adapter = GapRewritesCountMismatchThenValidAdapter()
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session, fake_adapter=adapter)
        # default_fake_provider_v1 allows 1 validation attempt / 1 physical call per action;
        # widen both so the semantic retry this test drives can actually reach a 2nd
        # physical call through the real ProviderGateway hard-limit check, not just PydanticAI.
        executor = runner._executors["structured_llm"]
        base_policy = executor._require_provider_policy("default_fake_provider_v1")
        patched_policy = replace(
            base_policy,
            retry_policy=replace(
                base_policy.retry_policy,
                validation=ProviderValidationRetryPolicy(
                    owner=base_policy.retry_policy.validation.owner,
                    max_attempts=2,
                ),
                hard_limits=ProviderRetryHardLimits(max_physical_provider_calls_per_action=2),
            ),
        )
        executor._require_provider_policy = lambda _provider_policy_ref: patched_policy
        executor._provider_gateway._policy_resolver.resolve = lambda _provider_policy_ref: patched_policy

        result = asyncio.run(
            runner.run(
                "text.generate_gap_rewrites",
                "kernel_demo.generate_gap_rewrites_v1",
                {
                    "source_text": "We will deliver the project soon.",
                    "gap": "No concrete delivery date is given.",
                    "n": 2,
                    "style": "moderate",
                },
                _context(
                    step_id="generate_gap_rewrites",
                    action_type="text.generate_gap_rewrites",
                    action_config_id="kernel_demo.generate_gap_rewrites_v1",
                ),
            )
        )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        artifact = session.execute(sa.select(artifacts_table)).mappings().one()
        provider_calls = list(
            session.execute(
                sa.select(provider_calls_table).order_by(
                    provider_calls_table.c.created_at, provider_calls_table.c.id
                )
            ).mappings()
        )
        events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert result.output_payload == {
        "rewrites": [
            {"text": "First rewrite.", "explanation": "e", "change_made": "c"},
            {"text": "Second rewrite.", "explanation": "e", "change_made": "c"},
        ],
        "best_pick": 1,
    }
    assert result.output_artifact_id == artifact["id"]
    assert adapter.call_count == 2
    assert len(provider_calls) == 2
    assert [row["semantic_attempt_index"] for row in provider_calls] == [1, 2]
    # physical_call_index tracks the action-wide physical-call budget, not a per-semantic-
    # attempt counter, so it keeps climbing across semantic attempts too.
    assert [row["physical_call_index"] for row in provider_calls] == [1, 2]
    assert all(row["action_run_id"] == action_run["id"] for row in provider_calls)
    assert action_run["status"].value == "succeeded"
    assert action_run["output_artifact_id"] == artifact["id"]
    assert artifact["action_run_id"] == action_run["id"]
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 2,
            "provider.request_succeeded": 2,
            "artifact.created": 1,
            "action.succeeded": 1,
        }
    )
    artifact_created = _event_by_type(events, "artifact.created")
    assert artifact_created["artifact_id"] == artifact["id"]


def test_action_runner_executes_compose_reply_atom_and_persists_event_lineage(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session)

        result = asyncio.run(
            runner.run(
                "text.compose_reply",
                "kernel_demo.compose_reply_v1",
                {
                    "situation": "The client asked for a status update on the project.",
                    "intent": "Reassure the client and confirm the new delivery date.",
                    "tone": "warm",
                },
                _context(
                    step_id="compose_reply",
                    action_type="text.compose_reply",
                    action_config_id="kernel_demo.compose_reply_v1",
                ),
            )
        )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        artifact = session.execute(sa.select(artifacts_table)).mappings().one()
        provider_call = session.execute(sa.select(provider_calls_table)).mappings().one()
        events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert result.output_payload == {
        "text": (
            "Thanks for flagging the delay. I've adjusted the schedule and the revised "
            "draft will be with you by Friday."
        ),
        "call_to_action": "Let me know by Wednesday if Friday doesn't work for you.",
    }
    assert result.output_artifact_id == artifact["id"]
    assert action_run["status"].value == "succeeded"
    assert action_run["output_artifact_id"] == artifact["id"]
    assert artifact["action_run_id"] == action_run["id"]
    assert artifact["metadata"]["schema_ref"] == "kernel.schemas.compose_reply_output_v1"
    assert provider_call["action_run_id"] == action_run["id"]
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 1,
            "provider.request_succeeded": 1,
            "artifact.created": 1,
            "action.succeeded": 1,
        }
    )
    action_started = _event_by_type(events, "action.started")
    artifact_created = _event_by_type(events, "artifact.created")
    action_succeeded = _event_by_type(events, "action.succeeded")
    assert action_started["action_run_id"] == action_run["id"]
    assert artifact_created["artifact_id"] == artifact["id"]
    assert action_succeeded["action_run_id"] == action_run["id"]


def test_action_runner_retries_compose_reply_cross_validation_through_real_ledger(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    """A07: proves the constraints.max_length cross-validation retry through the real
    ProviderGateway/ActionRunner path (not an in-memory spy) - a max_length failure
    followed by success must create two physical provider_calls rows with the expected
    semantic/physical indexes, provider events, and final artifact lineage."""
    adapter = ComposeReplyOverLimitThenValidAdapter()
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session, fake_adapter=adapter)
        # default_fake_provider_v1 allows 1 validation attempt / 1 physical call per action;
        # widen both so the semantic retry this test drives can actually reach a 2nd
        # physical call through the real ProviderGateway hard-limit check, not just PydanticAI.
        executor = runner._executors["structured_llm"]
        base_policy = executor._require_provider_policy("default_fake_provider_v1")
        patched_policy = replace(
            base_policy,
            retry_policy=replace(
                base_policy.retry_policy,
                validation=ProviderValidationRetryPolicy(
                    owner=base_policy.retry_policy.validation.owner,
                    max_attempts=2,
                ),
                hard_limits=ProviderRetryHardLimits(max_physical_provider_calls_per_action=2),
            ),
        )
        executor._require_provider_policy = lambda _provider_policy_ref: patched_policy
        executor._provider_gateway._policy_resolver.resolve = lambda _provider_policy_ref: patched_policy

        result = asyncio.run(
            runner.run(
                "text.compose_reply",
                "kernel_demo.compose_reply_v1",
                {
                    "situation": "The client asked for a status update on the project.",
                    "intent": "Reassure the client and confirm the new delivery date.",
                    "tone": "warm",
                    "constraints": {"max_length": 10},
                },
                _context(
                    step_id="compose_reply",
                    action_type="text.compose_reply",
                    action_config_id="kernel_demo.compose_reply_v1",
                ),
            )
        )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        artifact = session.execute(sa.select(artifacts_table)).mappings().one()
        provider_calls = list(
            session.execute(
                sa.select(provider_calls_table).order_by(
                    provider_calls_table.c.created_at, provider_calls_table.c.id
                )
            ).mappings()
        )
        events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert result.output_payload == {"text": "Short."}
    assert result.output_artifact_id == artifact["id"]
    assert adapter.call_count == 2
    assert len(provider_calls) == 2
    assert [row["semantic_attempt_index"] for row in provider_calls] == [1, 2]
    # physical_call_index tracks the action-wide physical-call budget, not a per-semantic-
    # attempt counter, so it keeps climbing across semantic attempts too.
    assert [row["physical_call_index"] for row in provider_calls] == [1, 2]
    assert all(row["action_run_id"] == action_run["id"] for row in provider_calls)
    assert action_run["status"].value == "succeeded"
    assert action_run["output_artifact_id"] == artifact["id"]
    assert artifact["action_run_id"] == action_run["id"]
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 2,
            "provider.request_succeeded": 2,
            "artifact.created": 1,
            "action.succeeded": 1,
        }
    )
    artifact_created = _event_by_type(events, "artifact.created")
    assert artifact_created["artifact_id"] == artifact["id"]


def test_action_runner_executes_compare_and_classify_atom_through_generic_path(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session)

        result = asyncio.run(
            runner.run(
                "text.compare_and_classify",
                "kernel_demo.compare_and_classify_v1",
                {
                    "subject_text": "Subject copy",
                    "reference_text": "Reference copy",
                    "categories": ["meets_bar", "below_bar"],
                    "criteria": [
                        {"id": "tone", "description": "Matches the reference tone."},
                        {"id": "coverage", "description": "Covers the required topics."},
                    ],
                },
                _context(
                    step_id="compare_and_classify",
                    action_type="text.compare_and_classify",
                    action_config_id="kernel_demo.compare_and_classify_v1",
                ),
            )
        )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        artifact = session.execute(sa.select(artifacts_table)).mappings().one()
        provider_call = session.execute(sa.select(provider_calls_table)).mappings().one()
        events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert result.output_payload == {
        "verdict": "meets_bar",
        "confidence": 0.82,
        "deltas": [
            {
                "criterion_id": "tone",
                "status": "match",
                "evidence": "Subject uses the same professional, direct tone as the reference.",
            },
            {
                "criterion_id": "coverage",
                "status": "partial",
                "evidence": "Subject omits the pricing section that the reference includes.",
            },
        ],
        "rationale": (
            "Subject matches the reference on tone and mostly covers the required topics, "
            "missing only pricing, which is enough to meet the bar."
        ),
    }
    assert result.output_artifact_id == artifact["id"]
    assert action_run["status"].value == "succeeded"
    assert action_run["output_artifact_id"] == artifact["id"]
    assert artifact["action_run_id"] == action_run["id"]
    assert artifact["metadata"]["schema_ref"] == "kernel.schemas.compare_classify_output_v1"
    assert provider_call["action_run_id"] == action_run["id"]
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 1,
            "provider.request_succeeded": 1,
            "artifact.created": 1,
            "action.succeeded": 1,
        }
    )
    action_started = _event_by_type(events, "action.started")
    artifact_created = _event_by_type(events, "artifact.created")
    action_succeeded = _event_by_type(events, "action.succeeded")
    assert action_started["action_run_id"] == action_run["id"]
    assert artifact_created["artifact_id"] == artifact["id"]
    assert action_succeeded["action_run_id"] == action_run["id"]


def test_action_runner_retries_compare_and_classify_cross_validation_through_real_ledger(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    """A11: proves the categories-membership cross-validation retry through the real
    ProviderGateway/ActionRunner path (not an in-memory spy) - an out-of-categories verdict
    followed by success must create two physical provider_calls rows with the expected
    semantic/physical indexes, provider events, and final artifact lineage."""
    adapter = CompareAndClassifyOutOfCategoriesThenValidAdapter()
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session, fake_adapter=adapter)
        # default_fake_provider_v1 allows 1 validation attempt / 1 physical call per action;
        # widen both so the semantic retry this test drives can actually reach a 2nd
        # physical call through the real ProviderGateway hard-limit check, not just PydanticAI.
        executor = runner._executors["structured_llm"]
        base_policy = executor._require_provider_policy("default_fake_provider_v1")
        patched_policy = replace(
            base_policy,
            retry_policy=replace(
                base_policy.retry_policy,
                validation=ProviderValidationRetryPolicy(
                    owner=base_policy.retry_policy.validation.owner,
                    max_attempts=2,
                ),
                hard_limits=ProviderRetryHardLimits(max_physical_provider_calls_per_action=2),
            ),
        )
        executor._require_provider_policy = lambda _provider_policy_ref: patched_policy
        executor._provider_gateway._policy_resolver.resolve = lambda _provider_policy_ref: patched_policy

        result = asyncio.run(
            runner.run(
                "text.compare_and_classify",
                "kernel_demo.compare_and_classify_v1",
                {
                    "subject_text": "Subject copy",
                    "reference_text": "Reference copy",
                    "categories": ["meets_bar", "below_bar"],
                    "criteria": [{"id": "tone", "description": "Matches the reference tone."}],
                },
                _context(
                    step_id="compare_and_classify",
                    action_type="text.compare_and_classify",
                    action_config_id="kernel_demo.compare_and_classify_v1",
                ),
            )
        )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        artifact = session.execute(sa.select(artifacts_table)).mappings().one()
        provider_calls = list(
            session.execute(
                sa.select(provider_calls_table).order_by(
                    provider_calls_table.c.created_at, provider_calls_table.c.id
                )
            ).mappings()
        )
        events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert result.output_payload == {
        "verdict": "meets_bar",
        "confidence": 0.7,
        "deltas": [{"criterion_id": "tone", "status": "match", "evidence": "e"}],
        "rationale": "r",
    }
    assert result.output_artifact_id == artifact["id"]
    assert adapter.call_count == 2
    assert len(provider_calls) == 2
    assert [row["semantic_attempt_index"] for row in provider_calls] == [1, 2]
    # physical_call_index tracks the action-wide physical-call budget, not a per-semantic-
    # attempt counter, so it keeps climbing across semantic attempts too.
    assert [row["physical_call_index"] for row in provider_calls] == [1, 2]
    assert all(row["action_run_id"] == action_run["id"] for row in provider_calls)
    assert action_run["status"].value == "succeeded"
    assert action_run["output_artifact_id"] == artifact["id"]
    assert artifact["action_run_id"] == action_run["id"]
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 2,
            "provider.request_succeeded": 2,
            "artifact.created": 1,
            "action.succeeded": 1,
        }
    )
    artifact_created = _event_by_type(events, "artifact.created")
    assert artifact_created["artifact_id"] == artifact["id"]


def test_action_runner_marks_failed_on_provider_failure(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session, fake_adapter=AlwaysFailFakeAdapter())

        with pytest.raises(ProviderGatewayExecutionError) as exc_info:
            asyncio.run(
                runner.run(
                    "text.extract_structured_fields",
                    "kernel_demo.extract_structured_fields_v1",
                    {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS},
                    _context(
                        step_id="extract",
                        action_type="text.extract_structured_fields",
                        action_config_id="kernel_demo.extract_structured_fields_v1",
                    ),
                )
            )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        events = _event_rows(session)

    assert exc_info.value.error_code == "provider_request_failed"
    assert action_run["status"].value == "failed"
    assert action_run["error_code"] == "provider_request_failed"
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 1,
            "provider.request_failed": 1,
            "action.failed": 1,
        }
    )
    assert _event_by_type(events, "action.started")["action_run_id"] == action_run["id"]
    assert _event_by_type(events, "provider.request_started")["action_run_id"] == action_run["id"]
    assert _event_by_type(events, "provider.request_failed")["action_run_id"] == action_run["id"]
    assert _event_by_type(events, "action.failed")["action_run_id"] == action_run["id"]


def test_action_runner_persists_failed_state_when_exception_escapes_transaction_boundary(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with pytest.raises(ProviderGatewayExecutionError) as exc_info:
        with transaction_boundary(session_factory) as session:
            runner = _build_runner(session, fake_adapter=AlwaysFailFakeAdapter())
            asyncio.run(
                runner.run(
                    "text.extract_structured_fields",
                    "kernel_demo.extract_structured_fields_v1",
                    {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS},
                    _context(
                        step_id="extract",
                        action_type="text.extract_structured_fields",
                        action_config_id="kernel_demo.extract_structured_fields_v1",
                    ),
                )
            )

    with transaction_boundary(session_factory) as session:
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        provider_call = session.execute(sa.select(provider_calls_table)).mappings().one()
        events = _event_rows(session)

    assert exc_info.value.error_code == "provider_request_failed"
    assert action_run["status"].value == "failed"
    assert action_run["error_code"] == "provider_request_failed"
    assert provider_call["action_run_id"] == action_run["id"]
    assert provider_call["status"] == ProviderCallStatus.failed
    assert provider_call["error_code"] == "provider_request_failed"
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 1,
            "provider.request_failed": 1,
            "action.failed": 1,
        }
    )
    assert provider_call["error_message_safe"] == "Provider request failed."
    assert _event_by_type(events, "provider.request_failed")["action_run_id"] == action_run["id"]
    assert _event_by_type(events, "action.failed")["action_run_id"] == action_run["id"]
    assert _event_by_type(events, "action.failed")["workflow_version"] == 1


def test_action_runner_persists_succeeded_state_when_later_failure_rolls_back_transaction_boundary(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with pytest.raises(RuntimeError, match="force rollback"):
        with transaction_boundary(session_factory) as session:
            runner = _build_runner(session)
            asyncio.run(
                runner.run(
                    "text.extract_structured_fields",
                    "kernel_demo.extract_structured_fields_v1",
                    {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS},
                    _context(
                        step_id="extract",
                        action_type="text.extract_structured_fields",
                        action_config_id="kernel_demo.extract_structured_fields_v1",
                    ),
                )
            )
            raise RuntimeError("force rollback")

    with transaction_boundary(session_factory) as session:
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        events = _event_rows(session)

    assert action_run["status"].value == "succeeded"
    assert action_run["output_artifact_id"] is not None
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 1,
            "provider.request_succeeded": 1,
            "artifact.created": 1,
            "action.succeeded": 1,
        }
    )


def test_action_recovery_rerun_does_not_duplicate_recovered_events(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with pytest.raises(RuntimeError, match="force rollback"):
        with transaction_boundary(session_factory) as session:
            runner = _build_runner(session)
            result = asyncio.run(
                runner.run(
                    "text.extract_structured_fields",
                    "kernel_demo.extract_structured_fields_v1",
                    {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS},
                    _context(
                        step_id="extract",
                        action_type="text.extract_structured_fields",
                        action_config_id="kernel_demo.extract_structured_fields_v1",
                    ),
                )
            )
            raise RuntimeError(f"force rollback {result.action_run_id}")

    with transaction_boundary(session_factory) as session:
        action_run_id = session.execute(sa.select(action_runs_table.c.id)).scalar_one()

    _recover_action_events_after_rollback(session_factory, action_run_id)

    with transaction_boundary(session_factory) as session:
        events = _event_rows(session)

    assert [event_row["event_type"] for event_row in events] == [
        "action.started",
        "provider.request_started",
        "provider.request_succeeded",
        "artifact.created",
        "action.succeeded",
    ]
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 1,
            "provider.request_succeeded": 1,
            "artifact.created": 1,
            "action.succeeded": 1,
        }
    )


def test_action_runner_persists_failed_state_when_cancellation_escapes_transaction_boundary(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with pytest.raises(asyncio.CancelledError):
        with transaction_boundary(session_factory) as session:
            runner = _build_runner(session, fake_adapter=CancelledFakeAdapter())
            asyncio.run(
                runner.run(
                    "text.extract_structured_fields",
                    "kernel_demo.extract_structured_fields_v1",
                    {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS},
                    _context(
                        step_id="extract",
                        action_type="text.extract_structured_fields",
                        action_config_id="kernel_demo.extract_structured_fields_v1",
                    ),
                )
            )

    with transaction_boundary(session_factory) as session:
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        provider_call = session.execute(sa.select(provider_calls_table)).mappings().one()
        events = _event_rows(session)

    assert action_run["status"].value == "failed"
    assert action_run["error_code"] == "action_execution_cancelled"
    assert provider_call["action_run_id"] == action_run["id"]
    assert provider_call["status"] == ProviderCallStatus.failed
    assert provider_call["error_code"] == "provider_request_cancelled"
    assert provider_call["failure_kind"] == "cancelled"
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 1,
            "provider.request_failed": 1,
            "action.failed": 1,
        }
    )
    assert _event_by_type(events, "provider.request_failed")["action_run_id"] == action_run["id"]
    assert _event_by_type(events, "action.failed")["action_run_id"] == action_run["id"]


def test_failed_action_recovery_clears_output_artifact_id_when_artifact_row_rolled_back(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    record = ActionRunRecord(
        id="action_run_missing_artifact",
        tenant_id="tenant_demo",
        region="eu-central",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_session_id="scenario_session_demo",
        job_id="job_demo",
        workflow_id="kernel_demo.extract_detect_report_v1",
        step_id="extract",
        action_type="text.extract_structured_fields",
        action_config_id="kernel_demo.extract_structured_fields_v1",
        status=ActionRunStatus.running,
        output_artifact_id="artifact_rolled_back",
        metadata={"workflow_version": 1},
    )

    _recover_failed_action_run_row_after_rollback(
        session_factory,
        record,
        error_code="provider_request_failed",
        metadata_updates={},
        output_artifact_id="artifact_rolled_back",
    )

    with transaction_boundary(session_factory) as session:
        action_run = session.execute(
            sa.select(action_runs_table).where(action_runs_table.c.id == record.id)
        ).mappings().one()

    assert action_run["status"].value == "failed"
    assert action_run["error_code"] == "provider_request_failed"
    assert action_run["output_artifact_id"] is None


def test_action_runner_marks_failed_on_input_validation_error(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session)

        with pytest.raises(ActionInputValidationError) as exc_info:
            asyncio.run(
                runner.run(
                    "text.extract_structured_fields",
                    "kernel_demo.extract_structured_fields_v1",
                    {"unexpected": "shape"},
                    _context(
                        step_id="extract",
                        action_type="text.extract_structured_fields",
                        action_config_id="kernel_demo.extract_structured_fields_v1",
                    ),
                )
            )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        provider_call_count = session.execute(
            sa.select(sa.func.count()).select_from(provider_calls_table)
        ).scalar_one()
        events = _event_rows(session)

    assert exc_info.value.code == "action_input_validation_failed"
    assert action_run["status"].value == "failed"
    assert action_run["error_code"] == "action_input_validation_failed"
    assert provider_call_count == 0
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "action.failed": 1,
        }
    )
    assert _event_by_type(events, "action.started")["workflow_version"] == 1
    assert _event_by_type(events, "action.failed")["workflow_version"] == 1


def test_action_runner_allows_executor_responses_without_provider_call(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        registry = build_config_registry(CONFIG_ROOT)
        emitter = EventEmitter(EventLogRepository(session))
        runner = ActionRunner(
            session=session,
            config_registry=registry,
            action_run_service=ActionRunService(ActionRunRepository(session), emitter),
            executors={GenericExecutor.executor_id: GenericExecutor()},
            artifact_repository=ArtifactRepository(session),
        )

        result = asyncio.run(
            runner.run(
                "text.extract_structured_fields",
                "kernel_demo.extract_structured_fields_v1",
                {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS},
                _context(
                    step_id="extract",
                    action_type="text.extract_structured_fields",
                    action_config_id="kernel_demo.extract_structured_fields_v1",
                ),
            )
        )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        artifact_count = session.execute(
            sa.select(sa.func.count()).select_from(artifacts_table)
        ).scalar_one()

    assert result.status.value == "succeeded"
    assert result.output_payload == {
        "title": "Generic Summary",
        "fields": ["budget"],
    }
    assert result.output_artifact_id is None
    assert result.provider_policy_ref is None
    assert result.provider is None
    assert result.model is None
    assert action_run["output_artifact_id"] is None
    assert artifact_count == 0
    assert action_run["metadata"]["llm_response_metadata"] == {
        "structured_output_artifact_id": "artifact_generic"
    }
    assert "structured_output_artifact_id" not in action_run["metadata"]
    assert "provider" not in action_run["metadata"]
    assert "model" not in action_run["metadata"]


def test_action_runner_ignores_non_structured_output_artifact_id_from_executor_metadata(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        registry = build_config_registry(CONFIG_ROOT)
        emitter = EventEmitter(EventLogRepository(session))
        artifact_service = ArtifactService(ArtifactRepository(session), emitter)
        debug_artifact = artifact_service.create_structured_output_debug_artifact(
            tenant_id="tenant_demo",
            region="eu-central",
            product_id="kernel_demo",
            frontend_id="kernel_demo_ce",
            scenario_session_id="scenario_session_demo",
            job_id="job_demo",
            action_run_id="action_run_debug",
            raw_output_text="not-json",
        )
        runner = ActionRunner(
            session=session,
            config_registry=registry,
            action_run_service=ActionRunService(ActionRunRepository(session), emitter),
            executors={GenericExecutor.executor_id: GenericExecutor(debug_artifact.id)},
            artifact_repository=ArtifactRepository(session),
        )

        result = asyncio.run(
            runner.run(
                "text.extract_structured_fields",
                "kernel_demo.extract_structured_fields_v1",
                {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS},
                _context(
                    step_id="extract",
                    action_type="text.extract_structured_fields",
                    action_config_id="kernel_demo.extract_structured_fields_v1",
                ),
            )
        )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()

    assert debug_artifact.artifact_type == "structured_output_debug_raw"
    assert result.output_artifact_id is None
    assert action_run["output_artifact_id"] is None
    assert "structured_output_artifact_id" not in action_run["metadata"]


def test_action_runner_does_not_link_failed_action_to_debug_raw_artifact(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session, fake_adapter=InvalidStructuredOutputAdapter())

        with pytest.raises(StructuredOutputValidationError) as exc_info:
            asyncio.run(
                runner.run(
                    "text.extract_structured_fields",
                    "kernel_demo.extract_structured_fields_v1",
                    {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS},
                    _context(
                        step_id="extract",
                        action_type="text.extract_structured_fields",
                        action_config_id="kernel_demo.extract_structured_fields_v1",
                    ),
                )
            )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        artifacts = session.execute(sa.select(artifacts_table)).mappings().all()

    assert exc_info.value.code == "structured_output_validation_failed"
    assert action_run["status"].value == "failed"
    assert action_run["output_artifact_id"] is None
    assert len(artifacts) == 1
    assert artifacts[0]["artifact_type"] == "structured_output_debug_raw"
    assert artifacts[0]["action_run_id"] == action_run["id"]


def test_action_runner_rejects_duplicate_field_names_before_any_provider_call(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    counting_adapter = CountingFakeAdapter(FakeProviderAdapter(FIXTURE_ROOT))
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session, fake_adapter=counting_adapter)
        duplicate_fields = [
            {
                "name": "deadline",
                "type": "string",
                "description": "Project deadline mentioned in the text.",
                "required": True,
            },
            {
                "name": "deadline",
                "type": "number",
                "description": "A conflicting second spec with the same name.",
                "required": False,
            },
        ]

        with pytest.raises(ActionInputValidationError):
            asyncio.run(
                runner.run(
                    "text.extract_structured_fields",
                    "kernel_demo.extract_structured_fields_v1",
                    {"source_text": "deadline budget deliverables", "fields": duplicate_fields},
                    _context(
                        step_id="extract",
                        action_type="text.extract_structured_fields",
                        action_config_id="kernel_demo.extract_structured_fields_v1",
                    ),
                )
            )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()

    assert counting_adapter.call_count == 0
    assert action_run["status"].value == "failed"
    assert action_run["error_code"] == "action_input_validation_failed"


def test_action_runner_rejects_duplicate_criteria_ids_before_any_provider_call(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    counting_adapter = CountingFakeAdapter(FakeProviderAdapter(FIXTURE_ROOT))
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session, fake_adapter=counting_adapter)
        duplicate_criteria = [
            {"id": "tone", "description": "Matches the reference tone."},
            {"id": "tone", "description": "A conflicting second spec with the same id."},
        ]

        with pytest.raises(ActionInputValidationError):
            asyncio.run(
                runner.run(
                    "text.compare_and_classify",
                    "kernel_demo.compare_and_classify_v1",
                    {
                        "subject_text": "Subject copy",
                        "reference_text": "Reference copy",
                        "categories": ["meets_bar", "below_bar"],
                        "criteria": duplicate_criteria,
                    },
                    _context(
                        step_id="compare_and_classify",
                        action_type="text.compare_and_classify",
                        action_config_id="kernel_demo.compare_and_classify_v1",
                    ),
                )
            )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()

    assert counting_adapter.call_count == 0
    assert action_run["status"].value == "failed"
    assert action_run["error_code"] == "action_input_validation_failed"


def test_action_runner_rejects_missing_workflow_version_before_creating_action_run(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session)

        with pytest.raises(ValueError, match="workflow_version"):
            asyncio.run(
                runner.run(
                    "text.extract_structured_fields",
                    "kernel_demo.extract_structured_fields_v1",
                    {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS},
                    _context(
                        step_id="extract",
                        action_type="text.extract_structured_fields",
                        action_config_id="kernel_demo.extract_structured_fields_v1",
                        workflow_version=None,
                    ),
                )
            )
        action_run_count = session.execute(
            sa.select(sa.func.count()).select_from(action_runs_table)
        ).scalar_one()
        event_count = session.execute(
            sa.select(sa.func.count()).select_from(event_log_table)
        ).scalar_one()

    assert action_run_count == 0
    assert event_count == 0


def test_action_runner_executes_score_multidimensional_axes_atom_through_generic_path(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session)

        result = asyncio.run(
            runner.run(
                "text.score_multidimensional_axes",
                "kernel_demo.score_multidimensional_axes_v1",
                {
                    "text": "The deliverable ships Friday but the middle section wanders.",
                    "axes": [
                        {"id": "clarity", "description": "How clearly the text states its point."},
                        {"id": "structure", "description": "How well organized the text is."},
                    ],
                },
                _context(
                    step_id="score_multidim",
                    action_type="text.score_multidimensional_axes",
                    action_config_id="kernel_demo.score_multidimensional_axes_v1",
                ),
            )
        )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        artifact = session.execute(sa.select(artifacts_table)).mappings().one()
        provider_call = session.execute(sa.select(provider_calls_table)).mappings().one()
        events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert result.output_payload == {
        "scores": [
            {
                "axis_id": "clarity",
                "score": 8,
                "commentary": "The text states its point directly with no ambiguous phrasing.",
            },
            {
                "axis_id": "structure",
                "score": 5,
                "commentary": "The text lacks clear paragraph breaks between its two ideas.",
            },
        ],
        "dominant_axes": ["clarity"],
        "weakest_axes": ["structure"],
    }
    assert result.output_artifact_id == artifact["id"]
    assert action_run["status"].value == "succeeded"
    assert action_run["output_artifact_id"] == artifact["id"]
    assert artifact["action_run_id"] == action_run["id"]
    assert artifact["metadata"]["schema_ref"] == "kernel.schemas.score_multidim_output_v1"
    assert provider_call["action_run_id"] == action_run["id"]
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 1,
            "provider.request_succeeded": 1,
            "artifact.created": 1,
            "action.succeeded": 1,
        }
    )
    action_started = _event_by_type(events, "action.started")
    artifact_created = _event_by_type(events, "artifact.created")
    action_succeeded = _event_by_type(events, "action.succeeded")
    assert action_started["action_run_id"] == action_run["id"]
    assert artifact_created["artifact_id"] == artifact["id"]
    assert action_succeeded["action_run_id"] == action_run["id"]


def test_action_runner_retries_score_multidimensional_axes_cross_validation_through_real_ledger(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    """A03: proves the dominant/weakest tie-preserving-order recompute cross-validation
    retry through the real ProviderGateway/ActionRunner path - a mismatched `dominant_axes`
    followed by a compliant one must create two physical provider_calls rows with the
    expected semantic/physical indexes, provider events, and final artifact lineage."""
    adapter = ScoreMultidimensionalAxesDominantMismatchThenValidAdapter()
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session, fake_adapter=adapter)
        # default_fake_provider_v1 allows 1 validation attempt / 1 physical call per action;
        # widen both so the semantic retry this test drives can actually reach a 2nd
        # physical call through the real ProviderGateway hard-limit check, not just PydanticAI.
        executor = runner._executors["structured_llm"]
        base_policy = executor._require_provider_policy("default_fake_provider_v1")
        patched_policy = replace(
            base_policy,
            retry_policy=replace(
                base_policy.retry_policy,
                validation=ProviderValidationRetryPolicy(
                    owner=base_policy.retry_policy.validation.owner,
                    max_attempts=2,
                ),
                hard_limits=ProviderRetryHardLimits(max_physical_provider_calls_per_action=2),
            ),
        )
        executor._require_provider_policy = lambda _provider_policy_ref: patched_policy
        executor._provider_gateway._policy_resolver.resolve = lambda _provider_policy_ref: patched_policy

        result = asyncio.run(
            runner.run(
                "text.score_multidimensional_axes",
                "kernel_demo.score_multidimensional_axes_v1",
                {
                    "text": "Some text.",
                    "axes": [
                        {"id": "clarity", "description": "How clearly the text states its point."},
                        {"id": "structure", "description": "How well organized the text is."},
                    ],
                },
                _context(
                    step_id="score_multidim",
                    action_type="text.score_multidimensional_axes",
                    action_config_id="kernel_demo.score_multidimensional_axes_v1",
                ),
            )
        )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        artifact = session.execute(sa.select(artifacts_table)).mappings().one()
        provider_calls = list(
            session.execute(
                sa.select(provider_calls_table).order_by(
                    provider_calls_table.c.created_at, provider_calls_table.c.id
                )
            ).mappings()
        )
        events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert result.output_payload["dominant_axes"] == ["clarity"]
    assert result.output_artifact_id == artifact["id"]
    assert adapter.call_count == 2
    assert len(provider_calls) == 2
    assert [row["semantic_attempt_index"] for row in provider_calls] == [1, 2]
    # physical_call_index tracks the action-wide physical-call budget, not a per-semantic-
    # attempt counter, so it keeps climbing across semantic attempts too.
    assert [row["physical_call_index"] for row in provider_calls] == [1, 2]
    assert all(row["action_run_id"] == action_run["id"] for row in provider_calls)
    assert action_run["status"].value == "succeeded"
    assert action_run["output_artifact_id"] == artifact["id"]
    assert artifact["action_run_id"] == action_run["id"]
    assert _event_counts(events) == Counter(
        {
            "action.started": 1,
            "provider.request_started": 2,
            "provider.request_succeeded": 2,
            "artifact.created": 1,
            "action.succeeded": 1,
        }
    )
    artifact_created = _event_by_type(events, "artifact.created")
    assert artifact_created["artifact_id"] == artifact["id"]


def test_action_runner_rejects_duplicate_axes_ids_before_any_provider_call(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    counting_adapter = CountingFakeAdapter(FakeProviderAdapter(FIXTURE_ROOT))
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session, fake_adapter=counting_adapter)
        duplicate_axes = [
            {"id": "clarity", "description": "How clearly the text states its point."},
            {"id": "clarity", "description": "A conflicting second spec with the same id."},
        ]

        with pytest.raises(ActionInputValidationError):
            asyncio.run(
                runner.run(
                    "text.score_multidimensional_axes",
                    "kernel_demo.score_multidimensional_axes_v1",
                    {"text": "Some text.", "axes": duplicate_axes},
                    _context(
                        step_id="score_multidim",
                        action_type="text.score_multidimensional_axes",
                        action_config_id="kernel_demo.score_multidimensional_axes_v1",
                    ),
                )
            )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()

    assert counting_adapter.call_count == 0
    assert action_run["status"].value == "failed"
    assert action_run["error_code"] == "action_input_validation_failed"
