from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import sqlalchemy as sa
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
    definition_hash: str | None = None,
    source_suffix: str = "",
    model_id: str = "openai/gpt-5.4-mini",
    reasoning_effort: ReasoningEffort | None = ReasoningEffort.high,
):
    payload = {
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
    scenario = ScenarioSessionRepository(session).create(
        ScenarioSessionRecord(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            frontend_id="kernel_demo_web",
            scenario_id="kernel_demo.atom_lab_a01_v1",
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
            workflow_id="kernel_demo.atom_lab_a01_v1",
            workflow_version=1,
        )
    )
    record = build_atom_lab_run_record(
        registry,
        scenario=scenario,
        job=job,
        request=AtomLabSnapshotRequest(
            atom_id="A01",
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
