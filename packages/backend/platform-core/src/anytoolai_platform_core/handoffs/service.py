from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.common.ids import new_id
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.handoffs.models import (
    AcceptHandoffCommand,
    CreateHandoffCommand,
    HandoffAccepted,
    HandoffCreated,
    HandoffPreview,
    HandoffRecord,
    HandoffStartPolicy,
    HandoffStatus,
)
from anytoolai_platform_core.handoffs.payloads import HandoffPayloadBuilder, HandoffPayloadError
from anytoolai_platform_core.handoffs.repository import HandoffRepository
from anytoolai_platform_core.handoffs.tokens import HandoffTokenService
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.scenarios.service import ScenarioRuntimeService

DEFAULT_TOKEN_TTL = timedelta(minutes=30)
MAX_ERROR_CODE_LENGTH = 128


class HandoffNotFoundError(PlatformError):
    def __init__(self) -> None:
        super().__init__("handoff_not_found", "Handoff not found.")


class HandoffSourceInvalidError(PlatformError):
    def __init__(self) -> None:
        super().__init__("handoff_source_invalid", "Handoff source is not available.")


class HandoffExpiredError(PlatformError):
    def __init__(self) -> None:
        super().__init__("handoff_expired", "Handoff has expired.")


class HandoffNotActionableError(PlatformError):
    def __init__(self, code: str = "handoff_not_actionable") -> None:
        messages = {
            "handoff_already_accepted": "Handoff has already been accepted.",
            "handoff_declined": "Handoff has been declined.",
            "handoff_failed": "Handoff is unavailable.",
            "handoff_not_actionable": "Handoff is not actionable.",
        }
        super().__init__(code, messages[code])


class HandoffAcceptanceExecutionError(RuntimeError):
    def __init__(self, handoff_id: str, error_code: str) -> None:
        super().__init__("handoff acceptance failed")
        self.handoff_id = handoff_id
        self.error_code = error_code


class HandoffService:
    def __init__(
        self,
        *,
        config_registry: ConfigRegistry,
        repository: HandoffRepository,
        payload_builder: HandoffPayloadBuilder,
        scenario_runtime: ScenarioRuntimeService,
        scenario_repository: ScenarioSessionRepository,
        guest_repository: GuestIdentityRepository,
        event_emitter: EventEmitter,
        clock: Callable[[], datetime] = utc_now,
        token_ttl: timedelta = DEFAULT_TOKEN_TTL,
        token_service: HandoffTokenService | None = None,
    ) -> None:
        self._registry = config_registry
        self._repository = repository
        self._payload_builder = payload_builder
        self._scenario_runtime = scenario_runtime
        self._scenarios = scenario_repository
        self._guests = guest_repository
        self._events = event_emitter
        self._clock = clock
        self._token_ttl = token_ttl
        self._token_service = token_service or HandoffTokenService()

    def create_handoff(self, command: CreateHandoffCommand) -> HandoffCreated:
        definition = self._registry.get_handoff(command.handoff_definition_id)
        if definition is None:
            raise HandoffNotFoundError()
        try:
            built = self._payload_builder.build(
                definition=definition,
                tenant_id=command.tenant_id,
                region=command.region,
                source_scenario_session_id=command.source_scenario_session_id,
                source_artifact_id=command.source_artifact_id,
            )
        except HandoffPayloadError as exc:
            raise HandoffSourceInvalidError() from exc
        now = self._clock()
        token = self._token_service.generate()
        record = self._repository.create(
            HandoffRecord(
                handoff_definition_id=definition.handoff_id,
                tenant_id=command.tenant_id,
                region=command.region,
                token_hash=self._token_service.hash(token),
                source_product_id=built.source_session.product_id,
                source_frontend_id=built.source_session.frontend_id,
                source_scenario_id=built.source_session.scenario_id,
                source_scenario_session_id=built.source_session.id,
                source_job_id=built.source_job.id,
                source_artifact_id=command.source_artifact_id,
                target_product_id=definition.target_product_id,
                target_frontend_id=definition.target_frontend_id,
                target_scenario_id=definition.target_scenario_id,
                scenario_chain_id=built.source_session.scenario_chain_id or built.source_session.id,
                created_by_guest_id=built.source_session.guest_id,
                consent_required=definition.consent_required,
                target_start_policy=definition.target_start_policy,
                context_payload=built.context_payload,
                preview_payload=built.preview_payload,
                created_at=now,
                updated_at=now,
                expires_at=now + self._token_ttl,
            )
        )
        self._emit("handoff.created", record)
        return HandoffCreated(preview=self.build_safe_preview(record), handoff_token=token)

    def get_by_id(self, handoff_id: str, *, tenant_id: str, region: str) -> HandoffRecord:
        record = self._repository.get_by_id(handoff_id, tenant_id=tenant_id, region=region)
        if record is None:
            raise HandoffNotFoundError()
        return record

    def get_preview(self, token: str, *, tenant_id: str, region: str) -> HandoffPreview:
        record = self._by_token(token, tenant_id=tenant_id, region=region)
        record = self.expire(record)
        if record.status is HandoffStatus.created:
            transition = self._repository.mark_viewed(record.id, self._clock())
            record = transition.record
            if transition.changed:
                self._emit("handoff.viewed", record)
        return self.build_safe_preview(record)

    def accept(self, token: str, command: AcceptHandoffCommand) -> HandoffAccepted:
        record = self._by_token(token, tenant_id=command.tenant_id, region=command.region)
        record = self.expire(record)
        if record.status is HandoffStatus.expired:
            raise HandoffExpiredError()
        if record.status not in {HandoffStatus.created, HandoffStatus.viewed}:
            raise _terminal_error(record.status)
        effective_guest_id = command.guest_id or record.created_by_guest_id
        if (
            effective_guest_id is not None
            and self._guests.get(
                effective_guest_id,
                tenant_id=command.tenant_id,
                region=command.region,
            )
            is None
        ):
            raise HandoffSourceInvalidError()
        now = self._clock()
        claimed = self._repository.claim_accept(
            record.id,
            now,
            accepted_by_guest_id=effective_guest_id,
            accepted_from_frontend_instance_id=command.source_frontend_instance_id,
        )
        if claimed is None:
            current = self.get_by_id(record.id, tenant_id=command.tenant_id, region=command.region)
            raise _terminal_error(current.status)
        target_session_id = new_id("scenario_session")
        try:
            self._emit(
                "handoff.accepted",
                claimed,
                scenario_session_id=target_session_id,
                properties={"target_start_policy": claimed.target_start_policy.value},
            )
            source_session = self._scenarios.get_in_scope(
                claimed.source_scenario_session_id,
                tenant_id=claimed.tenant_id,
                region=claimed.region,
            )
            if source_session is None:
                raise HandoffAcceptanceExecutionError(claimed.id, "handoff_source_invalid")
            linked = self._scenario_runtime.create_linked_session(
                tenant_id=claimed.tenant_id,
                region=claimed.region,
                product_id=claimed.target_product_id,
                scenario_id=claimed.target_scenario_id,
                frontend_id=claimed.target_frontend_id,
                input_payload=claimed.context_payload,
                scenario_session_id=target_session_id,
                scenario_chain_id=claimed.scenario_chain_id,
                parent_scenario_session_id=claimed.source_scenario_session_id,
                handoff_id=claimed.id,
                source_artifact_id=claimed.source_artifact_id,
                guest_id=effective_guest_id,
                user_id=source_session.user_id,
                source_frontend_instance_id=command.source_frontend_instance_id,
                queue_workflow=claimed.target_start_policy is HandoffStartPolicy.immediate,
            )
            attached = self._repository.attach_target(
                claimed.id,
                target_scenario_session_id=linked.session.id,
                target_job_id=None if linked.job is None else linked.job.id,
                now=self._clock(),
            )
            if linked.job is not None:
                transition = self._repository.consume(
                    attached.id,
                    target_job_id=linked.job.id,
                    now=self._clock(),
                )
                attached = transition.record
                if transition.changed:
                    self._emit(
                        "handoff.consumed",
                        attached,
                        scenario_session_id=linked.session.id,
                        job_id=linked.job.id,
                    )
        except HandoffAcceptanceExecutionError:
            raise
        except Exception as exc:
            error_code = (
                "quota_exhausted"
                if isinstance(exc, PlatformError) and exc.code == "quota_exhausted"
                else "handoff_acceptance_failed"
            )
            raise HandoffAcceptanceExecutionError(claimed.id, error_code) from exc
        return HandoffAccepted(preview=self.build_safe_preview(attached))

    def decline(self, token: str, *, tenant_id: str, region: str) -> HandoffPreview:
        record = self.expire(self._by_token(token, tenant_id=tenant_id, region=region))
        if record.status is HandoffStatus.expired:
            raise HandoffExpiredError()
        transition = self._repository.decline(record.id, self._clock())
        if not transition.changed:
            raise _terminal_error(transition.record.status)
        self._emit("handoff.declined", transition.record)
        return self.build_safe_preview(transition.record)

    def expire(self, record: HandoffRecord) -> HandoffRecord:
        transition = self._repository.expire_if_due(record.id, self._clock())
        if transition.changed:
            self._emit("handoff.expired", transition.record)
        return transition.record

    def consume(self, handoff_id: str, target_job_id: str) -> HandoffRecord:
        transition = self._repository.consume(
            handoff_id, target_job_id=target_job_id, now=self._clock()
        )
        if not transition.changed:
            raise _terminal_error(transition.record.status)
        self._emit(
            "handoff.consumed",
            transition.record,
            scenario_session_id=transition.record.target_scenario_session_id,
            job_id=target_job_id,
        )
        return transition.record

    def mark_failed(
        self,
        handoff_id: str,
        *,
        tenant_id: str,
        region: str,
        error_code: str,
    ) -> HandoffRecord:
        record = self.get_by_id(handoff_id, tenant_id=tenant_id, region=region)
        safe_error_code = _safe_error_code(error_code)
        transition = self._repository.mark_failed(
            record.id, error_code=safe_error_code, now=self._clock()
        )
        if transition.changed:
            self._emit(
                "handoff.failed",
                transition.record,
                properties={"error_code": safe_error_code},
            )
        return transition.record

    def build_safe_preview(self, record: HandoffRecord) -> HandoffPreview:
        source = self._registry.get_product(record.source_product_id)
        target = self._registry.get_product(record.target_product_id)
        if source is None or target is None:
            raise RuntimeError("handoff product config is unavailable")
        return HandoffPreview(
            handoff_id=record.id,
            status=record.status,
            source_product_id=source.product_id,
            source_product_display_name=source.display_name,
            target_product_id=target.product_id,
            target_product_display_name=target.display_name,
            target_scenario_id=record.target_scenario_id,
            preview=dict(record.preview_payload),
            expires_at=record.expires_at,
            target_scenario_session_id=record.target_scenario_session_id,
            target_job_id=record.target_job_id,
        )

    def _by_token(self, token: str, *, tenant_id: str, region: str) -> HandoffRecord:
        record = self._repository.get_by_token_hash(
            self._token_service.hash(token), tenant_id=tenant_id, region=region
        )
        if record is None:
            raise HandoffNotFoundError()
        return record

    def _emit(
        self,
        event_type: str,
        record: HandoffRecord,
        *,
        scenario_session_id: str | None = None,
        job_id: str | None = None,
        properties: dict[str, object] | None = None,
    ) -> None:
        event_properties = {
            "handoff_definition_id": record.handoff_definition_id,
            "source_scenario_session_id": record.source_scenario_session_id,
            "target_scenario_session_id": scenario_session_id or record.target_scenario_session_id,
            **(properties or {}),
        }
        self._events.emit(
            event_type,
            ExecutionContext(
                tenant_id=record.tenant_id,
                region=record.region,
                product_id=(
                    record.target_product_id if scenario_session_id else record.source_product_id
                ),
                frontend_id=(
                    record.target_frontend_id if scenario_session_id else record.source_frontend_id
                ),
                guest_id=record.accepted_by_guest_id or record.created_by_guest_id,
                scenario_session_id=scenario_session_id or record.source_scenario_session_id,
                scenario_chain_id=record.scenario_chain_id,
                job_id=job_id,
                handoff_id=record.id,
            ),
            result_status=record.status.value,
            properties=event_properties,
        )


def _terminal_error(status: HandoffStatus) -> PlatformError:
    if status is HandoffStatus.expired:
        return HandoffExpiredError()
    if status in {HandoffStatus.accepted, HandoffStatus.consumed}:
        return HandoffNotActionableError("handoff_already_accepted")
    if status is HandoffStatus.declined:
        return HandoffNotActionableError("handoff_declined")
    if status is HandoffStatus.failed:
        return HandoffNotActionableError("handoff_failed")
    return HandoffNotActionableError()


def _safe_error_code(error_code: str) -> str:
    if (
        error_code
        and len(error_code) <= MAX_ERROR_CODE_LENGTH
        and all(
            character.islower() or character.isdigit() or character == "_"
            for character in error_code
        )
    ):
        return error_code
    return "handoff_acceptance_failed"
