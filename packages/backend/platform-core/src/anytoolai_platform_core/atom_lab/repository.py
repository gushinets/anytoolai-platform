from __future__ import annotations

from dataclasses import asdict, replace

import sqlalchemy as sa
from sqlalchemy.orm import Session

from anytoolai_platform_core.atom_lab.models import AtomLabRunRecord
from anytoolai_platform_core.providers.models import ReasoningEffort
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.scenarios.runtime_scope import is_atom_lab_session
from anytoolai_platform_core.storage.db import (
    action_runs_table,
    artifacts_table,
    atom_lab_runs_table,
    jobs_table,
    scenario_sessions_table,
)


class AtomLabRunRepository:
    """Durable Atom Lab snapshots scoped to the caller's transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, record: AtomLabRunRecord) -> AtomLabRunRecord:
        self._require_runtime_link(record)
        values = asdict(record)
        values["reasoning_effort"] = (
            None if record.reasoning_effort is None else record.reasoning_effort.value
        )
        self._session.execute(sa.insert(atom_lab_runs_table).values(values))
        self._session.flush()
        stored = self.get(record.id)
        if stored is None:
            raise RuntimeError(f"Atom Lab run round-trip failed after create: {record.id}")
        return stored

    def get(self, run_id: str) -> AtomLabRunRecord | None:
        row = (
            self._session.execute(
                sa.select(atom_lab_runs_table).where(atom_lab_runs_table.c.id == run_id)
            )
            .mappings()
            .one_or_none()
        )
        return self._from_row(row)

    def get_by_scenario_session_id(self, scenario_session_id: str) -> AtomLabRunRecord | None:
        row = (
            self._session.execute(
                sa.select(atom_lab_runs_table).where(
                    atom_lab_runs_table.c.scenario_session_id == scenario_session_id
                )
            )
            .mappings()
            .one_or_none()
        )
        return self._from_row(row)

    def get_by_job_id(self, job_id: str) -> AtomLabRunRecord | None:
        row = (
            self._session.execute(
                sa.select(atom_lab_runs_table).where(atom_lab_runs_table.c.job_id == job_id)
            )
            .mappings()
            .one_or_none()
        )
        return self._from_row(row)

    def bind_runtime_ids(
        self,
        run_id: str,
        *,
        action_run_id: str | None = None,
        artifact_id: str | None = None,
    ) -> AtomLabRunRecord:
        record = self._get_for_update(run_id)
        if record is None:
            raise LookupError(f"Atom Lab run not found: {run_id}")
        self._require_fill_once("action_run_id", record.action_run_id, action_run_id)
        self._require_fill_once("artifact_id", record.artifact_id, artifact_id)
        if action_run_id is not None:
            self._require_action_link(record, action_run_id)
        if artifact_id is not None:
            self._require_artifact_link(record, artifact_id)
        updated = replace(
            record,
            action_run_id=record.action_run_id or action_run_id,
            artifact_id=record.artifact_id or artifact_id,
        )
        result = self._session.execute(
            sa.update(atom_lab_runs_table)
            .where(atom_lab_runs_table.c.id == run_id)
            .values(
                action_run_id=updated.action_run_id,
                artifact_id=updated.artifact_id,
            )
        )
        if result.rowcount != 1:
            raise LookupError(f"Atom Lab run not found: {run_id}")
        self._session.flush()
        return self.get(run_id) or updated

    def _get_for_update(self, run_id: str) -> AtomLabRunRecord | None:
        row = (
            self._session.execute(
                sa.select(atom_lab_runs_table)
                .where(atom_lab_runs_table.c.id == run_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        return self._from_row(row)

    def _require_runtime_link(self, record: AtomLabRunRecord) -> None:
        scenario_row = (
            self._session.execute(
                sa.select(scenario_sessions_table).where(
                    scenario_sessions_table.c.id == record.scenario_session_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if scenario_row is None or not is_atom_lab_session(
            ScenarioSessionRecord(**dict(scenario_row))
        ):
            raise ValueError("Atom Lab scenario session link is missing or not laboratory-owned")
        expected_scenario = (
            record.tenant_id,
            record.region,
            record.product_id,
            record.frontend_id,
            record.scenario_id,
            record.scenario_version,
        )
        actual_scenario = (
            scenario_row["tenant_id"],
            scenario_row["region"],
            scenario_row["product_id"],
            scenario_row["frontend_id"],
            scenario_row["scenario_id"],
            scenario_row["scenario_version"],
        )
        if actual_scenario != expected_scenario:
            raise ValueError("Atom Lab snapshot scenario linkage is inconsistent")
        job_row = (
            self._session.execute(sa.select(jobs_table).where(jobs_table.c.id == record.job_id))
            .mappings()
            .one_or_none()
        )
        if job_row is None:
            raise ValueError("Atom Lab job link is missing")
        expected = (
            record.tenant_id,
            record.region,
            record.product_id,
            record.frontend_id,
            record.scenario_session_id,
            record.workflow_id,
            record.workflow_version,
        )
        actual = (
            job_row["tenant_id"],
            job_row["region"],
            job_row["product_id"],
            job_row["frontend_id"],
            job_row["scenario_session_id"],
            job_row["workflow_id"],
            job_row["workflow_version"],
        )
        if actual != expected:
            raise ValueError("Atom Lab snapshot runtime linkage is inconsistent")

    def _require_action_link(self, record: AtomLabRunRecord, action_run_id: str) -> None:
        row = (
            self._session.execute(
                sa.select(
                    action_runs_table.c.job_id, action_runs_table.c.scenario_session_id
                ).where(action_runs_table.c.id == action_run_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None or (row["job_id"], row["scenario_session_id"]) != (
            record.job_id,
            record.scenario_session_id,
        ):
            raise ValueError("Atom Lab action run linkage is inconsistent")

    def _require_artifact_link(self, record: AtomLabRunRecord, artifact_id: str) -> None:
        row = (
            self._session.execute(
                sa.select(artifacts_table.c.job_id, artifacts_table.c.scenario_session_id).where(
                    artifacts_table.c.id == artifact_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None or (row["job_id"], row["scenario_session_id"]) != (
            record.job_id,
            record.scenario_session_id,
        ):
            raise ValueError("Atom Lab artifact linkage is inconsistent")

    @staticmethod
    def _require_fill_once(field_name: str, current: str | None, incoming: str | None) -> None:
        if current is not None and incoming is not None and current != incoming:
            raise ValueError(f"Atom Lab {field_name} is already bound")

    @staticmethod
    def _from_row(row: sa.RowMapping | None) -> AtomLabRunRecord | None:
        if row is None:
            return None
        values = dict(row)
        reasoning_effort = values.get("reasoning_effort")
        values["reasoning_effort"] = (
            None if reasoning_effort is None else ReasoningEffort(reasoning_effort)
        )
        return AtomLabRunRecord(**values)
