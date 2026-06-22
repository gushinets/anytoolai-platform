from __future__ import annotations

from dataclasses import replace
from typing import Any

from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.scenarios.models import (
    ScenarioSessionRecord,
    ScenarioSessionStatus,
)
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository


class ScenarioSessionService:
    def __init__(
        self,
        repository: ScenarioSessionRepository,
        event_emitter: EventEmitter,
    ) -> None:
        self._repository = repository
        self._event_emitter = event_emitter

    def start(self, record: ScenarioSessionRecord) -> ScenarioSessionRecord:
        stored = self._repository.create(record)
        self._event_emitter.emit(
            "scenario.started",
            _context_from_record(stored),
            properties={
                "scenario_id": stored.scenario_id,
                "scenario_version": stored.scenario_version,
            },
        )
        return stored

    def checkpoint(
        self,
        record: ScenarioSessionRecord,
        *,
        checkpoint_id: str,
        properties: dict[str, Any] | None = None,
    ) -> ScenarioSessionRecord:
        updated = self._repository.update(
            replace(record, current_checkpoint_id=checkpoint_id),
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

    def mark_completed(self, record: ScenarioSessionRecord) -> ScenarioSessionRecord:
        updated = self._repository.update(
            record,
            tenant_id=record.tenant_id,
            region=record.region,
            product_id=record.product_id,
            frontend_id=record.frontend_id,
        )
        self._event_emitter.emit(
            "scenario.completed",
            _context_from_record(updated),
            result_status=updated.status.value,
            properties={
                "scenario_id": updated.scenario_id,
                "scenario_version": updated.scenario_version,
            },
        )
        return updated

    def mark_failed(self, record: ScenarioSessionRecord, *, error_code: str) -> ScenarioSessionRecord:
        failed_record = replace(record, status=ScenarioSessionStatus.failed)
        updated = self._repository.update(
            failed_record,
            tenant_id=record.tenant_id,
            region=record.region,
            product_id=record.product_id,
            frontend_id=record.frontend_id,
        )
        self._event_emitter.emit(
            "scenario.failed",
            _context_from_record(updated),
            result_status=updated.status.value,
            properties={
                "error_code": error_code,
                "scenario_id": updated.scenario_id,
                "scenario_version": updated.scenario_version,
            },
        )
        return updated


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
