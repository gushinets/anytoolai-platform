from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from anytoolai_platform_core.events.envelope import EventEnvelope
from anytoolai_platform_core.storage.db import event_log_table


def _require_stored_event(
    stored: EventEnvelope | None, record_id: str, operation: str
) -> EventEnvelope:
    if stored is None:
        raise RuntimeError(f"event round-trip failed after {operation}: {record_id}")
    return stored


class EventLogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        record: EventEnvelope,
        *,
        allow_existing_event_id: bool = False,
    ) -> EventEnvelope:
        values = asdict(record)
        values.pop("schema_version", None)
        values.pop("metadata", None)
        insert_statement = sa.insert(event_log_table).values(values)
        if allow_existing_event_id:
            try:
                with self._session.begin_nested():
                    self._session.execute(insert_statement)
            except sa.exc.IntegrityError:
                stored = self.get(record.event_id)
                if stored is None:
                    raise
                return _require_stored_event(stored, record.event_id, "create")
        else:
            self._session.execute(insert_statement)
        self._session.flush()
        stored = self.get(record.event_id)
        return _require_stored_event(stored, record.event_id, "create")

    def get(self, event_id: str) -> EventEnvelope | None:
        row = (
            self._session.execute(
                sa.select(event_log_table).where(event_log_table.c.event_id == event_id)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else EventEnvelope(**dict(row))

    def exists_event(
        self,
        *,
        event_type: str,
        job_id: str | None = None,
        action_run_id: str | None = None,
        provider_call_id: str | None = None,
        artifact_id: str | None = None,
        step_id: str | None = None,
    ) -> bool:
        conditions = [event_log_table.c.event_type == event_type]
        if job_id is not None:
            conditions.append(event_log_table.c.job_id == job_id)
        if action_run_id is not None:
            conditions.append(event_log_table.c.action_run_id == action_run_id)
        if provider_call_id is not None:
            conditions.append(event_log_table.c.provider_call_id == provider_call_id)
        if artifact_id is not None:
            conditions.append(event_log_table.c.artifact_id == artifact_id)

        rows = self._session.execute(
            sa.select(event_log_table.c.properties).where(*conditions)
        ).scalars()
        if step_id is None:
            return rows.first() is not None

        for properties in rows:
            if _event_properties_step_id(properties) == step_id:
                return True
        return False


def build_replay_event_id(
    *,
    event_type: str,
    tenant_id: str,
    region: str,
    product_id: str | None = None,
    frontend_id: str | None = None,
    scenario_session_id: str | None = None,
    job_id: str | None = None,
    workflow_id: str | None = None,
    workflow_version: int | None = None,
    action_run_id: str | None = None,
    action_type: str | None = None,
    action_config_id: str | None = None,
    provider_policy_ref: str | None = None,
    provider_call_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    physical_call_index: int | None = None,
    pydantic_run_id: str | None = None,
    litellm_response_id: str | None = None,
    artifact_id: str | None = None,
    handoff_id: str | None = None,
    result_status: str | None = None,
    error_code: str | None = None,
    step_id: str | None = None,
) -> str:
    parts = (
        "replay_v1",
        event_type,
        tenant_id,
        region,
        product_id or "",
        frontend_id or "",
        scenario_session_id or "",
        job_id or "",
        workflow_id or "",
        "" if workflow_version is None else str(workflow_version),
        action_run_id or "",
        action_type or "",
        action_config_id or "",
        provider_policy_ref or "",
        provider_call_id or "",
        provider or "",
        model or "",
        "" if physical_call_index is None else str(physical_call_index),
        pydantic_run_id or "",
        litellm_response_id or "",
        artifact_id or "",
        handoff_id or "",
        result_status or "",
        error_code or "",
        step_id or "",
    )
    digest = sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return f"event_replay_{_replay_event_order_rank(event_type):03d}_{digest}"


def _event_properties_step_id(properties: Any) -> str | None:
    if not isinstance(properties, dict):
        return None
    step_id = properties.get("step_id")
    return step_id if isinstance(step_id, str) and step_id else None


def _replay_event_order_rank(event_type: str) -> int:
    return {
        "workflow.started": 10,
        "workflow.step_started": 20,
        "action.started": 30,
        "provider.request_started": 40,
        "provider.request_succeeded": 50,
        "provider.request_failed": 50,
        "artifact.created": 60,
        "action.succeeded": 70,
        "action.failed": 70,
        "workflow.step_skipped": 80,
        "workflow.step_succeeded": 80,
        "workflow.step_failed": 80,
        "workflow.succeeded": 90,
        "workflow.failed": 90,
        "workflow.canceled": 90,
    }.get(event_type, 999)
