from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.events.client_events import (
    ClientEventService,
    ClientEventTypeNotAllowedError,
)
from anytoolai_platform_core.events.emitter import EventValidationError


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


CONFIG_ROOT = _repo_root() / "configs" / "kernel"


class _RaisingEmitter:
    """Stands in for a real `EventEmitter` whose own validation unexpectedly rejects the call --
    exercises the defense-in-depth translation in `ClientEventService.record()` without needing an
    actual drift between `WebClientEventType` and `configs/kernel/platform_events.yaml`."""

    def emit(self, *args: Any, **kwargs: Any) -> Any:
        raise EventValidationError("unknown platform event type: web.product_viewed")


def _service(*, event_emitter: Any) -> ClientEventService:
    return ClientEventService(
        config_registry=build_config_registry(CONFIG_ROOT),
        guest_repository=None,  # type: ignore[arg-type]
        scenario_session_repository=None,  # type: ignore[arg-type]
        event_emitter=event_emitter,
    )


def test_client_event_service_maps_unexpected_event_validation_error_to_safe_platform_error() -> None:
    service = _service(event_emitter=_RaisingEmitter())

    with pytest.raises(ClientEventTypeNotAllowedError):
        service.record(
            tenant_id="anytoolai",
            region="default",
            event_id="11111111-1111-4111-8111-111111111111",
            event_type="web.product_viewed",
            product_id="kernel_demo",
            frontend_id="web_mirror",
            web_session_id="22222222-2222-4222-8222-222222222222",
        )
