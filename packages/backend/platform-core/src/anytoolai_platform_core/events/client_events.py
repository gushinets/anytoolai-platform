from __future__ import annotations

import uuid
from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import (
    MAX_CLIENT_EVENT_ID_LENGTH,
    EventEmitter,
    EventValidationError,
    sanitize_event_properties,
)
from anytoolai_platform_core.events.envelope import EventEnvelope
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.identity.service import GuestIdentityNotFoundError
from anytoolai_platform_core.products.models import ProductDefinition
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
# mode/gap_category are short categorical labels, never free text. A content-*shape* check (e.g. a
# slug pattern) is not enough on its own -- "please_rewrite_this_before_friday" is a valid slug and
# still arbitrary user content re-encoded under an allowlisted key. The actual closed set of valid
# values is product-owned (each product defines its own modes/gap categories) and must not be
# hardcoded in platform-core, so it's read per-request from
# `ProductDefinition.analytics["client_event_properties"]` (config/loader.py's `_load_analytics()`
# validates that shape at load time) -- see `_is_allowed_property_value()`. A product that hasn't
# declared a vocabulary for a key at all cannot use that key: the default is an empty closed set,
# never "anything goes".
CLIENT_EVENT_PROPERTIES_CONFIG_KEY = "client_event_properties"
# field_count is meant to be a small count (form fields on one page); an unbounded int would
# still round-trip through JSONB, but has no privacy-reviewed meaning past a sane ceiling.
MAX_PROPERTY_INT_VALUE = 10_000
# Echoed back in a 422 message; capped so a caller can't reflect an arbitrarily large key through
# the error response.
MAX_PROPERTY_KEY_LENGTH_IN_ERROR = 64
# Fields ClientEventIdConflictError's comparison reads off both `context` and the stored
# `envelope` -- both ExecutionContext and EventEnvelope name these identically.
_CONTEXT_CORRELATION_FIELDS = (
    "product_id",
    "frontend_id",
    "guest_id",
    "user_id",
    "scenario_session_id",
    "scenario_chain_id",
)
# event_log.user_id is a bounded String(128) column. Unlike guest_id/scenario_session_id (which
# are validated by requiring a matching existing row, indirectly bounding them), MVP-A has no
# user-identity table to look user_id up against, so its length must be checked explicitly here
# -- otherwise an oversized value reaches the INSERT unchecked and raises sa.exc.DataError, which
# EventLogRepository.create() does not catch (only sa.exc.IntegrityError), surfacing as a raw 500
# instead of this endpoint's normal 422 contract.
MAX_USER_ID_LENGTH = 128
# guest_id/scenario_session_id can never actually reach the INSERT oversized (they must exactly
# match an already-bounded existing row first, see `record()`), so this cap isn't load-bearing for
# safety the way MAX_USER_ID_LENGTH is -- it exists so an absurdly long value fails fast as a 422
# instead of paying for a lookup that can only ever miss.
MAX_LOOKUP_ID_LENGTH = 128


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
            "event_id must be a canonical lowercase UUID string (the same shape ce-kit's "
            "generateIdempotencyKey() already produces).",
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
            "web_session_id must be a canonical lowercase UUID string (the same shape ce-kit's "
            "getOrCreateWebSessionId() already produces).",
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


class ClientEventUserIdInvalidError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "client_event_user_id_invalid",
            f"user_id must be a non-empty string of at most {MAX_USER_ID_LENGTH} characters.",
        )


class ClientEventUserIdRequiresSessionError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "client_event_user_id_requires_scenario_session",
            "user_id is only accepted correlated with a known scenario_session_id; MVP-A has no "
            "authenticated-user lookup to verify a standalone user_id claim against.",
        )


class ClientEventGuestIdInvalidError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "client_event_guest_id_invalid",
            f"guest_id must be a non-empty string of at most {MAX_LOOKUP_ID_LENGTH} characters.",
        )


class ClientEventScenarioSessionIdInvalidError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "client_event_scenario_session_id_invalid",
            f"scenario_session_id must be a non-empty string of at most {MAX_LOOKUP_ID_LENGTH} "
            "characters.",
        )


class ClientEventPropertyInvalidError(PlatformError):
    def __init__(self, key: str) -> None:
        safe_key = (
            key
            if len(key) <= MAX_PROPERTY_KEY_LENGTH_IN_ERROR
            else f"{key[:MAX_PROPERTY_KEY_LENGTH_IN_ERROR]}..."
        )
        super().__init__(
            "client_event_property_invalid",
            f"Property '{safe_key}' is not an allowlisted client-event property of the expected "
            "type and shape.",
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
        event_type: WebClientEventType,
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
        # event_id/web_session_id are opaque client-minted identifiers, not arbitrary text: ce-kit
        # always generates a UUID for both, so requiring that shape (a) keeps the content-free
        # analytics guarantee for web_session_id, which is stored verbatim in event properties,
        # and (b) makes it structurally impossible for a client id to collide with the backend's
        # own reserved "event_<...>" / "event_replay_<...>" id namespaces (see common/ids.py,
        # events/replay.py), which a client must never be able to impersonate.
        event_id = _trim_or_raise(event_id, max_length=MAX_CLIENT_EVENT_ID_LENGTH, error=ClientEventIdInvalidError)
        if not _is_canonical_uuid(event_id):
            raise ClientEventIdInvalidError()
        web_session_id = _trim_or_raise(
            web_session_id, max_length=MAX_WEB_SESSION_ID_LENGTH, error=ClientEventWebSessionIdInvalidError
        )
        if not _is_canonical_uuid(web_session_id):
            raise ClientEventWebSessionIdInvalidError()
        if user_id is not None:
            user_id = _trim_or_raise(user_id, max_length=MAX_USER_ID_LENGTH, error=ClientEventUserIdInvalidError)
        if guest_id is not None:
            guest_id = _trim_or_raise(
                guest_id, max_length=MAX_LOOKUP_ID_LENGTH, error=ClientEventGuestIdInvalidError
            )
        if scenario_session_id is not None:
            scenario_session_id = _trim_or_raise(
                scenario_session_id,
                max_length=MAX_LOOKUP_ID_LENGTH,
                error=ClientEventScenarioSessionIdInvalidError,
            )

        product = self._config_registry.get_product(product_id)
        if product is None:
            raise ClientEventProductInvalidError()
        if not any(
            frontend.frontend_id == frontend_id and frontend.enabled
            for frontend in product.frontends
        ):
            raise ClientEventFrontendInvalidError()

        scenario_chain_id: str | None = None
        if scenario_session_id is not None:
            session = self._scenario_session_repository.get(
                scenario_session_id,
                tenant_id=tenant_id,
                region=region,
                product_id=product_id,
                frontend_id=frontend_id,
            )
            # An explicitly supplied guest_id/user_id that contradicts the session's real owner is
            # rejected outright (a confused or spoofing caller); one that's simply omitted is not
            # treated as a mismatch, since the session itself is about to become the source of
            # truth for identity below.
            if session is None or (
                (guest_id is not None and session.guest_id != guest_id)
                or (user_id is not None and session.user_id != user_id)
            ):
                raise ScenarioSessionNotFoundError()
            # The resolved session is authoritative for identity from here on -- derived, not
            # merely validated, so a caller never has to (and cannot incorrectly) re-assert
            # guest_id/user_id once scenario_session_id already carries that information, and so
            # scenario_chain_id (which a standalone client request has no way to know or claim on
            # its own) is populated instead of silently dropped.
            guest_id = session.guest_id
            user_id = session.user_id
            scenario_chain_id = session.scenario_chain_id
        elif user_id is not None:
            # No session to derive/verify user_id against, and MVP-A has no authenticated-user
            # lookup at all -- unlike guest_id (itself unauthenticated, but at least checked
            # against a real minted identity below), a standalone user_id claim is entirely
            # unverifiable and must not be trusted.
            raise ClientEventUserIdRequiresSessionError()
        elif guest_id is not None:
            guest = self._guest_repository.get(guest_id, tenant_id=tenant_id, region=region)
            if guest is None:
                raise GuestIdentityNotFoundError()

        event_properties = self._validate_properties(properties or {}, product=product)
        event_properties["web_session_id"] = web_session_id

        context = ExecutionContext(
            tenant_id=tenant_id,
            region=region,
            product_id=product_id,
            frontend_id=frontend_id,
            guest_id=guest_id,
            user_id=user_id,
            scenario_session_id=scenario_session_id,
            scenario_chain_id=scenario_chain_id,
        )
        try:
            envelope = self._event_emitter.emit(
                event_type,
                context,
                properties=event_properties,
                event_id=event_id,
            )
        except EventValidationError as exc:
            # Defense in depth: every input that could plausibly cause EventEmitter's own
            # validation to reject this call is already checked above (event_type against
            # CLIENT_EVENT_TYPES, event_id shape), so this should be unreachable in practice.
            # It only fires if those checks and the emitter's ever drift apart -- and if they
            # do, a client must still get a safe 422 (this service's own error contract), not an
            # uncaught ValueError surfacing as a raw 500.
            raise ClientEventTypeNotAllowedError() from exc
        # `EventEmitter.emit(event_id=...)` treats a colliding event_id as an idempotent replay
        # and returns whatever is already stored under it, even if that stored row belongs to a
        # different logical event -- harmless for a genuine retry (same content), but a silent
        # misattribution for a colliding id used for different content. Compare what we asked to
        # record against what is actually stored and reject the mismatch instead of returning it
        # as if it had succeeded. Correlation dimensions are read back off `context` itself (the
        # same object already passed to `emit()`) rather than re-listed as separate identifiers,
        # so a field can't silently drift out of sync between the two. Properties are compared
        # post-sanitization (the same transformation `emit()` itself applies) so a value that
        # `emit()` legitimately normalizes isn't mistaken for a content conflict on its very
        # first, successful write.
        correlation_mismatch = any(
            getattr(envelope, field) != getattr(context, field)
            for field in _CONTEXT_CORRELATION_FIELDS
        )
        if (
            envelope.event_type != event_type
            or correlation_mismatch
            or envelope.properties != sanitize_event_properties(event_properties)
        ):
            raise ClientEventIdConflictError()
        return envelope

    @staticmethod
    def _validate_properties(
        properties: Mapping[str, Any], *, product: ProductDefinition
    ) -> dict[str, Any]:
        allowed_categorical_values = product.analytics.get(CLIENT_EVENT_PROPERTIES_CONFIG_KEY, {})
        validated: dict[str, Any] = {}
        for key, value in properties.items():
            if not _is_allowed_property_value(key, value, allowed_categorical_values):
                raise ClientEventPropertyInvalidError(key)
            validated[key] = value
        return validated


def _trim_or_raise(value: str, *, max_length: int, error: type[PlatformError]) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > max_length:
        raise error()
    return normalized


def _is_canonical_uuid(value: str) -> bool:
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return str(parsed) == value


def _is_allowed_property_value(
    key: str, value: Any, allowed_categorical_values: Mapping[str, Any]
) -> bool:
    expected_type = CLIENT_EVENT_PROPERTY_TYPES.get(key)
    if expected_type is None or not isinstance(value, expected_type):
        return False
    if expected_type is int:
        # bool is a subclass of int in Python -- exclude it explicitly, but only here, so a
        # hypothetical future bool-typed key isn't rejected by this same guard.
        return not isinstance(value, bool) and 0 <= value <= MAX_PROPERTY_INT_VALUE
    if expected_type is str:
        # ConfigRegistry freezes loaded config into immutable structures, so a YAML list here
        # comes through as a tuple, not a list -- accept either rather than assuming the loader's
        # exact container type.
        allowed_values = allowed_categorical_values.get(key)
        return isinstance(allowed_values, (list, tuple)) and value in allowed_values
    return True
