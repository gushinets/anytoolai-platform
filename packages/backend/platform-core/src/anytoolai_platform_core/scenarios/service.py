from __future__ import annotations

import json
import os
import secrets
from collections.abc import Mapping
from dataclasses import asdict, replace
from typing import Any

from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as validate_json_schema
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.common.hashing import digest_parts
from anytoolai_platform_core.common.ids import new_id
from anytoolai_platform_core.common.metadata import metadata_str
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.products.models import FrontendDefinition
from anytoolai_platform_core.quotas.execution_repository import (
    ExecutionReservationRepository,
    is_expected_execution_replay_race,
)
from anytoolai_platform_core.quotas.execution_service import (
    ExecutionReservationService,
    PaidAllowanceInvalidError,
)
from anytoolai_platform_core.quotas.models import (
    ExecutionAcceptance,
    ExecutionCandidate,
    ExecutionOwner,
    ExecutionOwnerKind,
    ExecutionReplayIdentity,
    ExecutionReplayNamespace,
    ExecutionReservation,
    PaidAllowance,
)
from anytoolai_platform_core.quotas.service import (
    GuestIdentityRequiredError,
    GuestQuotaService,
    QuotaValidation,
)
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
from anytoolai_platform_core.scenarios.runtime_scope import (
    RuntimeScope,
    runtime_scope_metadata,
)
from anytoolai_platform_core.structured_output.schemas import normalize_schema_mapping
from anytoolai_platform_core.workflows.models import (
    JobConsumptionMode,
    JobRecord,
    WorkflowDefinition,
)
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
    def __init__(self, message: str = "Scenario input must be a JSON object.") -> None:
        super().__init__("scenario_input_invalid", message)


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
        self._reservations = ExecutionReservationService(config_registry, quota_service)

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
        runtime_scope: RuntimeScope = RuntimeScope.public,
        execution_owner: ExecutionOwner | None = None,
        paid_allowance: PaidAllowance | None = None,
    ) -> ExecutionAcceptance:
        idempotency_key = _normalize_idempotency_key(idempotency_key)

        if not isinstance(input_payload, Mapping):
            raise ScenarioInputInvalidError()

        owner = self._execution_owner(tenant_id, region, guest_id, execution_owner)
        paid = owner is not None and owner.owner_kind is ExecutionOwnerKind.portal_user
        guest_id = None if paid else guest_id
        user_id = owner.owner_id if paid else user_id
        _require_paid_start_inputs(paid, paid_allowance, idempotency_key)
        replay_identity = (
            None
            if idempotency_key is None
            else ExecutionReplayIdentity(
                product_id, scenario_id, ExecutionReplayNamespace.start, idempotency_key
            )
        )
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
                user_id=None if paid else user_id,
                input_payload=input_payload,
                runtime_scope=runtime_scope,
            )
        )

        # code-review (2026-08-24) finding: an idempotency-key replay below returns a
        # snapshot before the internal_only/live_canary_token check further down ever runs, so a
        # caller who ever learns (or brute-forces, within the same guest_id scope) a valid
        # idempotency_key for an internal_only scenario could replay it without the token.
        # live_canary.py itself never sends Idempotency-Key today, so this can't fire in
        # practice yet, but checking it here (before touching idempotency at all) closes the gap
        # regardless of how any future caller behaves. A bare config peek, not
        # _require_product_scenario() (which raises on an unknown/removed scenario_id) -- an
        # idempotency replay of a session whose scenario has since been removed from config must
        # keep the config-drift tolerance the comment below describes, not fail here instead.
        early_scenario = self._config_registry.get_scenario(scenario_id)
        if (
            early_scenario is not None
            and early_scenario.internal_only
            and not _live_canary_token_is_valid(live_canary_token)
        ):
            raise ScenarioNotFoundError()

        if replay_identity is not None:
            replay = (
                self.find_execution_replay(
                    self._session_repository.session,
                    owner,
                    replay_identity,
                    idempotency_request_hash,
                )
                if owner is not None
                else self._find_legacy_replay(
                    tenant_id,
                    region,
                    None,
                    replay_identity,
                    idempotency_request_hash,
                )
            )
            if replay is not None:
                return replay

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
        self._require_valid_workflow_input(workflow, input_payload)

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
            idempotency_key=None if paid else idempotency_key,
            idempotency_request_hash=None if paid else idempotency_request_hash,
            metadata={
                "input": dict(input_payload),
                **runtime_scope_metadata(runtime_scope),
            },
        )

        quota_input = self._quota_input(
            owner=owner,
            paid_allowance=paid_allowance,
            tenant_id=tenant_id,
            region=region,
            product_id=product_id,
            scenario_id=scenario.scenario_id,
            guest_id=guest_id,
        )
        try:
            # Include events, session, job, bucket and reserve in the same candidate savepoint.
            with self._session_repository.session.begin_nested():
                stored_session = self._session_service.start(session_record)
                job, reservation = self._create_execution_job(
                    stored_session,
                    workflow,
                    owner,
                    quota_input,
                    replay_identity,
                    idempotency_request_hash,
                )
        except IntegrityError as exc:
            if not (is_expected_idempotency_race(exc) or is_expected_execution_replay_race(exc)):
                raise
            if owner is None or replay_identity is None:
                raise
            replay = self.find_execution_replay(
                self._session_repository.session, owner, replay_identity, idempotency_request_hash
            )
            if replay is None:
                raise RuntimeError("execution replay race without a durable winner") from exc
            return replay
        return self._acceptance_snapshot(stored_session, scenario, job, reservation=reservation)

    def find_execution_replay(
        self,
        session: Session,
        owner: ExecutionOwner,
        replay_identity: ExecutionReplayIdentity,
        request_hash: str,
    ) -> ExecutionAcceptance | None:
        if session is not self._session_repository.session:
            raise ValueError("replay must use the runtime's caller-owned Session")
        reservations = ExecutionReservationRepository(session)
        reservation = reservations.find_replay(
            owner=owner,
            product_id=replay_identity.product_id,
            scenario_id=replay_identity.scenario_id,
            namespace=replay_identity.namespace,
            replay_key=replay_identity.replay_key,
        )
        if reservation is not None:
            if reservation.request_hash != request_hash:
                raise IdempotencyKeyConflictError()
            stored = self._session_repository.get_in_scope(
                reservation.scenario_session_id, tenant_id=owner.tenant_id, region=owner.region
            )
            job = self._job_repository.get(reservation.job_id)
            if stored is None or job is None:
                raise RuntimeError("reservation lost its execution linkage")
            scenario = self._find_product_scenario(stored.product_id, stored.scenario_id)
            return self._acceptance_snapshot(
                stored, scenario, job, reservation=reservation, is_replay=True
            )
        # Historical guest requests have no reservation. Never search guest_id=NULL for paid.
        if (
            owner.owner_kind is ExecutionOwnerKind.guest
            and replay_identity.namespace is ExecutionReplayNamespace.start
        ):
            return self._find_legacy_replay(
                owner.tenant_id,
                owner.region,
                owner.owner_id,
                replay_identity,
                request_hash,
            )
        return None

    def _find_legacy_replay(
        self,
        tenant_id: str,
        region: str,
        guest_id: str | None,
        identity: ExecutionReplayIdentity,
        request_hash: str,
    ) -> ExecutionAcceptance | None:
        # NULL guest lookup is retained only for untrusted historical/unmetered requests.
        # Authenticated paid replay always uses reservation ownership instead.
        stored = self._session_repository.get_by_idempotency_key(
            tenant_id=tenant_id,
            region=region,
            product_id=identity.product_id,
            scenario_id=identity.scenario_id,
            guest_id=guest_id,
            idempotency_key=identity.replay_key,
        )
        if stored is None:
            return None
        if stored.idempotency_request_hash != request_hash:
            raise IdempotencyKeyConflictError()
        job = self._job_repository.get_latest_for_scenario_session(stored.id)
        if job is not None and job.consumption_mode is JobConsumptionMode.reserved:
            raise RuntimeError("reserved job has no matching replay reservation")
        # Config enriches a durable replay; removing it cannot hide an accepted execution.
        scenario = self._find_product_scenario(stored.product_id, stored.scenario_id)
        return self._acceptance_snapshot(stored, scenario, job, is_replay=True)

    @staticmethod
    def _execution_owner(
        tenant_id: str,
        region: str,
        guest_id: str | None,
        explicit: ExecutionOwner | None,
    ) -> ExecutionOwner | None:
        if explicit is None:
            if guest_id == "":
                raise GuestIdentityRequiredError()
            return (
                None
                if guest_id is None
                else ExecutionOwner(tenant_id, region, ExecutionOwnerKind.guest, guest_id)
            )
        if (explicit.tenant_id, explicit.region) != (tenant_id, region) or (
            explicit.owner_kind is ExecutionOwnerKind.guest and explicit.owner_id != guest_id
        ):
            raise PlatformError(
                "execution_owner_invalid", "Execution owner does not match trusted scope or guest."
            )
        return explicit

    def _quota_input(
        self,
        *,
        owner: ExecutionOwner | None,
        paid_allowance: PaidAllowance | None,
        tenant_id: str,
        region: str,
        product_id: str,
        scenario_id: str,
        guest_id: str | None,
    ) -> QuotaValidation | PaidAllowance | None:
        if owner is not None and owner.owner_kind is ExecutionOwnerKind.portal_user:
            if paid_allowance is None:
                raise PaidAllowanceInvalidError()
            self._reservations.validate_paid_allowance(owner, product_id, paid_allowance)
            return paid_allowance
        if paid_allowance is not None:
            raise PaidAllowanceInvalidError()
        return (
            None
            if self._quota_service is None
            else self._quota_service.validate_accepted_start(
                tenant_id=tenant_id,
                region=region,
                product_id=product_id,
                guest_id=guest_id,
                scenario_id=scenario_id,
            )
        )

    def _acceptance_snapshot(
        self,
        session: ScenarioSessionRecord,
        scenario: ScenarioDefinition | None,
        job: JobRecord | None,
        *,
        reservation: ExecutionReservation | None = None,
        is_replay: bool = False,
    ) -> ExecutionAcceptance:
        return ExecutionAcceptance(
            **asdict(self._snapshot_from_records(session=session, scenario=scenario, job=job)),
            reservation=reservation,
            is_replay=is_replay,
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
        execution_owner: ExecutionOwner | None = None,
        paid_allowance: PaidAllowance | None = None,
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
        self._require_valid_workflow_input(workflow, input_payload)

        owner = self._execution_owner(tenant_id, region, guest_id, execution_owner)
        paid = owner is not None and owner.owner_kind is ExecutionOwnerKind.portal_user
        if paid:
            guest_id, user_id = None, owner.owner_id
        replay_identity = ExecutionReplayIdentity(
            product_id, scenario_id, ExecutionReplayNamespace.handoff, handoff_id
        )
        request_hash = digest_parts(
            compute_idempotency_request_hash(
                tenant_id=tenant_id,
                region=region,
                product_id=product_id,
                scenario_id=scenario_id,
                frontend_id=frontend_id,
                guest_id=guest_id,
                user_id=None if paid else user_id,
                input_payload=input_payload,
            ),
            handoff_id,
        )
        if owner is not None and queue_workflow:
            replay = self.find_execution_replay(
                self._session_repository.session, owner, replay_identity, request_hash
            )
            if replay is not None:
                stored = self._session_repository.get_in_scope(
                    replay.scenario_session_id, tenant_id=tenant_id, region=region
                )
                if stored is None or replay.job_id is None:
                    raise RuntimeError("handoff replay lost execution linkage")
                return LinkedScenarioSessionResult(
                    session=stored, job=self._job_repository.get(replay.job_id), acceptance=replay
                )
        quota_input = (
            None
            if not queue_workflow
            else self._quota_input(
                owner=owner,
                paid_allowance=paid_allowance,
                tenant_id=tenant_id,
                region=region,
                product_id=product_id,
                scenario_id=scenario_id,
                guest_id=guest_id,
            )
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
                **({"execution_owner": asdict(owner)} if paid and not queue_workflow else {}),
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
        with self._session_repository.session.begin_nested():
            stored_session = self._session_service.start(session_record, context=event_context)
            if not queue_workflow:
                return LinkedScenarioSessionResult(session=stored_session)
            job, reservation = self._create_execution_job(
                stored_session,
                workflow,
                owner,
                quota_input,
                replay_identity,
                request_hash,
                handoff_id=handoff_id,
            )
        return LinkedScenarioSessionResult(
            session=stored_session,
            job=job,
            acceptance=self._acceptance_snapshot(
                stored_session, scenario, job, reservation=reservation
            ),
        )

    def _create_execution_job(
        self,
        session: ScenarioSessionRecord,
        workflow: WorkflowDefinition,
        owner: ExecutionOwner | None,
        quota_input: QuotaValidation | PaidAllowance | None,
        replay_identity: ExecutionReplayIdentity | None,
        request_hash: str | None,
        *,
        handoff_id: str | None = None,
    ) -> tuple[JobRecord, ExecutionReservation | None]:
        metadata = {
            "guest_id": session.guest_id,
            "user_id": session.user_id,
            "scenario_chain_id": session.scenario_chain_id,
            "acquisition_source": session.frontend_id,
        }
        if handoff_id is not None:
            metadata["handoff_id"] = handoff_id
        job = self._job_repository.create(
            JobRecord(
                tenant_id=session.tenant_id,
                region=session.region,
                product_id=session.product_id,
                frontend_id=session.frontend_id,
                scenario_session_id=session.id,
                workflow_id=workflow.workflow_id,
                workflow_version=workflow.version,
                consumption_mode=(
                    JobConsumptionMode.unmetered
                    if quota_input is None
                    else JobConsumptionMode.reserved
                ),
                metadata=metadata,
            )
        )
        if quota_input is None:
            return job, None
        if owner is None:
            raise RuntimeError("metered execution has no owner")
        accepted = self._reservations.reserve_execution(
            self._session_repository.session,
            owner,
            ExecutionCandidate(session, job, replay_identity, request_hash, handoff_id),
            quota_input,
        )
        return job, accepted.reservation

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
        scenario = self._find_product_scenario(session.product_id, session.scenario_id)
        if scenario is not None and scenario.version != session.scenario_version:
            raise ScenarioNotFoundError()
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
        scenario: ScenarioDefinition | None,
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

    def _find_product_scenario(
        self, product_id: str, scenario_id: str
    ) -> ScenarioDefinition | None:
        product = self._config_registry.get_product(product_id)
        scenario = self._config_registry.get_scenario(scenario_id)
        if product is None or scenario is None or scenario_id not in product.scenarios:
            return None
        return scenario

    def _require_product_scenario(
        self,
        product_id: str,
        scenario_id: str,
        *,
        scenario_version: int | None = None,
    ) -> ScenarioDefinition:
        scenario = self._find_product_scenario(product_id, scenario_id)
        if scenario is None:
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

    def _require_valid_workflow_input(
        self,
        workflow: WorkflowDefinition,
        input_payload: Mapping[str, Any],
    ) -> None:
        # Same check SequentialWorkflowRunner._validate_workflow_input() repeats in the worker.
        # Running it here too means a payload the product's input schema rejects fails the
        # start request (422) before any scenario_sessions/jobs row is written or quota is
        # consumed, instead of being accepted and then failing in the worker with
        # workflow_input_validation_failed after the caller already paid for it.
        schema = self._config_registry.get_schema(workflow.input_schema_ref)
        if schema is None:
            raise LookupError(f"schema not found: {workflow.input_schema_ref}")
        normalized_schema = normalize_schema_mapping(schema.schema)
        if normalized_schema is None:
            return
        try:
            validate_json_schema(instance=input_payload, schema=normalized_schema)
        except JsonSchemaValidationError as exc:
            raise ScenarioInputInvalidError(
                "Scenario input does not match the scenario input schema."
            ) from exc


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

        Retained for session-only callers. Execution admission uses a savepoint covering
        the entire session/job/reservation candidate instead of this narrower helper.
        There is no optimistic pre-read here; the unique constraint arbitrates insertion.
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
                    f"scenario session idempotency race but no row found: {record.id}"
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
        if record.status is not ScenarioSessionStatus.started:
            return record
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


def _normalize_idempotency_key(key: str | None) -> str | None:
    if key is not None:
        key = key.strip() or None
    if key is not None and len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise IdempotencyKeyInvalidError()
    return key


def _require_paid_start_inputs(
    paid: bool, allowance: PaidAllowance | None, key: str | None
) -> None:
    if allowance is not None and not paid:
        raise PaidAllowanceInvalidError()
    if paid and key is None:
        raise PlatformError(
            "idempotency_key_required", "Idempotency-Key is required for paid execution."
        )


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
    runtime_scope: RuntimeScope = RuntimeScope.public,
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
    hash_parts = [
        tenant_id,
        region,
        product_id,
        scenario_id,
        frontend_id,
        guest_id or "",
        user_id or "",
        canonical_input,
    ]
    if runtime_scope is not RuntimeScope.public:
        hash_parts.append(runtime_scope.value)
    return digest_parts(*hash_parts)


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
