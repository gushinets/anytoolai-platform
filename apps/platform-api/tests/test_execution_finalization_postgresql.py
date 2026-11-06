from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import anytoolai_platform_core.quotas.service as quota_module
import anytoolai_platform_core.workflows.runner as runner_module
import pytest
import sqlalchemy as sa
from anytoolai_platform_api.routers.handoffs import _service as handoff_service
from anytoolai_platform_core.artifacts.canonical import CanonicalArtifactError
from anytoolai_platform_core.artifacts.models import ArtifactRecord, ArtifactStatus
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.handoffs.models import AcceptHandoffCommand
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.quotas.execution_repository import ExecutionReservationRepository
from anytoolai_platform_core.quotas.finalization import finalize_success, release_execution
from anytoolai_platform_core.quotas.models import (
    FinalExecutionResult,
    QuotaPeriod,
    ReservationState,
)
from anytoolai_platform_core.quotas.service import QuotaExhaustedError
from anytoolai_platform_core.results.service import ResultService
from anytoolai_platform_core.scenarios.models import ScenarioSessionStatus
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.scenarios.service import (
    IdempotencyKeyConflictError,
    ScenarioNotFoundError,
    ScenarioSessionService,
)
from anytoolai_platform_core.storage.db import (
    action_runs_table,
    artifacts_table,
    event_log_table,
    execution_reservations_table,
    guest_quota_usage_table,
    jobs_table,
    paid_allowance_usage_table,
    provider_calls_table,
    scenario_sessions_table,
)
from anytoolai_platform_core.storage.transactions import (
    engine_from_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.workflows.models import JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from anytoolai_platform_core.workflows.runner import (
    SequentialWorkflowRunner,
    WorkflowJobService,
    _recover_failed_workflow_row_after_rollback,
    _recover_succeeded_workflow_row_after_rollback,
)
from anytoolai_platform_worker.composition import build_worker
from anytoolai_platform_worker.lease import AdvisoryJobLease
from test_execution_admission_postgresql import allowance, rows, start, without_scenario_config
from test_execution_admission_postgresql import runtime as runtime_fixture
from test_handoffs_api import _create, _request, _seed_source
from test_scenario_runtime_api import FIXTURE_ROOT

pytestmark = [pytest.mark.postgresql, pytest.mark.slow]
runtime = runtime_fixture


def worker_for(runtime, **changes):
    factory, _, registry = runtime
    return build_worker(
        session_factory=factory,
        config_registry=registry,
        provider_adapters={"fake": FakeProviderAdapter(FIXTURE_ROOT)},
        **changes,
    )


def accepted(runtime, paid=True):
    factory, _, registry = runtime
    with transaction_boundary(factory) as session:
        return start(session, registry, allowance() if paid else None)


def candidate(runtime, acceptance):
    factory, _, registry = runtime
    with transaction_boundary(factory) as session:
        repository = JobRepository(session)
        job = WorkflowJobService(
            repository, EventEmitter(EventLogRepository(session))
        ).claim_created(acceptance.job_id)
        scenario = ScenarioSessionRepository(session).get_in_scope(
            acceptance.scenario_session_id, tenant_id="anytoolai", region="ru"
        )
        ScenarioSessionService(
            ScenarioSessionRepository(session), EventEmitter(EventLogRepository(session))
        ).mark_running(scenario)
        workflow = registry.get_workflow(job.workflow_id)
        schema = registry.get_schema(workflow.output_schema_ref)
        artifact = ArtifactRecord(
            tenant_id=job.tenant_id,
            region=job.region,
            product_id=job.product_id,
            frontend_id=job.frontend_id,
            scenario_session_id=job.scenario_session_id,
            job_id=job.id,
            artifact_type="structured_output",
            status=ArtifactStatus.stored,
            content_json=json.loads(
                (FIXTURE_ROOT / "kernel_demo.extract_structured_fields_v1.json").read_text()
            )["response_json"],
            metadata={
                "artifact_role": "workflow_result",
                "workflow_id": job.workflow_id,
                "workflow_version": job.workflow_version,
                "schema_ref": schema.schema_ref,
                "schema_version": schema.version,
            },
        )
        return FinalExecutionResult(
            replace(
                job,
                status=JobStatus.succeeded,
                result_artifact_id=artifact.id,
                completed_at=utc_now(),
            ),
            artifact,
        )


def assert_meter(runtime, acceptance, state, used, reserved):
    factory, _, _ = runtime
    reservation = next(
        r for r in rows(factory, execution_reservations_table) if r["job_id"] == acceptance.job_id
    )
    table = (
        paid_allowance_usage_table
        if reservation["paid_allowance_usage_id"]
        else guest_quota_usage_table
    )
    bucket_id = reservation["paid_allowance_usage_id"] or reservation["guest_quota_usage_id"]
    bucket = next(r for r in rows(factory, table) if r["id"] == bucket_id)
    assert reservation["state"] is state
    assert (bucket["used_count"], bucket["reserved_count"]) == (used, reserved)
    return reservation


@pytest.mark.parametrize("paid", [True, False])
@pytest.mark.parametrize("completed", [True, False])
@pytest.mark.parametrize("removal", ["scenario", "association", "product"])
def test_replay_and_poll_survive_config_removal_without_new_consumption(
    runtime, paid, completed, removal
):
    factory, app, registry = runtime
    grant = allowance() if paid else None
    with transaction_boundary(factory) as session:
        first = start(session, registry, grant)
    if completed:
        worker = worker_for(runtime)
        try:
            assert asyncio.run(worker.process_job(first.job_id)).status is JobStatus.succeeded
        finally:
            worker.dispose()
    with transaction_boundary(factory) as session:
        original = start(session, registry, grant)
    event_count = len(rows(factory, event_log_table))
    drifted = without_scenario_config(registry, removal)
    with transaction_boundary(factory) as session:
        replay = start(session, drifted, grant)
        with pytest.raises(IdempotencyKeyConflictError):
            start(session, drifted, grant, input_payload={"source_text": "changed input"})
        with pytest.raises(ScenarioNotFoundError):
            start(session, drifted, grant, key="new-request")
        if paid:
            with pytest.raises(ScenarioNotFoundError):
                start(session, drifted, allowance())
    assert replay.is_replay
    assert replay.scenario_session_id == original.scenario_session_id
    assert replay.job_id == original.job_id
    assert replay.result_artifact_id == original.result_artifact_id
    assert replay.status is original.status
    assert replay.current_checkpoint_id == original.current_checkpoint_id
    assert replay.reservation == original.reservation
    assert replay.allowed_next_actions == ()

    # The client polls immediately after replay, even if the returned execution is already done.
    app.state.runtime = replace(app.state.runtime, config_registry=drifted)
    path = f"/v1/scenario-sessions/{first.scenario_session_id}"
    polled = asyncio.run(_request(app, "GET", path))
    assert polled.status_code == HTTPStatus.OK
    assert polled.json()["job_id"] == first.job_id
    assert polled.json()["result_artifact_id"] == original.result_artifact_id
    assert polled.json()["status"] == original.status.value
    assert polled.json()["allowed_next_actions"] == []
    if completed:
        result = asyncio.run(_request(app, "GET", f"/v1/results/{original.result_artifact_id}"))
        assert result.status_code == HTTPStatus.OK
        action = asyncio.run(_request(
            app, "POST", f"{path}/next-actions/copy_result",
            json={"checkpoint_id": original.current_checkpoint_id},
        ))
        assert action.status_code == HTTPStatus.NOT_FOUND
    assert_meter(
        runtime, first, ReservationState.consumed if completed else ReservationState.reserved,
        int(completed), int(not completed),
    )
    for table in (scenario_sessions_table, jobs_table, execution_reservations_table):
        assert len(rows(factory, table)) == 1
    assert len(rows(factory, event_log_table)) == event_count


@pytest.mark.parametrize("paid", [True, False])
def test_one_available_result_consumes_once_and_terminal_replays_cannot_release(runtime, paid):
    factory, _, registry = runtime
    acceptance = accepted(runtime, paid)
    final = candidate(runtime, acceptance)
    with transaction_boundary(factory) as session:
        first = finalize_success(session, acceptance.job_id, final, config_registry=registry)
        again = finalize_success(session, acceptance.job_id, final, config_registry=registry)
        release = release_execution(session, acceptance.job_id)
        result = ResultService(
            config_registry=registry,
            artifact_repository=ArtifactRepository(session),
            job_repository=JobRepository(session),
        ).get_result(final.artifact.id, tenant_id="anytoolai", region="ru")
    assert first.applied and first.became_exhausted is paid
    assert not again.applied and not again.became_exhausted and not release.applied
    assert result.output == final.artifact.content_json
    assert_meter(runtime, acceptance, ReservationState.consumed, 1, 0)
    events = rows(factory, event_log_table)
    assert sum(e["event_type"] == "workflow.succeeded" for e in events) == 1
    assert sum(e["event_type"] == "scenario.completed" for e in events) == 1
    assert all(
        e["acquisition_source"] == "kernel_demo_ce" for e in events
        if e["event_type"] in {"workflow.succeeded", "scenario.completed"}
    )


@pytest.mark.parametrize(
    "fault", ["artifact", "job", "counter", "scenario", "before_commit", "after_commit"]
)
def test_success_recovery_retains_artifact_identity_and_atomic_debit(runtime, monkeypatch, fault):
    factory, _, _ = runtime
    acceptance = accepted(runtime)
    engine = engine_from_session_factory(factory)
    recorded_artifacts = []
    original_create = ArtifactRepository.create

    def create(self, record):
        if record.metadata.get("artifact_role") == "workflow_result":
            recorded_artifacts.append(record.id)
            if fault == "artifact" and len(recorded_artifacts) == 1:
                raise RuntimeError("injected final artifact insert failure")
        return original_create(self, record)

    monkeypatch.setattr(ArtifactRepository, "create", create)
    original_complete, original_success, original_commit = (
        ScenarioSessionService.mark_completed,
        JobRepository.mark_succeeded,
        engine.dialect.do_commit,
    )
    injected = False

    def fail_once():
        nonlocal injected
        if not injected:
            injected = True
            raise RuntimeError("injected publication boundary failure")

    def complete(self, record, *, context=None):
        if fault == "scenario":
            fail_once()
        return original_complete(self, record, context=context)

    def succeed(self, record):
        if fault == "job":
            fail_once()
        return original_success(self, record)

    def before_execute(conn, cursor, statement, parameters, context, executemany):
        if fault == "counter" and statement.startswith("UPDATE platform.paid_allowance_usage"):
            fail_once()

    def commit(connection):
        # Claim commits before publication; fault only after the final candidate was reached.
        if recorded_artifacts and fault in {"before_commit", "after_commit"} and not injected:
            if fault == "after_commit":
                original_commit(connection)
            fail_once()
        return original_commit(connection)

    monkeypatch.setattr(ScenarioSessionService, "mark_completed", complete)
    monkeypatch.setattr(JobRepository, "mark_succeeded", succeed)
    monkeypatch.setattr(engine.dialect, "do_commit", commit)
    sa.event.listen(engine, "before_cursor_execute", before_execute)
    worker = worker_for(runtime)
    try:
        result = asyncio.run(worker.process_job(acceptance.job_id))
    finally:
        worker.dispose()
        sa.event.remove(engine, "before_cursor_execute", before_execute)
    assert result.status is JobStatus.succeeded
    assert set(recorded_artifacts) == {result.result_artifact_id}
    assert_meter(runtime, acceptance, ReservationState.consumed, 1, 0)
    assert rows(factory, scenario_sessions_table)[0]["status"] is ScenarioSessionStatus.completed
    events = rows(factory, event_log_table)
    for event in (
        "workflow.started", "workflow.succeeded", "scenario.completed", "quota.reserved", "quota.consumed"
    ):
        assert sum(e["event_type"] == event for e in events) == 1
    assert not any(e["event_type"] == "quota.released" for e in events)
    assert rows(factory, action_runs_table) and rows(factory, provider_calls_table)


@pytest.mark.parametrize("path", ["preclaim", "failure", "cancel", "disabled", "poison"])
@pytest.mark.parametrize("paid", [True, False])
def test_terminal_paths_release_without_publishing_success(runtime, monkeypatch, path, paid):
    factory, _, _ = runtime
    acceptance = accepted(runtime, paid)
    worker = worker_for(runtime, enabled_product_ids=frozenset() if path == "disabled" else None)
    try:
        if path == "preclaim":
            result = worker.cancel_job(acceptance.job_id)
        else:
            if path == "poison":
                with transaction_boundary(factory) as session:
                    session.execute(sa.update(jobs_table).values(frontend_id="wrong"))
            if path in {"failure", "cancel"}:

                async def fail(*args, **kwargs):
                    if path == "cancel":
                        raise asyncio.CancelledError()
                    raise RuntimeError("injected runner failure")

                monkeypatch.setattr(SequentialWorkflowRunner, "run_claimed_job", fail)
            if path == "cancel":
                with pytest.raises(asyncio.CancelledError):
                    asyncio.run(worker.process_job(acceptance.job_id))
                result = rows(factory, jobs_table)[0]
                assert result["status"] is JobStatus.canceled
            else:
                result = asyncio.run(worker.process_job(acceptance.job_id))
                assert result.status is JobStatus.failed
        assert_meter(runtime, acceptance, ReservationState.released, 0, 0)
        assert not [
            r
            for r in rows(factory, artifacts_table)
            if r["metadata"].get("artifact_role") == "workflow_result"
        ]
        with transaction_boundary(factory) as session:
            assert not release_execution(session, acceptance.job_id).applied
        quota_events = [
            e["event_type"] for e in rows(factory, event_log_table)
            if e["event_type"] in {"quota.reserved", "quota.consumed", "quota.released"}
        ]
        assert sorted(quota_events) == ["quota.released", "quota.reserved"]
    finally:
        worker.dispose()


def test_expired_scenario_wins_publication_and_cannot_be_restored_by_late_worker(runtime):
    factory, _, registry = runtime
    acceptance = accepted(runtime)
    final = candidate(runtime, acceptance)
    with transaction_boundary(factory) as session:
        session.execute(
            sa.update(scenario_sessions_table).values(status=ScenarioSessionStatus.expired)
        )
    with transaction_boundary(factory) as session:
        transition = finalize_success(session, acceptance.job_id, final, config_registry=registry)
    assert transition.applied and transition.reservation.state is ReservationState.released
    _recover_succeeded_workflow_row_after_rollback(
        factory, final.job, final_result=final, config_registry=registry
    )
    assert_meter(runtime, acceptance, ReservationState.released, 0, 0)
    assert rows(factory, artifacts_table) == []
    assert rows(factory, scenario_sessions_table)[0]["status"] is ScenarioSessionStatus.expired
    with (
        transaction_boundary(factory) as session,
        pytest.raises(ValueError, match="status changes"),
    ):
        JobRepository(session).update(replace(final.job, status=JobStatus.running))


@pytest.mark.parametrize("winner", ["success", "failure", "duplicate"])
def test_competing_terminal_transactions_have_one_decision(runtime, winner):
    factory, _, registry = runtime
    acceptance = accepted(runtime)
    final = candidate(runtime, acceptance)
    locked = threading.Event()
    release = threading.Event()

    def transition(success, wait=False):
        with transaction_boundary(factory) as session:
            job = JobRepository(session).get(acceptance.job_id, for_update=True)
            if wait:
                locked.set()
                assert release.wait(10)
            if success:
                return finalize_success(session, job.id, final, config_registry=registry)
            WorkflowJobService(
                JobRepository(session), EventEmitter(EventLogRepository(session))
            ).mark_failed(replace(job, status=JobStatus.failed), error_code="injected_failure")

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(transition, winner != "failure", True)
        assert locked.wait(10)
        second = pool.submit(transition, winner != "success")
        release.set()
        first.result(timeout=10)
        second.result(timeout=10)
    if winner != "failure":
        assert_meter(runtime, acceptance, ReservationState.consumed, 1, 0)
        _recover_failed_workflow_row_after_rollback(
            factory, replace(final.job, status=JobStatus.failed), failed_step=None
        )
        assert_meter(runtime, acceptance, ReservationState.consumed, 1, 0)
    else:
        assert_meter(runtime, acceptance, ReservationState.released, 0, 0)
        assert rows(factory, artifacts_table) == []


@pytest.mark.parametrize("invalid", ["schema", "internal_key", "provenance"])
def test_unavailable_final_candidate_never_consumes_or_publishes(runtime, invalid):
    factory, _, registry = runtime
    acceptance = accepted(runtime)
    final = candidate(runtime, acceptance)
    artifact = final.artifact
    if invalid == "schema":
        workflow = registry.get_workflow(final.job.workflow_id)
        schema = registry.get_schema(workflow.output_schema_ref)
        registry = replace(
            registry,
            schemas={
                **registry.schemas,
                schema.schema_ref: replace(
                    schema, schema={"type": "object", "required": ["expected"]}
                ),
            },
        )
    elif invalid == "internal_key":
        artifact = replace(
            artifact, content_json={**artifact.content_json, "gatewayModel": "secret"}
        )
        workflow = registry.get_workflow(final.job.workflow_id)
        schema = registry.get_schema(workflow.output_schema_ref)
        registry = replace(
            registry,
            schemas={
                **registry.schemas,
                schema.schema_ref: replace(
                    schema, schema={**schema.schema, "additionalProperties": True}
                ),
            },
        )
    else:
        artifact = replace(artifact, metadata={**artifact.metadata, "schema_version": 999})
    with pytest.raises(CanonicalArtifactError), transaction_boundary(factory) as session:
        finalize_success(
            session, acceptance.job_id, replace(final, artifact=artifact), config_registry=registry
        )
    assert_meter(runtime, acceptance, ReservationState.reserved, 0, 1)
    assert rows(factory, artifacts_table) == []


def test_failed_success_recovery_does_not_leave_free_final_artifact(runtime, monkeypatch):
    factory, _, _ = runtime
    acceptance = accepted(runtime)

    def unavailable(*args, **kwargs):
        raise RuntimeError("scenario completion storage unavailable")

    monkeypatch.setattr(ScenarioSessionService, "mark_completed", unavailable)
    worker = worker_for(runtime)
    try:
        result = asyncio.run(worker.process_job(acceptance.job_id))
    finally:
        worker.dispose()
    assert result.status is JobStatus.failed
    assert_meter(runtime, acceptance, ReservationState.released, 0, 0)
    assert not [
        r
        for r in rows(factory, artifacts_table)
        if r["metadata"].get("artifact_role") == "workflow_result"
    ]
    assert rows(factory, provider_calls_table) and rows(factory, action_runs_table)
    events = rows(factory, event_log_table)
    for event_type in (
        "workflow.started",
        "workflow.step_started",
        "action.started",
        "provider.request_started",
        "provider.request_succeeded",
        "action.succeeded",
        "workflow.step_succeeded",
        "workflow.failed",
    ):
        assert sum(e["event_type"] == event_type for e in events) == 1


@pytest.mark.parametrize("cancel", [False, True])
def test_partial_action_provider_history_survives_release_recovery(runtime, monkeypatch, cancel):
    factory, _, _ = runtime
    acceptance = accepted(runtime)

    def fail_after_actions(*args, **kwargs):
        if cancel:
            raise asyncio.CancelledError()
        raise RuntimeError("injected failure after successful actions")

    monkeypatch.setattr(SequentialWorkflowRunner, "_create_final_artifact", fail_after_actions)
    worker = worker_for(runtime)
    try:
        if cancel:
            with pytest.raises(asyncio.CancelledError):
                asyncio.run(worker.process_job(acceptance.job_id))
        else:
            assert asyncio.run(worker.process_job(acceptance.job_id)).status is JobStatus.failed
    finally:
        worker.dispose()
    assert_meter(runtime, acceptance, ReservationState.released, 0, 0)
    assert rows(factory, action_runs_table) and rows(factory, provider_calls_table)
    assert rows(factory, artifacts_table)
    events = rows(factory, event_log_table)
    assert sum(e["event_type"] == "workflow.started" for e in events) == 1
    assert (
        sum(
            e["event_type"] == ("workflow.canceled" if cancel else "workflow.failed")
            for e in events
        )
        == 1
    )
    assert not any(e["event_type"] == "workflow.succeeded" for e in events)


def test_paid_cycle_change_finishes_and_replays_on_original_bucket(runtime):
    factory, _, registry = runtime
    grant = allowance()
    with transaction_boundary(factory) as session:
        old = start(session, registry, grant)
    final = candidate(runtime, old)
    with transaction_boundary(factory) as session:
        new = start(session, registry, replace(grant, allowance_id="new-cycle"), key="new-request")
        replay = start(session, registry, replace(grant, allowance_id="new-cycle"))
        assert replay.is_replay and replay.job_id == old.job_id
        finalize_success(session, old.job_id, final, config_registry=registry)
    assert_meter(runtime, old, ReservationState.consumed, 1, 0)
    assert_meter(runtime, new, ReservationState.reserved, 0, 1)


def test_guest_legacy_usage_and_original_utc_window_are_preserved(runtime, monkeypatch):
    factory, _, registry = runtime
    product = registry.get_product("kernel_demo")
    policy = registry.get_quota_policy(product.quota_policy_ref)
    registry = replace(
        registry,
        quotas={
            **registry.quotas,
            policy.quota_policy_id: replace(policy, period=QuotaPeriod.calendar_day),
        },
    )
    now = datetime(2026, 11, 3, 23, 59, tzinfo=UTC)
    monkeypatch.setattr(quota_module, "utc_now", lambda: now)
    runtime = factory, None, registry
    with transaction_boundary(factory) as session:
        old = start(session, registry)
        session.execute(
            sa.update(guest_quota_usage_table).values(used_count=1, legacy_used_count=1)
        )
    final = candidate(runtime, old)
    now += timedelta(minutes=2)
    with transaction_boundary(factory) as session:
        new = start(session, registry, key="next-day")
        finalize_success(session, old.job_id, final, config_registry=registry)
    assert_meter(runtime, old, ReservationState.consumed, 2, 0)
    assert_meter(runtime, new, ReservationState.reserved, 0, 1)
    buckets = rows(factory, guest_quota_usage_table)
    assert {b["period_key"] for b in buckets} == {"day:2026-11-03", "day:2026-11-04"}
    assert sum(b["legacy_used_count"] for b in buckets) == 1


def test_live_lease_then_connection_loss_releases_once_and_blocks_late_success(runtime):
    factory, _, registry = runtime
    acceptance = accepted(runtime)
    final = candidate(runtime, acceptance)
    engine = engine_from_session_factory(factory)
    lease = AdvisoryJobLease(engine)
    worker = worker_for(runtime)
    assert lease.acquire(acceptance.job_id)
    try:
        assert worker._reconciler.reconcile_once() == 0
        assert_meter(runtime, acceptance, ReservationState.reserved, 0, 1)
        lease._connections[acceptance.job_id].invalidate()
        assert worker._reconciler.reconcile_once() == 1
        assert worker._reconciler.reconcile_once() == 0
        _recover_succeeded_workflow_row_after_rollback(
            factory, final.job, final_result=final, config_registry=registry
        )
        assert_meter(runtime, acceptance, ReservationState.released, 0, 0)
        assert rows(factory, artifacts_table) == []
    finally:
        lease.release(acceptance.job_id)
        worker.dispose()


def test_sigkill_claimed_worker_then_restart_reconciles_reservation(runtime, tmp_path):
    factory, _, registry = runtime
    acceptance = accepted(runtime)
    database_url = engine_from_session_factory(factory).url.render_as_string(hide_password=False)
    ready = tmp_path / "worker-claimed"
    script = f"""
import sys
import time
sys.path[:] = {sys.path!r}
from anytoolai_platform_worker.composition import build_worker
worker = build_worker(database_url={database_url!r})
claimed = worker._workflow_handler._claim({acceptance.job_id!r})
assert claimed is not None
from pathlib import Path
Path({str(ready)!r}).write_text("CLAIMED")
time.sleep(60)
"""
    process = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "LITELLM_LOCAL_MODEL_COST_MAP": "True"},
    )
    try:
        deadline = time.monotonic() + 20
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ready.exists(), "worker did not report a durable claim"
        worker = worker_for(runtime)
        try:
            assert worker._reconciler.reconcile_once() == 0
            process.kill()
            process.wait(timeout=10)
            assert worker._reconciler.reconcile_once() == 1
            assert_meter(runtime, acceptance, ReservationState.released, 0, 0)
            assert rows(factory, jobs_table)[0]["error_code"] == "worker_lease_lost"
            assert rows(factory, artifacts_table) == []
        finally:
            worker.dispose()
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)


def test_caller_rollback_reverts_publication_counters_scenario_and_events(runtime):
    factory, _, registry = runtime
    acceptance = accepted(runtime)
    final = candidate(runtime, acceptance)
    events_before = rows(factory, event_log_table)
    with (
        pytest.raises(RuntimeError, match="caller rejection"),
        transaction_boundary(factory) as session,
    ):
        finalize_success(session, acceptance.job_id, final, config_registry=registry)
        raise RuntimeError("caller rejection")
    assert_meter(runtime, acceptance, ReservationState.reserved, 0, 1)
    assert rows(factory, artifacts_table) == []
    assert rows(factory, event_log_table) == events_before
    assert rows(factory, jobs_table)[0]["status"] is JobStatus.running
    assert rows(factory, scenario_sessions_table)[0]["status"] is ScenarioSessionStatus.running


def test_expiry_committed_while_success_waits_for_scenario_lock_wins(runtime):
    factory, _, registry = runtime
    acceptance = accepted(runtime)
    final = candidate(runtime, acceptance)
    engine = engine_from_session_factory(factory)
    waiting = threading.Event()

    def observe_lock(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("SELECT platform.scenario_sessions") and "FOR UPDATE" in statement:
            waiting.set()

    def publish():
        with transaction_boundary(factory) as session:
            return finalize_success(session, acceptance.job_id, final, config_registry=registry)

    sa.event.listen(engine, "before_cursor_execute", observe_lock)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction_boundary(factory) as session:
                session.execute(
                    sa.update(scenario_sessions_table).values(status=ScenarioSessionStatus.expired)
                )
                future = pool.submit(publish)
                assert waiting.wait(10)
                assert not future.done()
            transition = future.result(timeout=10)
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe_lock)
    assert transition.reservation.state is ReservationState.released
    assert_meter(runtime, acceptance, ReservationState.released, 0, 0)
    assert rows(factory, artifacts_table) == []
    assert rows(factory, scenario_sessions_table)[0]["status"] is ScenarioSessionStatus.expired


def test_success_prevents_stale_scenario_terminal_writer_and_stale_job_update(runtime, monkeypatch):
    factory, _, registry = runtime
    acceptance = accepted(runtime)
    final = candidate(runtime, acceptance)
    with transaction_boundary(factory) as session:
        stale_scenario = ScenarioSessionRepository(session).get_in_scope(
            acceptance.scenario_session_id, tenant_id="anytoolai", region="ru"
        )
    with transaction_boundary(factory) as session:
        finalize_success(session, acceptance.job_id, final, config_registry=registry)
    with (
        pytest.raises(RuntimeError, match="already terminal"),
        transaction_boundary(factory) as session,
    ):
        ScenarioSessionRepository(session).update(
            replace(stale_scenario, status=ScenarioSessionStatus.expired),
            tenant_id="anytoolai",
            region="ru",
            product_id="kernel_demo",
            frontend_id="kernel_demo_ce",
        )
    assert_meter(runtime, acceptance, ReservationState.consumed, 1, 0)
    assert rows(factory, scenario_sessions_table)[0]["status"] is ScenarioSessionStatus.completed

    # A stale read between update's validation and SQL cannot reset terminal job state.
    original_get = JobRepository.get

    def stale_get(self, job_id, *, for_update=False):
        if job_id == acceptance.job_id:
            return replace(final.job, status=JobStatus.running)
        return original_get(self, job_id, for_update=for_update)

    monkeypatch.setattr(JobRepository, "get", stale_get)
    with (
        pytest.raises(RuntimeError, match="state changed"),
        transaction_boundary(factory) as session,
    ):
        JobRepository(session).update(replace(final.job, status=JobStatus.running))
    assert rows(factory, jobs_table)[0]["status"] is JobStatus.succeeded


@pytest.mark.parametrize("paid", [True, False])
def test_immediate_handoff_uses_same_terminal_metering(runtime, paid):
    factory, app, registry = runtime
    with transaction_boundary(factory) as session:
        source, artifact = _seed_source(session)
    created = _create(app, source, artifact).json()
    grant = allowance() if paid else None
    with transaction_boundary(factory) as session:
        result = handoff_service(session, registry).accept(
            created["handoff_token"],
            AcceptHandoffCommand("anytoolai", "ru"),
            execution_owner=None if grant is None else grant.owner,
            paid_allowance=grant,
        )
    worker = worker_for(runtime)
    try:
        terminal = asyncio.run(worker.process_job(result.preview.target_job_id))
    finally:
        worker.dispose()
    assert terminal.status is JobStatus.succeeded
    reservation = next(
        r
        for r in rows(factory, execution_reservations_table)
        if r["job_id"] == result.preview.target_job_id
    )
    assert reservation["state"] is ReservationState.consumed
    table = paid_allowance_usage_table if paid else guest_quota_usage_table
    assert (rows(factory, table)[0]["used_count"], rows(factory, table)[0]["reserved_count"]) == (
        1,
        0,
    )
    with transaction_boundary(factory) as session:
        replay = handoff_service(session, registry).accept(
            created["handoff_token"],
            AcceptHandoffCommand("anytoolai", "ru"),
            execution_owner=None if grant is None else grant.owner,
        )
    assert replay.is_replay and replay.preview.target_job_id == terminal.id
    assert len(rows(factory, execution_reservations_table)) == 1


def test_reserved_job_without_reservation_fails_closed(runtime, monkeypatch):
    factory, _, registry = runtime
    acceptance = accepted(runtime)
    final = candidate(runtime, acceptance)
    monkeypatch.setattr(ExecutionReservationRepository, "get_by_job", lambda self, job_id: None)
    with (
        pytest.raises(RuntimeError, match="lacks its reservation"),
        transaction_boundary(factory) as session,
    ):
        finalize_success(session, acceptance.job_id, final, config_registry=registry)
    assert rows(factory, artifacts_table) == []
    assert rows(factory, paid_allowance_usage_table)[0]["used_count"] == 0


@pytest.mark.parametrize("paid", [True, False])
def test_last_unit_failure_restores_capacity_then_success_exhausts_it(runtime, paid):
    factory, app, registry = runtime
    policy = registry.get_quota_policy("kernel_demo.guest_quota_v1")
    registry = replace(
        registry, quotas={**registry.quotas, policy.quota_policy_id: replace(policy, limit_count=1)}
    )
    runtime = factory, app, registry
    grant = allowance() if paid else None
    with transaction_boundary(factory) as session:
        first = start(session, registry, grant)
    failed = candidate(runtime, first)
    with transaction_boundary(factory) as session:
        WorkflowJobService(
            JobRepository(session), EventEmitter(EventLogRepository(session))
        ).mark_failed(
            replace(failed.job, status=JobStatus.failed, result_artifact_id=None),
            error_code="test_failure",
        )
    assert_meter(runtime, first, ReservationState.released, 0, 0)
    with transaction_boundary(factory) as session:
        second = start(session, registry, grant, key="second")
    final = candidate(runtime, second)
    with transaction_boundary(factory) as session:
        transition = finalize_success(session, second.job_id, final, config_registry=registry)
        assert transition.became_exhausted
    with pytest.raises(QuotaExhaustedError), transaction_boundary(factory) as session:
        start(session, registry, grant, key="third")
    assert_meter(runtime, second, ReservationState.consumed, 1, 0)
    expected_accepted_jobs = 2
    assert len(rows(factory, jobs_table)) == expected_accepted_jobs


def test_expiry_winning_success_recovery_preserves_causal_step_history(runtime, monkeypatch):
    factory, _, _ = runtime
    acceptance = accepted(runtime)
    original = runner_module.finalize_success
    first = True

    def expire_before_recovery(session, job_id, final_result, *, config_registry):
        nonlocal first
        if first:
            first = False
            raise RuntimeError("publication transaction lost")
        with transaction_boundary(factory) as expiry_session:
            expiry_session.execute(
                sa.update(scenario_sessions_table).values(status=ScenarioSessionStatus.expired)
            )
        return original(session, job_id, final_result, config_registry=config_registry)

    monkeypatch.setattr(runner_module, "finalize_success", expire_before_recovery)
    worker = worker_for(runtime)
    try:
        result = asyncio.run(worker.process_job(acceptance.job_id))
    finally:
        worker.dispose()
    assert result.status is JobStatus.failed
    assert_meter(runtime, acceptance, ReservationState.released, 0, 0)
    assert rows(factory, scenario_sessions_table)[0]["status"] is ScenarioSessionStatus.expired
    assert not [
        r
        for r in rows(factory, artifacts_table)
        if r["metadata"].get("artifact_role") == "workflow_result"
    ]
    events = rows(factory, event_log_table)
    for event_type in (
        "workflow.started",
        "workflow.step_started",
        "workflow.step_succeeded",
        "action.started",
        "action.succeeded",
        "provider.request_succeeded",
        "workflow.failed",
    ):
        assert sum(e["event_type"] == event_type for e in events) == 1
