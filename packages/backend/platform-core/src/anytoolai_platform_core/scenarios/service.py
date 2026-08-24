from __future__ import annotations

import json
import os
import secrets
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from sqlalchemy.exc import IntegrityError

from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.common.hashing import digest_parts
from anytoolai_platform_core.common.metadata import metadata_str
from anytoolai_platform_core.common.ids import new_id
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.products.models import FrontendDefinition
from anytoolai_platform_core.quotas.service import GuestQuotaService
from anytoolai_platform_core.scenarios.checkpoints import (
    FAILED_CHECKPOINT_ID,
    HANDOFF_READY_CHECKPOINT_ID,
    PROCESSING_CHECKPOINT_ID,
    RESULT_READY_CHECKPOINT_ID,
    resolve_checkpoint_state,
    resolve_effective_status,
)
from anytoolai_platform_core.scenarios.models import (
    LinkedScenarioSessionResult,
    ScenarioDefinition,
    ScenarioSessionRecord,
    ScenarioSessionSnapshot,
    ScenarioSessionStatus,
)
from anytoolai_platform_core.scenarios.next_actions import (
    ScenarioCheckpointNotActionableError,
    validate_next_action,
)
from anytoolai_platform_core.scenarios.repository import (
    MAX_IDEMPOTENCY_KEY_LENGTH,
    ScenarioSessionRepository,
    is_expected_idempotency_race,
)
from anytoolai_platform_core.workflows.models import JobRecord
from anytoolai_platform_core.workflows.repository import JobRepository


class ScenarioNotFoundError(PlatformError):
    def __init__(self) -> None:
        super().__init__("scenario_not_found", "Scenario not found.")


class ScenarioSessionNotFoundError(PlatformError):
    def __init__(self) -> None:
        super().__init__("scenario_session_not_found", "Scenario session not found.")


class ScenarioFrontendInvalidError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "scenario_frontend_invalid",
            "Frontend is not enabled for this product scenario.",
        )


class ScenarioInputInvalidError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "scenario_input_invalid",
            "Scenario input must be a JSON object.",
        )


class IdempotencyKeyConflictError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "idempotency_key_conflict",
            "Idempotency-Key was already used with a different request.",
        )


class IdempotencyKeyInvalidError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "idempotency_key_invalid",
            f"Idempotency-Key must be at most {MAX_IDEMPOTENCY_KEY_LENGTH} characters.",
        )


LIVE_CANARY_TOKEN_ENV_VAR = "ANYTOOLAI_LIVE_CANARY_TOKEN"


def _live_canary_token_is_valid(provided: str | None) -> bool:
    """Gate for ScenarioDefinition.internal_only (ANY-221's 14 kernel_demo "_live_" canary
    scenarios, real billed OpenAI calls) -- see start_session()'s own check. Fails closed: if the
    server itself hasn't been configured with a real ANYTOOLAI_LIVE_CANARY_TOKEN, nothing can ever
    match it, so an unconfigured deployment can never accidentally serve an internal_only scenario
    to any caller. secrets.compare_digest avoids a timing side-channel on the comparison, the same
    reasoning any secret-token check gets."""
    configured = os.environ.get(LIVE_CANARY_TOKEN_ENV_VAR, "")
    if not configured or not provided:
        return False
    return secrets.compare_digest(configured, provided)


class ScenarioRuntimeService:
    def __init__(
        self,
        *,
        config_registry: ConfigRegistry,
        session_repository: ScenarioSessionRepository,
        session_service: ScenarioSessionService,
        job_repository: JobRepository,
        event_emitter: EventEmitter,
        quota_service: GuestQuotaService | None = None,
    ) -> None:
        self._config_registry = config_registry
        self._session_repository = session_repository
        self._session_service = session_service
        self._job_repository = job_repository
        self._event_emitter = event_emitter
        self._quota_service = quota_service

    def start_session(
        self,
        *,
        tenant_id: str,
        region: str,
        product_id: str,
        scenario_id: str,
        frontend_id: str,
        input_payload: Mapping[str, Any],
        guest_id: str | None = None,
        user_id: str | None = None,
        source_frontend_instance_id: str | None = None,
        idempotency_key: str | None = None,
        live_canary_token: str | None = None,
    ) -> ScenarioSessionSnapshot:
        # An empty or whitespace-only header (e.g. a proxy sending "Idempotency-Key: ")
        # must mean "no key was sent", not a real, distinct empty-string key -- two
        # different callers both sending a blank header would otherwise be scoped
        # together as if they shared one key.
        if idempotency_key is not None:
            idempotency_key = idempotency_key.strip() or None
        if idempotency_key is not None and len(idempotency_key) > MAX_IDEMPOTENCY_KEY_LENGTH:
            raise IdempotencyKeyInvalidError()

        if not isinstance(input_payload, Mapping):
            raise ScenarioInputInvalidError()

        idempotency_request_hash = (
            None
            if idempotency_key is None
            else compute_idempotency_request_hash(
                tenant_id=tenant_id,
                region=region,
                product_id=product_id,
                scenario_id=scenario_id,
                frontend_id=frontend_id,
                guest_id=guest_id,
                user_id=user_id,
                input_payload=input_payload,
            )
        )

        # A replay of an already-accepted start must survive config drift since the
        # original request: the frontend can be disabled, the quota policy
        # reconfigured/broken, or the guest identity removed in between -- none of
        # that may block a legitimate retry (browser back-button, fetch-timeout retry,
        # flaky mobile network -- exactly the cases Idempotency-Key exists for). Look
        # up an existing match on the raw, unvalidated identifiers *before* running
        # any product/scenario/frontend/quota validation, which only a genuinely new
        # request still needs. get_by_idempotency_key() only needs tenant/region/
        # product/scenario/guest_id/idempotency_key, none of which require resolving
        # config first.
        existing = (
            self._session_repository.get_by_idempotency_key(
                tenant_id=tenant_id,
                region=region,
                product_id=product_id,
                scenario_id=scenario_id,
                guest_id=guest_id,
                idempotency_key=idempotency_key,
            )
            if idempotency_key is not None
            else None
        )
        if existing is not None:
            if existing.idempotency_request_hash != idempotency_request_hash:
                raise IdempotencyKeyConflictError()
            return self._replay_snapshot(existing)

        scenario = self._require_product_scenario(product_id, scenario_id)
        # ANY-221: internal_only scenarios (the 14 kernel_demo "_live_" canary scenarios) exist
        # only for scripts/agent/live_canary.py's own cost-capped, credentialed-gated CLI, not the
        # normal public start-session API any frontend/Chrome-extension client also reaches through
        # this same method -- without this, that public path bypasses live_canary.py's $0.50 cost
        # cap and OPENAI_API_KEY fail-fast entirely (both exist only in that CLI). Raises the same
        # ScenarioNotFoundError an unknown scenario_id would -- a caller without the right token
        # can't distinguish "doesn't exist" from "exists but is internal-only".
        if scenario.internal_only and not _live_canary_token_is_valid(live_canary_token):
            raise ScenarioNotFoundError()
        self._require_enabled_frontend(product_id, frontend_id)

        workflow = self._config_registry.get_workflow(scenario.workflow_id)
        if workflow is None:
            raise LookupError(f"workflow not found: {scenario.workflow_id}")

        scenario_session_id = new_id("scenario_session")
        session_record = ScenarioSessionRecord(
            id=scenario_session_id,
            tenant_id=tenant_id,
            region=region,
            product_id=product_id,
            frontend_id=frontend_id,
            scenario_id=scenario.scenario_id,
            scenario_version=scenario.version,
            guest_id=guest_id,
            user_id=user_id,
            status=ScenarioSessionStatus.started,
            current_checkpoint_id=PROCESSING_CHECKPOINT_ID,
            scenario_chain_id=scenario_session_id,
            source_frontend_instance_id=source_frontend_instance_id,
            idempotency_key=idempotency_key,
            idempotency_request_hash=idempotency_request_hash,
            metadata={"input": dict(input_payload)},
        )

        # Validate guest identity/quota policy before any write: consume_for_accepted_start()
        # now requires this result as a parameter, so it is structurally impossible to
        # reach quota consumption without validating first. Doing this before the
        # insert-or-select means a request with an invalid/missing/unknown guest_id
        # fails fast without ever inserting a scenario_sessions row (and the event it
        # would emit) that would just be rolled back a moment later.
        quota_validation = (
            self._quota_service.validate_accepted_start(
                tenant_id=tenant_id,
                region=region,
                product_id=product_id,
                guest_id=guest_id,
                scenario_id=scenario.scenario_id,
            )
            if self._quota_service is not None
            else None
        )

        # The atomic insert-or-select must run before quota consumption: it is the
        # only thing that can tell N concurrent requests sharing one Idempotency-Key
        # apart from N genuinely distinct requests (the lookup above only closes the
        # common sequential-replay case; two concurrent requests for a brand-new key
        # can both miss it and reach here). Gating quota on its outcome means a losing
        # duplicate never touches quota at all, instead of racing to consume it and
        # needing a refund. If quota is exhausted after a fresh insert here, this
        # error propagates uncaught so the caller's transaction rolls back the insert
        # (and its scenario.started event) via normal DB rollback, while
        # GuestQuotaService's already-registered rollback-recovery callback persists
        # the quota-exhaustion audit trail in an independent transaction.
        stored_session, inserted = self._session_service.start_or_get_existing(session_record)

        if not inserted:
            if (
                idempotency_key is not None
                and stored_session.idempotency_request_hash != idempotency_request_hash
            ):
                raise IdempotencyKeyConflictError()
            # Re-resolve from the row that actually won the race, not the `scenario`
            # this (losing) request resolved a moment ago: under a rolling config
            # deploy that bumps the scenario version between the two concurrent
            # requests, the winner's stored_session.scenario_version can differ from
            # this request's locally-resolved scenario.version.
            return self._replay_snapshot(stored_session)

        if self._quota_service is not None and quota_validation is not None:
            assert guest_id is not None  # validate_accepted_start already required this
            self._quota_service.consume_for_accepted_start(
                tenant_id=tenant_id,
                region=region,
                product_id=product_id,
                frontend_id=frontend_id,
                guest_id=guest_id,
                scenario_id=scenario.scenario_id,
                scenario_session_id=stored_session.id,
                scenario_chain_id=stored_session.scenario_chain_id,
                validation=quota_validation,
            )

        job = self._job_repository.create(
            JobRecord(
                tenant_id=tenant_id,
                region=region,
                product_id=product_id,
                frontend_id=frontend_id,
                scenario_session_id=stored_session.id,
                workflow_id=workflow.workflow_id,
                workflow_version=workflow.version,
                metadata={
                    "guest_id": guest_id,
                    "user_id": user_id,
                    "scenario_chain_id": stored_session.scenario_chain_id,
                    "acquisition_source": frontend_id,
                },
            )
        )

        return self._snapshot_from_records(
            session=stored_session,
            scenario=scenario,
            job=job,
        )

    def _replay_snapshot(self, session: ScenarioSessionRecord) -> ScenarioSessionSnapshot:
        # Deliberately unpinned: a replay must survive config drift, including the
        # scenario's own configured version moving on since the original accepted
        # start (an ordinary config deploy, not a code change). Pinning to
        # session.scenario_version here would 404 every replay of a session whose
        # scenario was since bumped -- exactly the retry case Idempotency-Key exists
        # for. scenario is only used below for allowed_next_actions on an
        # already-completed session; a version-drifted value there is a much smaller,
        # cosmetic risk than failing the replay outright.
        scenario = self._require_product_scenario(session.product_id, session.scenario_id)
        job = self._job_repository.get_latest_for_scenario_session(session.id)
        return self._snapshot_from_records(
            session=session,
            scenario=scenario,
            job=job,
        )

    def create_linked_session(
        self,
        *,
        tenant_id: str,
        region: str,
        product_id: str,
        scenario_id: str,
        frontend_id: str,
        input_payload: Mapping[str, Any],
        scenario_session_id: str,
        scenario_chain_id: str,
        parent_scenario_session_id: str,
        handoff_id: str,
        source_artifact_id: str,
        guest_id: str | None,
        user_id: str | None,
        source_frontend_instance_id: str | None,
        queue_workflow: bool,
    ) -> LinkedScenarioSessionResult:
        scenario = self._require_product_scenario(product_id, scenario_id)
        # ANY-221: no legitimate handoff ever targets an internal_only (live-canary) scenario --
        # unlike start_session(), there's no live_canary_token to check here at all, since
        # live_canary.py never creates linked/handoff sessions; this path is always rejected.
        if scenario.internal_only:
            raise ScenarioNotFoundError()
        self._require_enabled_frontend(product_id, frontend_id)
        if not isinstance(input_payload, Mapping):
            raise ScenarioInputInvalidError()
        workflow = self._config_registry.get_workflow(scenario.workflow_id)
        if workflow is None:
            raise LookupError(f"workflow not found: {scenario.workflow_id}")

        if queue_workflow and self._quota_service is not None:
            quota_validation = self._quota_service.validate_accepted_start(
                tenant_id=tenant_id,
                region=region,
                product_id=product_id,
                guest_id=guest_id,
                scenario_id=scenario.scenario_id,
            )
            if quota_validation is not None:
                assert guest_id is not None  # validate_accepted_start already required this
                self._quota_service.consume_for_accepted_start(
                    tenant_id=tenant_id,
                    region=region,
                    product_id=product_id,
                    frontend_id=frontend_id,
                    guest_id=guest_id,
                    scenario_id=scenario.scenario_id,
                    scenario_session_id=scenario_session_id,
                    scenario_chain_id=scenario_chain_id,
                    handoff_id=handoff_id,
                    validation=quota_validation,
                )

        session_record = ScenarioSessionRecord(
            id=scenario_session_id,
            tenant_id=tenant_id,
            region=region,
            product_id=product_id,
            frontend_id=frontend_id,
            scenario_id=scenario.scenario_id,
            scenario_version=scenario.version,
            guest_id=guest_id,
            user_id=user_id,
            status=(
                ScenarioSessionStatus.started
                if queue_workflow
                else ScenarioSessionStatus.waiting_for_user
            ),
            current_checkpoint_id=(
                PROCESSING_CHECKPOINT_ID if queue_workflow else HANDOFF_READY_CHECKPOINT_ID
            ),
            scenario_chain_id=scenario_chain_id,
            parent_scenario_session_id=parent_scenario_session_id,
            source_frontend_instance_id=source_frontend_instance_id,
            metadata={
                "input": dict(input_payload),
                "handoff_id": handoff_id,
                "source_scenario_session_id": parent_scenario_session_id,
                "source_artifact_id": source_artifact_id,
            },
        )
        event_context = ExecutionContext(
            tenant_id=tenant_id,
            region=region,
            product_id=product_id,
            frontend_id=frontend_id,
            scenario_session_id=scenario_session_id,
            scenario_chain_id=scenario_chain_id,
            guest_id=guest_id,
            user_id=user_id,
            handoff_id=handoff_id,
            acquisition_source=frontend_id,
        )
        stored_session = self._session_service.start(session_record, context=event_context)
        if not queue_workflow:
            return LinkedScenarioSessionResult(session=stored_session)

        job = self._job_repository.create(
            JobRecord(
                tenant_id=tenant_id,
                region=region,
                product_id=product_id,
                frontend_id=frontend_id,
                scenario_session_id=stored_session.id,
                workflow_id=workflow.workflow_id,
                workflow_version=workflow.version,
                metadata={
                    "guest_id": guest_id,
                    "user_id": user_id,
                    "scenario_chain_id": scenario_chain_id,
                    "handoff_id": handoff_id,
                    "acquisition_source": frontend_id,
                },
            )
        )
        return LinkedScenarioSessionResult(session=stored_session, job=job)

    def get_session_snapshot(
        self,
        scenario_session_id: str,
        *,
        tenant_id: str,
        region: str,
    ) -> ScenarioSessionSnapshot:
        session = self._session_repository.get_in_scope(
            scenario_session_id,
            tenant_id=tenant_id,
            region=region,
        )
        if session is None:
            raise ScenarioSessionNotFoundError()
        job = self._job_repository.get_latest_for_scenario_session(session.id)
        scenario = self._require_product_scenario(
            session.product_id,
            session.scenario_id,
            scenario_version=session.scenario_version,
        )
        return self._snapshot_from_records(
            session=session,
            scenario=scenario,
            job=job,
        )

    def record_next_action(
        self,
        scenario_session_id: str,
        *,
        tenant_id: str,
        region: str,
        next_action_id: str,
        checkpoint_id: str,
    ) -> ScenarioSessionSnapshot:
        session = self._session_repository.get_in_scope(
            scenario_session_id,
            tenant_id=tenant_id,
            region=region,
        )
        if session is None:
            raise ScenarioSessionNotFoundError()
        job = self._job_repository.get_latest_for_scenario_session(session.id)
        scenario = self._require_product_scenario(
            session.product_id,
            session.scenario_id,
            scenario_version=session.scenario_version,
        )
        checkpoint_state = resolve_checkpoint_state(
            scenario=scenario,
            session=session,
            job=job,
        )
        validate_next_action(
            expected_checkpoint_id=checkpoint_id,
            current_checkpoint=checkpoint_state,
            next_action_id=next_action_id,
        )
        if job is None:
            raise ScenarioCheckpointNotActionableError()
        self._event_emitter.emit(
            "client.next_action_clicked",
            ExecutionContext(
                tenant_id=session.tenant_id,
                region=session.region,
                product_id=session.product_id,
                frontend_id=session.frontend_id,
                scenario_session_id=session.id,
                scenario_chain_id=session.scenario_chain_id,
                guest_id=session.guest_id,
                user_id=session.user_id,
                job_id=job.id,
                workflow_id=job.workflow_id,
                workflow_version=job.workflow_version,
                acquisition_source=metadata_str(job.metadata, "acquisition_source")
                or session.frontend_id,
            ),
            properties={
                "checkpoint_id": checkpoint_state.checkpoint_id,
                "next_action_id": next_action_id,
            },
        )
        return self._snapshot_from_records(
            session=session,
            scenario=scenario,
            job=job,
        )

    def _snapshot_from_records(
        self,
        *,
        session: ScenarioSessionRecord,
        scenario: ScenarioDefinition,
        job: JobRecord | None,
    ) -> ScenarioSessionSnapshot:
        checkpoint_state = resolve_checkpoint_state(
            scenario=scenario,
            session=session,
            job=job,
        )
        return ScenarioSessionSnapshot(
            scenario_session_id=session.id,
            job_id=None if job is None else job.id,
            status=resolve_effective_status(session=session, job=job),
            allowed_next_actions=checkpoint_state.allowed_next_actions,
            result_artifact_id=None if job is None else job.result_artifact_id,
            current_checkpoint_id=checkpoint_state.checkpoint_id,
        )

    def _require_product_scenario(
        self,
        product_id: str,
        scenario_id: str,
        *,
        scenario_version: int | None = None,
    ) -> ScenarioDefinition:
        product = self._config_registry.get_product(product_id)
        scenario = self._config_registry.get_scenario(scenario_id)
        if product is None or scenario is None:
            raise ScenarioNotFoundError()
        if scenario_id not in product.scenarios:
            raise ScenarioNotFoundError()
        if scenario_version is not None and scenario.version != scenario_version:
            raise ScenarioNotFoundError()
        return scenario

    def _require_enabled_frontend(
        self,
        product_id: str,
        frontend_id: str,
    ) -> FrontendDefinition:
        product = self._config_registry.get_product(product_id)
        if product is None:
            raise ScenarioNotFoundError()
        for frontend in product.frontends:
            if frontend.frontend_id == frontend_id and frontend.enabled:
                return frontend
        raise ScenarioFrontendInvalidError()


class ScenarioSessionService:
    def __init__(
        self,
        repository: ScenarioSessionRepository,
        event_emitter: EventEmitter,
    ) -> None:
        self._repository = repository
        self._event_emitter = event_emitter

    def start(
        self,
        record: ScenarioSessionRecord,
        *,
        context: ExecutionContext | None = None,
    ) -> ScenarioSessionRecord:
        stored = self._repository.create(record)
        self._event_emitter.emit(
            "scenario.started",
            _event_context_from_record(stored, context),
            properties={
                "scenario_id": stored.scenario_id,
                "scenario_version": stored.scenario_version,
            },
        )
        return stored

    def start_or_get_existing(
        self,
        record: ScenarioSessionRecord,
        *,
        context: ExecutionContext | None = None,
    ) -> tuple[ScenarioSessionRecord, bool]:
        """Insert-or-select on the idempotency-key uniqueness constraint.

        Returns (session, inserted) -- inserted is True only when this call created the
        row and therefore emitted scenario.started; a replay of an existing key must not
        re-emit the event or let the caller re-consume quota.

        Deliberately does not do its own optimistic pre-read: ScenarioRuntimeService.
        start_session() is this method's only caller, and it already does an
        equivalent get_by_idempotency_key() lookup immediately before calling this
        (to let a sequential replay skip validation/quota entirely, not just skip the
        insert) -- a second identical SELECT here would be redundant on every call. A
        true sequential duplicate that somehow still reaches this point (or a genuine
        concurrent race) is caught below via the INSERT's own IntegrityError, which
        this repository's constraint guarantees will fire.
        """
        if record.idempotency_key is None:
            return self.start(record, context=context), True

        try:
            with self._repository.session.begin_nested():
                stored = self._repository.create(record)
        except IntegrityError as exc:
            if not is_expected_idempotency_race(exc):
                raise
            raced = self._repository.get_by_idempotency_key(
                tenant_id=record.tenant_id,
                region=record.region,
                product_id=record.product_id,
                scenario_id=record.scenario_id,
                guest_id=record.guest_id,
                idempotency_key=record.idempotency_key,
            )
            if raced is None:
                raise RuntimeError(
                    "scenario session idempotency race but no row found: "
                    f"{record.id}"
                ) from exc
            return raced, False

        self._event_emitter.emit(
            "scenario.started",
            _event_context_from_record(stored, context),
            properties={
                "scenario_id": stored.scenario_id,
                "scenario_version": stored.scenario_version,
            },
        )
        return stored, True

    def checkpoint(
        self,
        record: ScenarioSessionRecord,
        *,
        checkpoint_id: str,
        properties: dict[str, Any] | None = None,
    ) -> ScenarioSessionRecord:
        updated = self._repository.update(
            replace(
                record,
                current_checkpoint_id=checkpoint_id,
                last_event_at=utc_now(),
            ),
            tenant_id=record.tenant_id,
            region=record.region,
            product_id=record.product_id,
            frontend_id=record.frontend_id,
        )
        event_properties = dict(properties or {})
        event_properties["checkpoint_id"] = checkpoint_id
        self._event_emitter.emit(
            "scenario.checkpoint_reached",
            _context_from_record(updated),
            properties=event_properties,
        )
        return updated

    def mark_running(self, record: ScenarioSessionRecord) -> ScenarioSessionRecord:
        running_record = replace(
            record,
            status=ScenarioSessionStatus.running,
            current_checkpoint_id=record.current_checkpoint_id or PROCESSING_CHECKPOINT_ID,
            last_event_at=utc_now(),
        )
        return self._repository.update(
            running_record,
            tenant_id=record.tenant_id,
            region=record.region,
            product_id=record.product_id,
            frontend_id=record.frontend_id,
        )

    def mark_completed(
        self,
        record: ScenarioSessionRecord,
        *,
        context: ExecutionContext | None = None,
    ) -> ScenarioSessionRecord:
        updated = self._repository.update(
            replace(
                record,
                status=ScenarioSessionStatus.completed,
                current_checkpoint_id=RESULT_READY_CHECKPOINT_ID,
                completed_at=record.completed_at or utc_now(),
                last_event_at=utc_now(),
            ),
            tenant_id=record.tenant_id,
            region=record.region,
            product_id=record.product_id,
            frontend_id=record.frontend_id,
        )
        event_context = _event_context_from_record(updated, context)
        if record.current_checkpoint_id != RESULT_READY_CHECKPOINT_ID:
            self._event_emitter.emit(
                "scenario.checkpoint_reached",
                event_context,
                properties={
                    "checkpoint_id": RESULT_READY_CHECKPOINT_ID,
                    "scenario_id": updated.scenario_id,
                    "scenario_version": updated.scenario_version,
                },
            )
        self._event_emitter.emit(
            "scenario.completed",
            event_context,
            result_status=updated.status.value,
            properties={
                "scenario_id": updated.scenario_id,
                "scenario_version": updated.scenario_version,
            },
        )
        return updated

    def mark_failed(
        self,
        record: ScenarioSessionRecord,
        *,
        error_code: str,
        context: ExecutionContext | None = None,
    ) -> ScenarioSessionRecord:
        updated = self._repository.update(
            replace(
                record,
                status=ScenarioSessionStatus.failed,
                current_checkpoint_id=FAILED_CHECKPOINT_ID,
                completed_at=record.completed_at or utc_now(),
                last_event_at=utc_now(),
            ),
            tenant_id=record.tenant_id,
            region=record.region,
            product_id=record.product_id,
            frontend_id=record.frontend_id,
        )
        event_context = _event_context_from_record(updated, context)
        if record.current_checkpoint_id != FAILED_CHECKPOINT_ID:
            self._event_emitter.emit(
                "scenario.checkpoint_reached",
                event_context,
                properties={
                    "checkpoint_id": FAILED_CHECKPOINT_ID,
                    "error_code": error_code,
                    "scenario_id": updated.scenario_id,
                    "scenario_version": updated.scenario_version,
                },
            )
        self._event_emitter.emit(
            "scenario.failed",
            event_context,
            result_status=updated.status.value,
            properties={
                "error_code": error_code,
                "scenario_id": updated.scenario_id,
                "scenario_version": updated.scenario_version,
            },
        )
        return updated


def compute_idempotency_request_hash(
    *,
    tenant_id: str,
    region: str,
    product_id: str,
    scenario_id: str,
    frontend_id: str,
    guest_id: str | None,
    user_id: str | None,
    input_payload: Mapping[str, Any],
) -> str:
    """Hash the parts of a scenario-start request that must match on replay.

    source_frontend_instance_id is deliberately excluded: it identifies where the
    request came from (telemetry/origin), not what the request asks for, so a retry
    from a second tab with the same Idempotency-Key must still be treated as the same
    logical request rather than a hash-mismatch conflict.
    """
    try:
        canonical_input = json.dumps(dict(input_payload), sort_keys=True, separators=(",", ":"))
    except TypeError as exc:
        # isinstance(input_payload, Mapping) only guarantees the container shape, not
        # that every value inside it is JSON-serializable (e.g. a datetime or a
        # custom object). Surface the same safe validation error the caller already
        # raises for a non-Mapping payload instead of an unhandled TypeError.
        raise ScenarioInputInvalidError() from exc
    return digest_parts(
        tenant_id,
        region,
        product_id,
        scenario_id,
        frontend_id,
        guest_id or "",
        user_id or "",
        canonical_input,
    )


def _context_from_record(record: ScenarioSessionRecord) -> ExecutionContext:
    return ExecutionContext(
        tenant_id=record.tenant_id,
        region=record.region,
        product_id=record.product_id,
        frontend_id=record.frontend_id,
        scenario_session_id=record.id,
        guest_id=record.guest_id,
        user_id=record.user_id,
        scenario_chain_id=record.scenario_chain_id,
    )


def _event_context_from_record(
    record: ScenarioSessionRecord,
    context: ExecutionContext | None,
) -> ExecutionContext:
    event_context = _context_from_record(record)
    if context is None:
        return event_context
    return replace(
        event_context,
        job_id=context.job_id,
        workflow_id=context.workflow_id,
        workflow_version=context.workflow_version,
        handoff_id=context.handoff_id,
        acquisition_source=context.acquisition_source,
    )
