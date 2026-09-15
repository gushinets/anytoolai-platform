from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from anytoolai_platform_actions.structured_llm.executor import StructuredLlmActionExecutor
from anytoolai_platform_core.actions.executor import ActionExecutorRequest
from anytoolai_platform_core.atom_lab.repository import AtomLabRunRepository
from anytoolai_platform_core.atom_lab.snapshots import (
    AtomLabSnapshotRequest,
    build_atom_lab_run_record,
)
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.providers.models import (
    ProviderCallStatus,
    ProviderModelAddressing,
    ProviderResponse,
    ReasoningEffort,
)
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.db import runtime_metadata
from anytoolai_platform_core.storage.transactions import build_session_factory, transaction_boundary
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from anytoolai_platform_worker.composition import build_worker
from anytoolai_platform_worker.handlers.run_workflow import (
    AtomLabSnapshotInvalidError,
    RunWorkflowHandler,
)

from tests.db_support import provision_database
from tests.support.sqlite_harness import build_sqlite_runtime_engine

CONFIG_ROOT = Path(__file__).resolve().parents[3] / "configs" / "kernel"

EXACT_INPUT_BY_ATOM: dict[str, dict[str, Any]] = {
    "A01": {
        "source_text": "Review payload A01: delivery is 17 October and costs 91 500 EUR.",
        "fields": [
            {
                "name": "delivery_date",
                "type": "date",
                "description": "Contractual delivery date.",
                "required": True,
            },
            {
                "name": "price_eur",
                "type": "number",
                "description": "Contract price in euros.",
                "required": False,
            },
        ],
        "strict": False,
    },
    "A02": {
        "text_a": "Review payload A02: the proposal delivers an audited prototype in nine days.",
        "text_b": "The brief requires an audited prototype within twelve days.",
        "rubric": [
            {
                "id": "audit_deadline",
                "description": "Meets the audited-prototype deadline.",
                "weight": 3,
            }
        ],
    },
    "A03": {
        "text": "Review payload A03: every milestone names an owner and an acceptance check.",
        "axes": [
            {"id": "ownership", "description": "Explicit accountable owners.", "weight": 2},
            {"id": "verification", "description": "Measurable acceptance checks.", "weight": 4},
        ],
    },
    "A04": {
        "source_text": (
            "Review payload A04: ship next month; the approver and rollback plan are open."
        ),
        "context": "Pre-release readiness review.",
        "taxonomy": ["approval", "rollback"],
    },
    "A05": {
        "issues": [
            {
                "category": "ownership",
                "description": "No approver is named.",
                "severity": "medium",
                "evidence": "The approval field is blank.",
            }
        ],
        "context": "Review payload A05: prepare the launch decision record.",
        "target_audience": "Release manager",
        "max_questions": 2,
    },
    "A06": {
        "context": {"product": "Review payload A06", "saved_hours_per_week": 11},
        "objective": "Secure approval for a seven-day measurement pilot.",
        "audience": "Operations lead",
        "angle": "Measure saved time before committing to rollout.",
        "constraints": {
            "tone": "firm",
            "length": 640,
            "language": "en-GB",
            "format": "plain_text",
        },
    },
    "A07": {
        "situation": "Review payload A07: a customer asks whether the audit can start Tuesday.",
        "intent": "Confirm availability and request repository access.",
        "tone": "neutral",
        "constraints": {
            "language": "en",
            "max_length": 420,
            "output_format": "markdown",
        },
    },
    "A08": {
        "source_text": "Review payload A08: monitoring will be added later.",
        "gap": "No owner, deadline, or measurable alert target is specified.",
        "n": 2,
        "style": "bold",
    },
    "A09": {
        "signals": [
            {
                "id": "support_load",
                "label": "Support load",
                "value": 37,
                "evidence": "Review payload A09: weekly triage counted 37 duplicate tickets.",
            }
        ],
        "objective": "Prioritize automated duplicate detection.",
        "options": ["faster triage", "lower support load"],
    },
    "A10": {
        "template_ref": "review_payload_a10_release_note_v2",
        "data": {"release": "2.4", "risk": "low", "rollback_minutes": 8},
        "style": "detailed",
    },
    "A11": {
        "subject_text": "Review payload A11: the plan retains logs for 45 days.",
        "reference_text": "The policy requires at least 30 days of retention.",
        "categories": ["compliant", "non_compliant"],
        "criteria": [
            {
                "id": "retention",
                "description": "Retention meets or exceeds policy.",
                "weight": 5,
            }
        ],
    },
}


@pytest.fixture
def session_factory(tmp_path: Path):
    engine = build_sqlite_runtime_engine(tmp_path / "main.sqlite3", tmp_path / "platform.sqlite3")
    runtime_metadata.create_all(engine)
    try:
        yield build_session_factory(engine)
    finally:
        engine.dispose()


def _seed_lab_run(
    session,
    registry,
    *,
    atom_id: str = "A01",
    input_payload: dict[str, Any] | None = None,
    definition_hash: str | None = None,
    source_suffix: str = "",
    model_id: str = "openai/gpt-5.4-mini",
    reasoning_effort: ReasoningEffort | None = ReasoningEffort.high,
):
    payload = (
        input_payload
        if input_payload is not None
        else {
            "source_text": f"worker must execute this exact value{source_suffix}",
            "fields": [
                {
                    "name": "deadline",
                    "type": "string",
                    "description": "A test-only deadline field.",
                    "required": True,
                }
            ],
            "strict": False,
        }
    )
    atom_suffix = atom_id.lower()
    scenario = ScenarioSessionRepository(session).create(
        ScenarioSessionRecord(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            frontend_id="kernel_demo_web",
            scenario_id=f"kernel_demo.atom_lab_{atom_suffix}_v1",
            scenario_version=1,
            metadata={"runtime_scope": "atom_lab", "input": payload},
        )
    )
    job = JobRepository(session).create(
        JobRecord(
            tenant_id=scenario.tenant_id,
            region=scenario.region,
            product_id=scenario.product_id,
            frontend_id=scenario.frontend_id,
            scenario_session_id=scenario.id,
            workflow_id=f"kernel_demo.atom_lab_{atom_suffix}_v1",
            workflow_version=1,
        )
    )
    record = build_atom_lab_run_record(
        registry,
        scenario=scenario,
        job=job,
        request=AtomLabSnapshotRequest(
            atom_id=atom_id,
            input_payload=payload,
            prompt=f"worker edited prompt{source_suffix}",
            model_id=model_id,
            reasoning_effort=reasoning_effort,
            capability_snapshot_id="fixture-v1",
            capability_provenance={"source": "fixture", "version": "1"},
        ),
    )
    if definition_hash is not None:
        record = record.__class__(
            **{**record.__dict__, "execution_definition_hash": definition_hash}
        )
    return scenario, job, AtomLabRunRepository(session).create(record)


class _StopAtExecutorBoundary(RuntimeError):
    pass


@pytest.mark.parametrize(
    ("atom_id", "input_payload"),
    EXACT_INPUT_BY_ATOM.items(),
    ids=EXACT_INPUT_BY_ATOM,
)
def test_worker_passes_each_atom_lab_payload_unchanged_to_executor(
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
    atom_id: str,
    input_payload: dict[str, Any],
) -> None:
    """Catches per-atom workflow mappings that replace or drop accepted input fields."""
    registry = build_config_registry(CONFIG_ROOT)
    with transaction_boundary(session_factory) as session:
        _scenario, job, record = _seed_lab_run(
            session,
            registry,
            atom_id=atom_id,
            input_payload=input_payload,
        )
    action_config = registry.get_action_configuration(record.action_config_id)
    assert action_config is not None
    atom_metadata = action_config.metadata.get("atom_lab")
    assert isinstance(atom_metadata, Mapping)
    assert input_payload != atom_metadata.get("example_input")

    captured_requests: list[ActionExecutorRequest] = []

    async def capture_request(
        _executor: StructuredLlmActionExecutor,
        request: ActionExecutorRequest,
        *,
        session,
    ) -> None:
        captured_requests.append(request)
        raise _StopAtExecutorBoundary

    monkeypatch.setattr(StructuredLlmActionExecutor, "execute", capture_request)
    worker = build_worker(
        session_factory=session_factory,
        config_registry=registry,
        provider_adapters={"litellm": _RecordingLabAdapter()},
    )
    try:
        processed = asyncio.run(worker.process_next_job())
    finally:
        worker.dispose()

    assert processed is not None
    assert processed.status is JobStatus.failed
    assert len(captured_requests) == 1
    assert dict(captured_requests[0].input_payload) == input_payload


def test_worker_loads_exact_input_and_settings_from_durable_snapshot(session_factory) -> None:
    """Catches using process-local draft data after a worker restart."""
    registry = build_config_registry(CONFIG_ROOT)
    with transaction_boundary(session_factory) as session:
        scenario, job, record = _seed_lab_run(session, registry)

    handler = object.__new__(RunWorkflowHandler)
    handler._config_registry = registry
    with transaction_boundary(session_factory) as session:
        persisted_scenario = ScenarioSessionRepository(session).get(
            scenario.id,
            tenant_id=scenario.tenant_id,
            region=scenario.region,
            product_id=scenario.product_id,
            frontend_id=scenario.frontend_id,
        )
        persisted_job = JobRepository(session).get(job.id)
        assert persisted_scenario is not None and persisted_job is not None
        input_payload, settings = handler._resolve_execution_input_and_settings(
            session, persisted_job, persisted_scenario
        )

    assert input_payload == record.input_payload
    assert settings is not None
    assert settings.run_id == record.id
    assert settings.prompt == "worker edited prompt"
    assert settings.provider_policy.model == "openai/gpt-5.4-mini"


def test_worker_rejects_incompatible_snapshot_before_action_creation(session_factory) -> None:
    """Catches silent registry migration of an already accepted lab run."""
    registry = build_config_registry(CONFIG_ROOT)
    with transaction_boundary(session_factory) as session:
        scenario, job, _record = _seed_lab_run(session, registry, definition_hash="0" * 64)

    handler = object.__new__(RunWorkflowHandler)
    handler._config_registry = registry
    with transaction_boundary(session_factory) as session:
        persisted_scenario = ScenarioSessionRepository(session).get(
            scenario.id,
            tenant_id=scenario.tenant_id,
            region=scenario.region,
            product_id=scenario.product_id,
            frontend_id=scenario.frontend_id,
        )
        persisted_job = JobRepository(session).get(job.id)
        assert persisted_scenario is not None and persisted_job is not None
        with pytest.raises(AtomLabSnapshotInvalidError) as exc_info:
            handler._resolve_execution_input_and_settings(
                session, persisted_job, persisted_scenario
            )

    assert exc_info.value.code == "atom_lab_snapshot_incompatible"


class _RecordingLabAdapter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.requests = []

    async def complete(self, request):
        with self._lock:
            self.requests.append(request)
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider=request.provider,
            model=request.model,
            output_text=(
                '{"values": {"deadline": "tomorrow"}, "missing_fields": [], '
                '"confidence": {"deadline": 0.9}}'
            ),
            status=ProviderCallStatus.succeeded,
        )


def test_real_worker_path_applies_snapshot_and_binds_runtime_ids(session_factory) -> None:
    """Catches composition that loads settings in isolation but drops them in the real worker."""
    registry = build_config_registry(CONFIG_ROOT)
    with transaction_boundary(session_factory) as session:
        _scenario, job, record = _seed_lab_run(session, registry)

    adapter = _RecordingLabAdapter()
    worker = build_worker(
        session_factory=session_factory,
        config_registry=registry,
        provider_adapters={"litellm": adapter},
    )
    handler = worker._workflow_handler
    assert isinstance(handler, RunWorkflowHandler)
    handler._sync_atom_lab_runtime_ids = lambda _job_id: None
    processed = asyncio.run(worker.process_next_job())
    worker.dispose()

    assert processed is not None
    assert processed.error_code is None
    assert len(adapter.requests) == 1
    request = adapter.requests[0]
    assert request.model == "openai/gpt-5.4-mini"
    assert request.model_addressing is ProviderModelAddressing.direct
    assert request.reasoning_effort is ReasoningEffort.high
    assert request.prompt.startswith("worker edited prompt")
    assert "worker must execute this exact value" in request.prompt
    with transaction_boundary(session_factory) as session:
        stored = AtomLabRunRepository(session).get(record.id)
        assert stored is not None
        assert stored.action_run_id is not None
        assert stored.artifact_id == processed.result_artifact_id


@pytest.fixture
def postgres_session_factory() -> Iterator[sa.orm.sessionmaker[sa.orm.Session]]:
    with provision_database(
        database_name_prefix="anytoolai_atom_lab_worker_test",
        skip_reason="PostgreSQL Atom Lab worker concurrency coverage",
    ) as (engine, _alembic_config, _database_url):
        yield build_session_factory(engine)


@pytest.mark.postgresql
@pytest.mark.slow
def test_parallel_lab_runs_do_not_leak_settings_into_an_ordinary_job(
    postgres_session_factory,
) -> None:
    """Catches shared Router/registry mutation and cross-run state leakage."""
    registry = build_config_registry(CONFIG_ROOT)
    with transaction_boundary(postgres_session_factory) as session:
        _scenario_one, job_one, run_one = _seed_lab_run(
            session,
            registry,
            source_suffix=" for lab one",
            model_id="openai/gpt-5.4-mini",
            reasoning_effort=ReasoningEffort.low,
        )
        _scenario_two, job_two, run_two = _seed_lab_run(
            session,
            registry,
            source_suffix=" for lab two",
            model_id="openai/gpt-5.4",
            reasoning_effort=ReasoningEffort.high,
        )
        ordinary_input = {
            "source_text": "ordinary job input",
            "fields": [
                {
                    "name": "deadline",
                    "type": "string",
                    "description": "A normal deadline field.",
                    "required": True,
                }
            ],
            "strict": False,
        }
        ordinary_scenario = ScenarioSessionRepository(session).create(
            ScenarioSessionRecord(
                tenant_id="anytoolai",
                region="default",
                product_id="kernel_demo",
                frontend_id="kernel_demo_web",
                scenario_id="kernel_demo.single_action_smoke_v1",
                scenario_version=1,
                metadata={"input": ordinary_input},
            )
        )
        ordinary_job = JobRepository(session).create(
            JobRecord(
                tenant_id=ordinary_scenario.tenant_id,
                region=ordinary_scenario.region,
                product_id=ordinary_scenario.product_id,
                frontend_id=ordinary_scenario.frontend_id,
                scenario_session_id=ordinary_scenario.id,
                workflow_id="kernel_demo.single_action_extract_v1",
                workflow_version=1,
            )
        )

    adapter = _RecordingLabAdapter()
    barrier = threading.Barrier(3)

    def process_until_queue_is_empty() -> list[JobRecord]:
        worker = build_worker(
            session_factory=postgres_session_factory,
            config_registry=registry,
            provider_adapters={"fake": adapter, "litellm": adapter},
        )
        try:
            barrier.wait()
            observed: list[JobRecord] = []
            while True:
                job = asyncio.run(worker.process_next_job())
                if job is None:
                    return observed
                observed.append(job)
        finally:
            worker.dispose()

    with ThreadPoolExecutor(max_workers=3) as executor:
        list(executor.map(lambda _index: process_until_queue_is_empty(), range(3)))

    with transaction_boundary(postgres_session_factory) as session:
        final_jobs = [
            JobRepository(session).get(job_id)
            for job_id in (job_one.id, job_two.id, ordinary_job.id)
        ]
    assert all(job is not None and job.status is JobStatus.succeeded for job in final_jobs)
    requests_by_job = {request.job_id: request for request in adapter.requests}
    assert len(requests_by_job) == 3
    assert requests_by_job[job_one.id].model == "openai/gpt-5.4-mini"
    assert requests_by_job[job_one.id].reasoning_effort is ReasoningEffort.low
    assert requests_by_job[job_two.id].model == "openai/gpt-5.4"
    assert requests_by_job[job_two.id].reasoning_effort is ReasoningEffort.high
    assert requests_by_job[ordinary_job.id].model_addressing is ProviderModelAddressing.policy_alias
    assert requests_by_job[ordinary_job.id].reasoning_effort is None

    with transaction_boundary(postgres_session_factory) as session:
        stored_one = AtomLabRunRepository(session).get(run_one.id)
        stored_two = AtomLabRunRepository(session).get(run_two.id)
        assert stored_one is not None and stored_one.action_run_id is not None
        assert stored_two is not None and stored_two.action_run_id is not None
