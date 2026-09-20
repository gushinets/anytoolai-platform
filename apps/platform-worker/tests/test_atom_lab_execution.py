from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import monotonic
from typing import Any

import pytest
import sqlalchemy as sa
from anytoolai_platform_actions.structured_llm.executor import StructuredLlmActionExecutor
from anytoolai_platform_core.actions.executor import ActionExecutorRequest
from anytoolai_platform_core.atom_lab.models import AtomLabRunStatus
from anytoolai_platform_core.atom_lab.repository import AtomLabRunRepository
from anytoolai_platform_core.atom_lab.service import (
    AtomLabRunAdmissionRequest,
    AtomLabRunHistoryService,
    AtomLabRunService,
)
from anytoolai_platform_core.atom_lab.snapshots import (
    AtomLabSnapshotRequest,
    build_atom_lab_run_record,
)
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.providers.models import (
    ProviderCallStatus,
    ProviderModelAddressing,
    ProviderResponse,
    ReasoningEffort,
)
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.db import (
    artifacts_table,
    atom_lab_runs_table,
    guest_identities_table,
    jobs_table,
    runtime_metadata,
    scenario_sessions_table,
)
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
LOCK_COORDINATION_TIMEOUT_SECONDS = 10
LOCK_OBSERVATION_INTERVAL_SECONDS = 0.01
DIAGNOSTIC_MARKER_SEPARATORS = (
    "\n", "\t", "\u00a0", "\u2003", "\u202e", "\x00", "\x1b[31m", "\x9b31m", r"\n", r"\t",
)

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


class _SequenceLabAdapter:
    """Only the external provider is replaced; retry and persistence remain real."""

    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = iter(responses)

    async def complete(self, request):
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider=request.provider,
            model=request.model,
            output_text=response,
            status=ProviderCallStatus.succeeded,
            metadata={
                "litellm": {"actual_model": "gpt-5.4-mini-2026-03-17"},
                "reasoning_content": "private hidden reasoning",
                "authorization": "Bearer private-provider-key",
            },
        )


def _history(session_factory, run_id):
    with transaction_boundary(session_factory) as session:
        state, = AtomLabRunRepository(session).history_in_scope(
            tenant_id="anytoolai", region="default", run_id=run_id, limit=1
        )
        return AtomLabRunHistoryService(session).detail(state)


def _attempt_counts(diagnostics):
    return tuple(diagnostics[key] for key in (
        "validation_attempts", "transport_attempts", "physical_calls",
    ))


def test_invalid_lab_output_is_bounded_durable_and_never_a_result(session_factory) -> None:
    """Catches unbounded raw persistence and missing protected failure diagnostics."""
    registry = build_config_registry(CONFIG_ROOT)
    with transaction_boundary(session_factory) as session:
        _scenario, job, run = _seed_lab_run(session, registry)
    invalid = "Ж" * 5000
    worker = build_worker(
        session_factory=session_factory, config_registry=registry,
        provider_adapters={"litellm": _SequenceLabAdapter([invalid, invalid])},
    )
    try:
        processed = asyncio.run(worker.process_next_job())
    finally:
        worker.dispose()
    assert processed is not None and processed.status is JobStatus.failed
    first = _history(session_factory, run.id)
    assert first["result"] is None
    diagnostics = first["diagnostics"]
    assert diagnostics["error_code"] == "structured_output_validation_failed"
    assert _attempt_counts(diagnostics) == (2, 2, 2)
    debug, = diagnostics["debug_artifacts"]
    assert debug["raw_output_text"] == "Ж" * 4096
    assert debug["truncated"] is True
    assert debug["redacted"] is False
    with transaction_boundary(session_factory) as session:
        artifact = session.execute(
            sa.select(artifacts_table).where(artifacts_table.c.id == debug["artifact_id"])
        ).mappings().one()
        assert artifact["content_text"] == "Ж" * 4096
        assert artifact["metadata"]["atom_lab_run_id"] == run.id
    restarted = build_worker(
        session_factory=session_factory, config_registry=registry,
        provider_adapters={"litellm": _SequenceLabAdapter([])},
    )
    try:
        replay = asyncio.run(restarted._workflow_handler.handle(job.id))
    finally:
        restarted.dispose()
    assert replay is not None and replay.status is JobStatus.failed
    assert _history(session_factory, run.id) == first


@pytest.mark.parametrize("invalid", [
    '{"api_key":"sk-sensitive-provider-value"}',
    "Bearer private-access-code",
    '<think>private hidden reasoning</think>invalid',
    '{"reasoning_content":"private hidden reasoning"}',
    r'{"api\u005fkey":"private-value"}',
    r'{"rea\u0073oning_content":"private internal content"}',
    'api\x1b[31m_key=private-value',
    r'{"api\u005fkey":"private-value",}',
    r'{"rea\u0000soning_content":"private internal content"}',
    "-----BEGIN PRIVATE KEY-----\nYWJj\n-----END PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----\nYWJj\n-----END RSA PRIVATE KEY-----",
    "-----BEGIN OPENSSH PRIVATE KEY-----\nYWJj\n-----END OPENSSH PRIVATE KEY-----",
    '{"private_key":"private-value"}',
    '{"privateKey":"private-value"}',
    '{"PRIVATE--KEY":"private-value"}',
    '<thinking>private internal content</thinking>invalid',
    r'{"api\tkey":"private-value"}',
    "Here is sk-\nabcdefghijklmnopqrst",
    "Here is s\tk-abcdefghijklmnopqrst",
    "Here is eyJ\nhbGciOiJub25lIn0.cGF5bG9hZA.c2lnbmF0dXJl",
    "Here is e\tyJhbGciOiJub25lIn0.cGF5bG9hZA.c2lnbmF0dXJl",
    "Here is e\x9b31myJhbGciOiJub25lIn0.cGF5bG9hZA.c2lnbmF0dXJl",
    "Here is sk-\u202e\tabcdefghijklmnopqrst",
    "rea\x9b31msoning_content: private deliberation",
    *[
        f'{{"rea{separator}soning_content":"private internal content"}}'
        for separator in DIAGNOSTIC_MARKER_SEPARATORS
    ],
    *[
        f'{{"pr{separator}ivate_k{separator}ey":"private-value"}}'
        for separator in DIAGNOSTIC_MARKER_SEPARATORS
    ],
    *[
        f'<t{separator}hinking>private internal content</t{separator}hinking>'
        for separator in DIAGNOSTIC_MARKER_SEPARATORS
    ],
])
def test_invalid_lab_output_with_sensitive_markers_is_withheld(session_factory, invalid) -> None:
    """Catches credentials or hidden-reasoning envelopes leaking through raw diagnostics."""
    registry = build_config_registry(CONFIG_ROOT)
    with transaction_boundary(session_factory) as session:
        _scenario, _job, run = _seed_lab_run(session, registry)
    worker = build_worker(
        session_factory=session_factory, config_registry=registry,
        provider_adapters={"litellm": _SequenceLabAdapter([invalid, invalid])},
    )
    try:
        asyncio.run(worker.process_next_job())
    finally:
        worker.dispose()
    debug, = _history(session_factory, run.id)["diagnostics"]["debug_artifacts"]
    assert debug["raw_output_text"] == "[redacted]"
    assert debug["redacted"] is True
    assert debug["truncated"] is False
    with transaction_boundary(session_factory) as session:
        assert session.scalar(
            sa.select(artifacts_table.c.content_text).where(
                artifacts_table.c.id == debug["artifact_id"]
            )
        ) == "[redacted]"


@pytest.mark.parametrize(
    ("prefix_responses", "expected_indices", "attempt_counts"),
    [
        (["not-json"], [(1, 1, 1), (2, 1, 2)], (2, 2, 2)),
        ([TimeoutError("private timeout")], [(1, 1, 1), (1, 2, 2)], (1, 2, 2)),
        (
            ["not-json", TimeoutError("private timeout")],
            [(1, 1, 1), (2, 1, 2), (2, 2, 3)], (2, 3, 3),
        ),
    ],
    ids=["validation-correction", "transport-retry", "validation-and-transport"],
)
def test_lab_retry_success_keeps_separate_physical_calls_after_restart(
    session_factory, prefix_responses, expected_indices, attempt_counts,
) -> None:
    """Catches conflated retries, dropped ledger rows, or reexecution of a terminal job."""
    registry = build_config_registry(CONFIG_ROOT)
    with transaction_boundary(session_factory) as session:
        _scenario, job, run = _seed_lab_run(session, registry)
    expected = {
        "values": {"deadline": "tomorrow"}, "missing_fields": [],
        "confidence": {"deadline": 0.9},
    }
    worker = build_worker(
        session_factory=session_factory, config_registry=registry,
        provider_adapters={
            "litellm": _SequenceLabAdapter([*prefix_responses, json.dumps(expected)])
        },
    )
    try:
        processed = asyncio.run(worker.process_next_job())
    finally:
        worker.dispose()
    assert processed is not None and processed.status is JobStatus.succeeded
    first = _history(session_factory, run.id)
    assert first["result"] == expected
    diagnostics = first["diagnostics"]
    assert _attempt_counts(diagnostics) == attempt_counts
    assert diagnostics["succeeded_first_attempt"] is False
    assert diagnostics["response_model_id"] == "gpt-5.4-mini-2026-03-17"
    assert [
        (row["semantic_attempt_index"], row["transport_attempt_index"], row["physical_call_index"])
        for row in diagnostics["provider_calls"]
    ] == expected_indices
    assert "private" not in json.dumps(diagnostics)
    restarted = build_worker(
        session_factory=session_factory, config_registry=registry,
        provider_adapters={"litellm": _SequenceLabAdapter([])},
    )
    try:
        asyncio.run(restarted._workflow_handler.handle(job.id))
    finally:
        restarted.dispose()
    assert _history(session_factory, run.id) == first


def test_lab_provider_failure_exposes_only_safe_code_and_complete_attempts(session_factory):
    """Catches exception-message leakage and loss of failed physical attempts on rollback."""
    registry = build_config_registry(CONFIG_ROOT)
    with transaction_boundary(session_factory) as session:
        _scenario, _job, run = _seed_lab_run(session, registry)
    worker = build_worker(
        session_factory=session_factory, config_registry=registry,
        provider_adapters={"litellm": _SequenceLabAdapter([
            TimeoutError("Authorization Bearer private-token; private prompt"),
            TimeoutError("Authorization Bearer private-token; private prompt"),
        ])},
    )
    try:
        processed = asyncio.run(worker.process_next_job())
    finally:
        worker.dispose()
    assert processed is not None and processed.status is JobStatus.failed
    detail = _history(session_factory, run.id)
    diagnostics = detail["diagnostics"]
    assert detail["result"] is None
    assert diagnostics["error_code"] == "provider_request_timed_out"
    assert _attempt_counts(diagnostics) == (1, 2, 2)
    assert diagnostics["debug_artifacts"] == []
    assert "private" not in json.dumps(diagnostics)


def test_lab_worker_lease_lost_remains_visible_after_reconciliation(session_factory):
    """Catches a restarted worker hiding or rerunning an accepted abandoned job."""
    registry = build_config_registry(CONFIG_ROOT)
    with transaction_boundary(session_factory) as session:
        _scenario, job, run = _seed_lab_run(session, registry)
    worker = build_worker(
        session_factory=session_factory, config_registry=registry,
        provider_adapters={"litellm": _SequenceLabAdapter([])},
    )
    try:
        assert worker._workflow_handler._claim(job.id) is not None
        assert _history(session_factory, run.id)["status"] == "running"
        worker._workflow_handler.terminate_orphaned_job(job.id)
        first = _history(session_factory, run.id)
        worker._workflow_handler.terminate_orphaned_job(job.id)
        asyncio.run(worker._workflow_handler.handle(job.id))
    finally:
        worker.dispose()
    assert first["status"] == "failed"
    assert first["finished_at"] is not None
    assert first["result"] is None
    assert first["diagnostics"]["error_code"] == "worker_lease_lost"
    assert first["diagnostics"]["physical_calls"] == 0
    assert first["runtime_ids"]["action_run_id"] is None
    assert _history(session_factory, run.id) == first


@pytest.fixture
def postgres_session_factory() -> Iterator[sa.orm.sessionmaker[sa.orm.Session]]:
    with provision_database(
        database_name_prefix="anytoolai_atom_lab_worker_test",
        skip_reason="PostgreSQL Atom Lab worker concurrency coverage",
    ) as (engine, _alembic_config, _database_url):
        yield build_session_factory(engine)


def _admit_with_observed_scope_lock_contention(postgres_session_factory, registry, request):
    first_locked = threading.Event()
    second_started = threading.Event()
    release_first = threading.Event()
    backend_pids: dict[str, int] = {}

    def hold_first_admission():
        # Validation is reached after scope locking but before any run/count writes.
        # Holding here isolates admission row locking from incidental insert conflicts.
        first_locked.set()
        assert release_first.wait(LOCK_COORDINATION_TIMEOUT_SECONDS * 2)

    def submit_first():
        with transaction_boundary(postgres_session_factory) as session:
            backend_pids["first"] = session.scalar(sa.text("SELECT pg_backend_pid()"))
            return AtomLabRunService(session=session, config_registry=registry).start(
                request, validate=hold_first_admission,
            )

    def submit_second():
        with transaction_boundary(postgres_session_factory) as session:
            backend_pids["second"] = session.scalar(sa.text("SELECT pg_backend_pid()"))
            second_started.set()
            return AtomLabRunService(session=session, config_registry=registry).start(
                request, validate=lambda: None,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(submit_first)
        try:
            assert first_locked.wait(LOCK_COORDINATION_TIMEOUT_SECONDS)
            second = executor.submit(submit_second)
            assert second_started.wait(LOCK_COORDINATION_TIMEOUT_SECONDS)
            blocked_by_first = False
            deadline = monotonic() + LOCK_COORDINATION_TIMEOUT_SECONDS
            with transaction_boundary(postgres_session_factory) as observer:
                while monotonic() < deadline and not second.done():
                    blocked_by_first = observer.scalar(sa.text(
                        "SELECT :first_pid = ANY(pg_blocking_pids(:second_pid))"
                    ), {"first_pid": backend_pids["first"], "second_pid": backend_pids["second"]})
                    if blocked_by_first:
                        break
                    release_first.wait(LOCK_OBSERVATION_INTERVAL_SECONDS)
            assert blocked_by_first, "second admission must wait for the first scope row lock"
            assert not second.done(), "second admission completed while the first lock was held"
        finally:
            release_first.set()
        return [
            first.result(timeout=LOCK_COORDINATION_TIMEOUT_SECONDS),
            second.result(timeout=LOCK_COORDINATION_TIMEOUT_SECONDS),
        ]


@pytest.mark.postgresql
@pytest.mark.slow
def test_concurrent_lab_submission_creates_one_job_with_distinct_allowed_retries(
    postgres_session_factory,
) -> None:
    """Catches existing-scope admission races and conflating retry calls with new runs."""
    registry = build_config_registry(CONFIG_ROOT)
    request = AtomLabRunAdmissionRequest(
        tenant_id="anytoolai", region="default", product_id="kernel_demo",
        frontend_id="kernel_demo_web", atom_id="A01",
        input_payload={
            "source_text": "The deadline is tomorrow.",
            "fields": [{
                "name": "deadline", "type": "string", "description": "Date", "required": True,
            }],
            "strict": False,
        },
        prompt="Extract the deadline.", model_id="openai/gpt-5.4-mini",
        reasoning_effort=ReasoningEffort.high,
        capability_snapshot_id="worker-integration", capability_provenance={"source": "fixture"},
        idempotency_key="concurrent-submission",
    )
    with transaction_boundary(postgres_session_factory) as session:
        now = utc_now()
        AtomLabRunRepository(session).lock_admission_scope(
            tenant_id=request.tenant_id, region=request.region,
            accepted_on=now.date(), now=now,
        )
    admitted = _admit_with_observed_scope_lock_contention(
        postgres_session_factory, registry, request,
    )
    assert len({run.run_id for run in admitted}) == 1
    assert sorted(run.replayed for run in admitted) == [False, True]
    run = admitted[0]
    expected = {
        "values": {"deadline": "tomorrow"}, "missing_fields": [],
        "confidence": {"deadline": 0.9},
    }
    worker = build_worker(
        session_factory=postgres_session_factory, config_registry=registry,
        provider_adapters={"litellm": _SequenceLabAdapter([
            "not-json", TimeoutError("temporary timeout"), json.dumps(expected),
        ])},
    )
    try:
        processed = asyncio.run(worker.process_next_job())
        assert asyncio.run(worker.process_next_job()) is None
    finally:
        worker.dispose()
    assert processed is not None and processed.status is JobStatus.succeeded
    detail = _history(postgres_session_factory, run.run_id)
    assert detail["result"] == expected
    assert [
        (row["semantic_attempt_index"], row["transport_attempt_index"], row["physical_call_index"])
        for row in detail["diagnostics"]["provider_calls"]
    ] == [(1, 1, 1), (2, 1, 2), (2, 2, 3)]
    assert _attempt_counts(detail["diagnostics"]) == (2, 3, 3)
    with transaction_boundary(postgres_session_factory) as session:
        replay = AtomLabRunService(session=session, config_registry=registry).start(
            request, validate=lambda: None,
        )
        assert replay.run_id == run.run_id
        assert replay.job_id == run.job_id
        assert replay.guest_id == run.guest_id
        assert replay.status is AtomLabRunStatus.succeeded
        assert replay.replayed is True
        assert [
            session.scalar(sa.select(sa.func.count()).select_from(table))
            for table in (
                atom_lab_runs_table, jobs_table, scenario_sessions_table, guest_identities_table,
            )
        ] == [1, 1, 1, 1]


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
    assert len(requests_by_job) == len(final_jobs)
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
