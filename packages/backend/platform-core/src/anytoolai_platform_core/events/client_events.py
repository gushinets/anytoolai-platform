from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import (
    MAX_CLIENT_EVENT_ID_LENGTH,
    EventEmitter,
)
from anytoolai_platform_core.events.envelope import EventEnvelope
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.identity.service import GuestIdentityNotFoundError
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.scenarios.service import ScenarioSessionNotFoundError


class WebClientEventType(StrEnum):
    """ANY-17 v1 web-event allowlist -- the only event types POST /v1/client-events accepts.

    A closed HTTP-facing enum per docs/agent/coding-conventions.md, not a plain `str`, so OpenAPI
    emits a real enum and `ce-kit` can generate its client-side union from it instead of keeping an
    independent hand-maintained copy.
    """

    product_viewed = "web.product_viewed"
    form_started = "web.form_started"
    form_submitted = "web.form_submitted"
    result_viewed = "web.result_viewed"
    retry_clicked = "web.retry_clicked"
    mode_selected = "web.mode_selected"
    gap_selected = "web.gap_selected"
    feedback_submitted = "web.feedback_submitted"


CLIENT_EVENT_TYPES = frozenset(WebClientEventType)
# Privacy-reviewed scalar properties a client is allowed to send, each with its own expected type
# -- no prompt text, result text, clipboard contents, or arbitrary payload passthrough. See
# docs/architecture/event-taxonomy.md.
CLIENT_EVENT_PROPERTY_TYPES: dict[str, type] = {
    "mode": str,
    "field_count": int,
    "gap_category": str,
}
MAX_WEB_SESSION_ID_LENGTH = 128


class ClientEventTypeNotAllowedError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "client_event_type_not_allowed",
            "Event type is not part of the v1 client-event allowlist.",
        )


class ClientEventIdInvalidError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "client_event_id_invalid",
            f"event_id must be a non-empty string of at most {MAX_CLIENT_EVENT_ID_LENGTH} characters.",
        )


class ClientEventIdConflictError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "client_event_id_conflict",
            "event_id was already used to record a different client event.",
        )


class ClientEventWebSessionIdInvalidError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "client_event_web_session_id_invalid",
            f"web_session_id must be a non-empty string of at most {MAX_WEB_SESSION_ID_LENGTH} characters.",
        )


class ClientEventProductInvalidError(PlatformError):
    def __init__(self) -> None:
        super().__init__("client_event_product_invalid", "Product is not known.")


class ClientEventFrontendInvalidError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "client_event_frontend_invalid",
            "Frontend is not enabled for this product.",
        )


class ClientEventPropertyInvalidError(PlatformError):
    def __init__(self, key: str) -> None:
        super().__init__(
            "client_event_property_invalid",
            f"Property '{key}' is not an allowlisted client-event property of the expected type.",
        )


class ClientEventService:
    """Validates and records an allowlisted `web.*` client event (ANY-17).

    Extends the existing event log rather than replacing it: this only decides whether a
    client-submitted event is allowed to exist, then hands it to the same `EventEmitter` every
    other runtime-owned emission path uses.
    """

    def __init__(
        self,
        *,
        config_registry: ConfigRegistry,
        guest_repository: GuestIdentityRepository,
        scenario_session_repository: ScenarioSessionRepository,
        event_emitter: EventEmitter,
    ) -> None:
        self._config_registry = config_registry
        self._guest_repository = guest_repository
        self._scenario_session_repository = scenario_session_repository
        self._event_emitter = event_emitter

    def record(
        self,
        *,
        tenant_id: str,
        region: str,
        event_id: str,
        event_type: str,
        product_id: str,
        frontend_id: str,
        web_session_id: str,
        guest_id: str | None = None,
        user_id: str | None = None,
        scenario_session_id: str | None = None,
        properties: Mapping[str, Any] | None = None,
    ) -> EventEnvelope:
        if event_type not in CLIENT_EVENT_TYPES:
            raise ClientEventTypeNotAllowedError()
        if not event_id.strip() or len(event_id) > MAX_CLIENT_EVENT_ID_LENGTH:
            raise ClientEventIdInvalidError()
        if not web_session_id.strip() or len(web_session_id) > MAX_WEB_SESSION_ID_LENGTH:
            raise ClientEventWebSessionIdInvalidError()

        product = self._config_registry.get_product(product_id)
        if product is None:
            raise ClientEventProductInvalidError()
        if not any(
            frontend.frontend_id == frontend_id and frontend.enabled
            for frontend in product.frontends
        ):
            raise ClientEventFrontendInvalidError()

        if guest_id is not None:
            guest = self._guest_repository.get(guest_id, tenant_id=tenant_id, region=region)
            if guest is None:
                raise GuestIdentityNotFoundError()

        if scenario_session_id is not None:
            session = self._scenario_session_repository.get(
                scenario_session_id,
                tenant_id=tenant_id,
                region=region,
                product_id=product_id,
                frontend_id=frontend_id,
            )
            # A session that exists but belongs to a different guest must be indistinguishable
            # from a session that does not exist at all -- otherwise a caller could correlate
            # (and misattribute analytics to) a session it does not own, by guessing a valid
            # scenario_session_id and pairing it with its own unrelated guest_id.
            if session is None or (guest_id is not None and session.guest_id != guest_id):
                raise ScenarioSessionNotFoundError()

        event_properties = self._validate_properties(properties or {})
        event_properties["web_session_id"] = web_session_id

        context = ExecutionContext(
            tenant_id=tenant_id,
            region=region,
            product_id=product_id,
            frontend_id=frontend_id,
            guest_id=guest_id,
            user_id=user_id,
            scenario_session_id=scenario_session_id,
        )
        envelope = self._event_emitter.emit(
            event_type,
            context,
            properties=event_properties,
            event_id=event_id,
        )
        # `EventEmitter.emit(event_id=...)` treats a colliding event_id as an idempotent replay
        # and returns whatever is already stored under it, even if that stored row belongs to a
        # different logical event -- harmless for a genuine retry (same content), but a silent
        # misattribution for a colliding id used for different content. Compare what we asked to
        # record against what is actually stored and reject the mismatch instead of returning it
        # as if it had succeeded.
        if (
            envelope.event_type != event_type
            or envelope.product_id != product_id
            or envelope.frontend_id != frontend_id
            or envelope.guest_id != guest_id
            or envelope.user_id != user_id
            or envelope.scenario_session_id != scenario_session_id
            or envelope.properties != event_properties
        ):
            raise ClientEventIdConflictError()
        return envelope

    @staticmethod
    def _validate_properties(properties: Mapping[str, Any]) -> dict[str, Any]:
        validated: dict[str, Any] = {}
        for key, value in properties.items():
            expected_type = CLIENT_EVENT_PROPERTY_TYPES.get(key)
            if expected_type is None or isinstance(value, bool) or not isinstance(value, expected_type):
                raise ClientEventPropertyInvalidError(key)
            validated[key] = value
        return validated
