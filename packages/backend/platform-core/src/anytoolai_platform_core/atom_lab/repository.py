from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, replace
from datetime import date, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from anytoolai_platform_core.actions.models import ActionRunRecord
from anytoolai_platform_core.artifacts.models import ArtifactRecord
from anytoolai_platform_core.atom_lab.models import (
    AtomLabAdmissionScopeRecord,
    AtomLabPresetIdentityRecord,
    AtomLabPresetSummary,
    AtomLabPresetVersionRecord,
    AtomLabRunHistoryState,
    AtomLabRunRecord,
)
from anytoolai_platform_core.providers.models import ProviderCallRecord, ReasoningEffort
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord, ScenarioSessionStatus
from anytoolai_platform_core.scenarios.runtime_scope import (
    RUNTIME_SCOPE_METADATA_KEY,
    RuntimeScope,
    is_atom_lab_session,
)
from anytoolai_platform_core.storage.db import (
    action_runs_table,
    artifacts_table,
    atom_lab_admission_scopes_table,
    atom_lab_preset_versions_table,
    atom_lab_presets_table,
    atom_lab_runs_table,
    jobs_table,
    provider_calls_table,
    scenario_sessions_table,
)
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus

ATOM_LAB_DIAGNOSTIC_ITEMS_MAX = 100


class PresetVersionConflictError(RuntimeError):
    pass


class PresetSourceRunError(ValueError):
    pass


class PresetAtomMismatchError(ValueError):
    pass


class AtomLabPresetRepository:
    """Immutable preset versions within the server-owned Atom Lab scope."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        identity: AtomLabPresetIdentityRecord,
        version: AtomLabPresetVersionRecord,
    ) -> AtomLabPresetVersionRecord:
        if (
            version.preset_id != identity.id
            or version.version != 1
            or identity.latest_version != 1
        ):
            raise ValueError("A new Atom Lab preset must start at version 1")
        self._require_same_scope(identity, version)
        self._require_same_atom(identity.atom_id, version.atom_id)
        self._require_source_run(version)
        self._session.execute(sa.insert(atom_lab_presets_table).values(asdict(identity)))
        self._insert_version(version)
        self._session.flush()
        stored = self.get_version(
            identity.id,
            1,
            tenant_id=identity.tenant_id,
            region=identity.region,
        )
        if stored is None:
            raise RuntimeError("Atom Lab preset round-trip failed after create")
        return stored

    def add_version(
        self,
        version: AtomLabPresetVersionRecord,
        *,
        base_version: int,
    ) -> AtomLabPresetVersionRecord:
        row = (
            self._session.execute(
                sa.select(atom_lab_presets_table)
                .where(
                    atom_lab_presets_table.c.id == version.preset_id,
                    atom_lab_presets_table.c.tenant_id == version.tenant_id,
                    atom_lab_presets_table.c.region == version.region,
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LookupError("Atom Lab preset not found")
        if row["latest_version"] != base_version:
            raise PresetVersionConflictError("Atom Lab preset base version is stale")
        self._require_same_atom(row["atom_id"], version.atom_id)
        expected_version = base_version + 1
        if version.version != expected_version:
            raise ValueError("Atom Lab preset version number is not sequential")
        self._require_source_run(version)
        self._insert_version(version)
        result = self._session.execute(
            sa.update(atom_lab_presets_table)
            .where(
                atom_lab_presets_table.c.id == version.preset_id,
                atom_lab_presets_table.c.latest_version == base_version,
            )
            .values(latest_version=expected_version, updated_at=version.created_at)
        )
        if result.rowcount != 1:
            raise PresetVersionConflictError("Atom Lab preset base version is stale")
        self._session.flush()
        return version

    def get_version(
        self,
        preset_id: str,
        version: int,
        *,
        tenant_id: str,
        region: str,
    ) -> AtomLabPresetVersionRecord | None:
        row = (
            self._session.execute(
                sa.select(atom_lab_preset_versions_table).where(
                    atom_lab_preset_versions_table.c.preset_id == preset_id,
                    atom_lab_preset_versions_table.c.version == version,
                    atom_lab_preset_versions_table.c.tenant_id == tenant_id,
                    atom_lab_preset_versions_table.c.region == region,
                )
            )
            .mappings()
            .one_or_none()
        )
        return self._version_from_row(row)

    def get_identity(
        self,
        preset_id: str,
        *,
        tenant_id: str,
        region: str,
    ) -> AtomLabPresetIdentityRecord | None:
        row = (
            self._session.execute(
                sa.select(atom_lab_presets_table).where(
                    atom_lab_presets_table.c.id == preset_id,
                    atom_lab_presets_table.c.tenant_id == tenant_id,
                    atom_lab_presets_table.c.region == region,
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else AtomLabPresetIdentityRecord(**dict(row))

    def list_presets(
        self,
        *,
        tenant_id: str,
        region: str,
        limit: int,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[AtomLabPresetSummary, ...]:
        latest = atom_lab_preset_versions_table.alias("latest_preset_version")
        statement = (
            sa.select(
                atom_lab_presets_table.c.id.label("preset_id"),
                atom_lab_presets_table.c.latest_version,
                latest.c.name,
                latest.c.description,
                atom_lab_presets_table.c.atom_id,
                atom_lab_presets_table.c.created_at,
                atom_lab_presets_table.c.updated_at,
            )
            .join(
                latest,
                sa.and_(
                    latest.c.preset_id == atom_lab_presets_table.c.id,
                    latest.c.version == atom_lab_presets_table.c.latest_version,
                ),
            )
            .where(
                atom_lab_presets_table.c.tenant_id == tenant_id,
                atom_lab_presets_table.c.region == region,
            )
            .order_by(
                atom_lab_presets_table.c.created_at.desc(),
                atom_lab_presets_table.c.id.desc(),
            )
            .limit(limit)
        )
        if before is not None:
            created_at, preset_id = before
            before_created_at = sa.bindparam(
                "preset_before_created_at",
                created_at,
                type_=atom_lab_presets_table.c.created_at.type,
            )
            before_preset_id = sa.bindparam(
                "preset_before_id",
                preset_id,
                type_=atom_lab_presets_table.c.id.type,
            )
            statement = statement.where(
                sa.tuple_(atom_lab_presets_table.c.created_at, atom_lab_presets_table.c.id)
                < sa.tuple_(before_created_at, before_preset_id)
            )
        rows = self._session.execute(statement).mappings().all()
        return tuple(AtomLabPresetSummary(**dict(row)) for row in rows)

    def list_versions(
        self,
        preset_id: str,
        *,
        tenant_id: str,
        region: str,
        limit: int,
        before_version: int | None = None,
    ) -> tuple[AtomLabPresetVersionRecord, ...]:
        statement = (
            sa.select(atom_lab_preset_versions_table)
            .where(
                atom_lab_preset_versions_table.c.preset_id == preset_id,
                atom_lab_preset_versions_table.c.tenant_id == tenant_id,
                atom_lab_preset_versions_table.c.region == region,
            )
            .order_by(atom_lab_preset_versions_table.c.version.desc())
            .limit(limit)
        )
        if before_version is not None:
            statement = statement.where(
                atom_lab_preset_versions_table.c.version < before_version
            )
        rows = self._session.execute(statement).mappings().all()
        return tuple(self._version_from_row(row) for row in rows if row is not None)

    def _insert_version(self, version: AtomLabPresetVersionRecord) -> None:
        values = asdict(version)
        values["reasoning_effort"] = (
            None if version.reasoning_effort is None else version.reasoning_effort.value
        )
        values["fixed_fields"] = list(version.fixed_fields)
        self._session.execute(sa.insert(atom_lab_preset_versions_table).values(values))

    def _require_source_run(self, version: AtomLabPresetVersionRecord) -> None:
        if version.source_run_id is None:
            return
        run = (
            self._session.execute(
                sa.select(atom_lab_runs_table).where(
                    atom_lab_runs_table.c.id == version.source_run_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if run is None:
            raise PresetSourceRunError("Atom Lab source run was not found")
        scenario_row = (
            self._session.execute(
                sa.select(scenario_sessions_table).where(
                    scenario_sessions_table.c.id == run["scenario_session_id"]
                )
            )
            .mappings()
            .one_or_none()
        )
        if scenario_row is None or not is_atom_lab_session(
            ScenarioSessionRecord(**dict(scenario_row))
        ):
            raise PresetSourceRunError("Atom Lab source run is outside laboratory scope")
        expected = (
            version.tenant_id,
            version.region,
            version.atom_id,
            version.base_action_config_id,
            version.input_schema_ref,
            version.input_schema_version,
            version.output_schema_ref,
            version.output_schema_version,
            version.prompt_ref,
        )
        actual = (
            run["tenant_id"],
            run["region"],
            run["atom_id"],
            run["action_config_id"],
            run["input_schema_ref"],
            run["input_schema_version"],
            run["output_schema_ref"],
            run["output_schema_version"],
            run["prompt_ref"],
        )
        if actual != expected:
            raise PresetSourceRunError("Atom Lab source run provenance does not match preset")

    @staticmethod
    def _require_same_scope(
        identity: AtomLabPresetIdentityRecord,
        version: AtomLabPresetVersionRecord,
    ) -> None:
        if (identity.tenant_id, identity.region) != (version.tenant_id, version.region):
            raise ValueError("Atom Lab preset identity and version scope differ")

    @staticmethod
    def _require_same_atom(identity_atom_id: str, version_atom_id: str) -> None:
        if identity_atom_id != version_atom_id:
            raise PresetAtomMismatchError("Atom Lab preset atom cannot change between versions")

    @staticmethod
    def _version_from_row(row: sa.RowMapping | None) -> AtomLabPresetVersionRecord | None:
        if row is None:
            return None
        values = dict(row)
        effort = values.get("reasoning_effort")
        values["reasoning_effort"] = None if effort is None else ReasoningEffort(effort)
        values["fixed_fields"] = tuple(values["fixed_fields"])
        return AtomLabPresetVersionRecord(**values)


class AtomLabRunRepository:
    """Durable Atom Lab snapshots scoped to the caller's transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, record: AtomLabRunRecord) -> AtomLabRunRecord:
        self._require_runtime_link(record)
        self._require_preset_link(record)
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

    def get_by_idempotency_key(
        self,
        *,
        tenant_id: str,
        region: str,
        idempotency_key: str,
    ) -> AtomLabRunRecord | None:
        row = (
            self._session.execute(
                sa.select(atom_lab_runs_table).where(
                    atom_lab_runs_table.c.tenant_id == tenant_id,
                    atom_lab_runs_table.c.region == region,
                    atom_lab_runs_table.c.idempotency_key == idempotency_key,
                )
            )
            .mappings()
            .one_or_none()
        )
        return self._from_row(row)

    def history_in_scope(
        self,
        *,
        tenant_id: str,
        region: str,
        limit: int,
        before: tuple[datetime, str] | None = None,
        run_id: str | None = None,
    ) -> tuple[AtomLabRunHistoryState, ...]:
        statement = (
            sa.select(
                atom_lab_runs_table,
                jobs_table,
                scenario_sessions_table.c.status.label("session_status"),
            )
            .join(jobs_table, jobs_table.c.id == atom_lab_runs_table.c.job_id)
            .join(
                scenario_sessions_table,
                scenario_sessions_table.c.id == atom_lab_runs_table.c.scenario_session_id,
            )
            .where(
                atom_lab_runs_table.c.tenant_id == tenant_id,
                atom_lab_runs_table.c.region == region,
                jobs_table.c.tenant_id == tenant_id,
                jobs_table.c.region == region,
                jobs_table.c.scenario_session_id == scenario_sessions_table.c.id,
                scenario_sessions_table.c.tenant_id == tenant_id,
                scenario_sessions_table.c.region == region,
                scenario_sessions_table.c.metadata[RUNTIME_SCOPE_METADATA_KEY].as_string()
                == RuntimeScope.atom_lab.value,
            )
            .order_by(atom_lab_runs_table.c.created_at.desc(), atom_lab_runs_table.c.id.desc())
            .limit(limit)
        )
        if run_id is not None:
            statement = statement.where(atom_lab_runs_table.c.id == run_id)
        if before is not None:
            statement = statement.where(
                sa.tuple_(atom_lab_runs_table.c.created_at, atom_lab_runs_table.c.id)
                < sa.tuple_(
                    sa.bindparam(
                        "history_before_time",
                        before[0],
                        type_=atom_lab_runs_table.c.created_at.type,
                    ),
                    sa.bindparam(
                        "history_before_id", before[1], type_=atom_lab_runs_table.c.id.type
                    ),
                )
            )
        result = []
        for row in self._session.execute(statement).mappings():
            run_values = {column.name: row[column] for column in atom_lab_runs_table.c}
            run = self._from_row(run_values)
            assert run is not None
            result.append(
                AtomLabRunHistoryState(
                    run=run,
                    job=JobRecord(**{column.name: row[column] for column in jobs_table.c}),
                    session_status=row["session_status"],
                )
            )
        return tuple(result)

    @staticmethod
    def _runtime_scope(
        table: sa.Table, run: AtomLabRunRecord,
    ) -> tuple[sa.ColumnElement[bool], ...]:
        return (
            table.c.tenant_id == run.tenant_id,
            table.c.region == run.region,
            table.c.scenario_session_id == run.scenario_session_id,
            table.c.job_id == run.job_id,
        )

    def history_action(self, run: AtomLabRunRecord) -> ActionRunRecord | None:
        statement = sa.select(action_runs_table).where(
            *self._runtime_scope(action_runs_table, run),
            action_runs_table.c.step_id == run.step_id,
        )
        if run.action_run_id is not None:
            statement = statement.where(action_runs_table.c.id == run.action_run_id)
        row = (
            self._session.execute(
                statement.order_by(
                    action_runs_table.c.created_at.desc(), action_runs_table.c.id.desc()
                ).limit(1)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else ActionRunRecord(**dict(row))

    def history_artifact(self, run: AtomLabRunRecord, artifact_id: str) -> ArtifactRecord | None:
        row = (
            self._session.execute(
                sa.select(artifacts_table).where(
                    *self._runtime_scope(artifacts_table, run),
                    artifacts_table.c.id == artifact_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else ArtifactRecord(**dict(row))

    def history_provider_calls(
        self,
        run: AtomLabRunRecord,
    ) -> tuple[tuple[ProviderCallRecord, ...], int, int, int]:
        scope = self._runtime_scope(provider_calls_table, run)
        # The aggregates use all ledger rows even when the diagnostic page is truncated.
        physical = self._session.scalar(
            sa.select(sa.func.count()).select_from(provider_calls_table).where(*scope)
        )
        semantic_groups = (
            sa.select(
                provider_calls_table.c.action_run_id, provider_calls_table.c.semantic_attempt_index
            )
            .where(*scope)
            .distinct()
            .subquery()
        )
        transport_groups = (
            sa.select(
                provider_calls_table.c.action_run_id,
                provider_calls_table.c.semantic_attempt_index,
                provider_calls_table.c.transport_attempt_index,
            )
            .where(*scope)
            .distinct()
            .subquery()
        )
        semantic = self._session.scalar(sa.select(sa.func.count()).select_from(semantic_groups))
        transport = self._session.scalar(sa.select(sa.func.count()).select_from(transport_groups))
        rows = (
            self._session.execute(
                sa.select(provider_calls_table)
                .where(*scope)
                .order_by(
                    provider_calls_table.c.created_at.desc(),
                    provider_calls_table.c.physical_call_index.desc(),
                    provider_calls_table.c.id.desc(),
                )
                .limit(ATOM_LAB_DIAGNOSTIC_ITEMS_MAX)
            )
            .mappings()
            .all()
        )
        calls = tuple(ProviderCallRecord(**dict(row)) for row in reversed(rows))
        return calls, semantic, transport, physical

    def history_debug_artifacts(self, run: AtomLabRunRecord) -> tuple[ArtifactRecord, ...]:
        rows = (
            self._session.execute(
                sa.select(artifacts_table)
                .where(
                    *self._runtime_scope(artifacts_table, run),
                    artifacts_table.c.artifact_type == "structured_output_debug_raw",
                )
                .order_by(artifacts_table.c.created_at.desc(), artifacts_table.c.id.desc())
                .limit(ATOM_LAB_DIAGNOSTIC_ITEMS_MAX + 1)
            )
            .mappings()
            .all()
        )
        return tuple(ArtifactRecord(**dict(row)) for row in rows)

    def list_in_scope(
        self,
        *,
        tenant_id: str,
        region: str,
        limit: int,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[AtomLabRunRecord, ...]:
        statement = (
            sa.select(atom_lab_runs_table)
            .where(
                atom_lab_runs_table.c.tenant_id == tenant_id,
                atom_lab_runs_table.c.region == region,
            )
            .order_by(
                atom_lab_runs_table.c.created_at.desc(),
                atom_lab_runs_table.c.id.desc(),
            )
            .limit(limit)
        )
        if before is not None:
            created_at, run_id = before
            statement = statement.where(
                sa.tuple_(atom_lab_runs_table.c.created_at, atom_lab_runs_table.c.id)
                < sa.tuple_(
                    sa.bindparam(
                        "atom_lab_run_before_created_at",
                        created_at,
                        type_=atom_lab_runs_table.c.created_at.type,
                    ),
                    sa.bindparam(
                        "atom_lab_run_before_id",
                        run_id,
                        type_=atom_lab_runs_table.c.id.type,
                    ),
                )
            )
        rows = self._session.execute(statement).mappings().all()
        return tuple(record for row in rows if (record := self._from_row(row)) is not None)

    def lock_admission_scope(
        self,
        *,
        tenant_id: str,
        region: str,
        accepted_on: date,
        now: datetime,
    ) -> AtomLabAdmissionScopeRecord:
        values = {
            "tenant_id": tenant_id,
            "region": region,
            "accepted_on": accepted_on,
            "accepted_count": 0,
            "updated_at": now,
        }
        dialect_name = self._session.get_bind().dialect.name
        if dialect_name == "postgresql":
            statement = postgresql.insert(atom_lab_admission_scopes_table).values(values)
            statement = statement.on_conflict_do_nothing(index_elements=["tenant_id", "region"])
        elif dialect_name == "sqlite":
            statement = sqlite.insert(atom_lab_admission_scopes_table).values(values)
            statement = statement.on_conflict_do_nothing(index_elements=["tenant_id", "region"])
        else:
            statement = sa.insert(atom_lab_admission_scopes_table).values(values)
        if dialect_name in {"postgresql", "sqlite"}:
            self._session.execute(statement)
        else:  # pragma: no cover - production and tests use PostgreSQL/SQLite
            existing = self._get_admission_scope(tenant_id=tenant_id, region=region)
            if existing is None:
                self._session.execute(statement)
        row = (
            self._session.execute(
                sa.select(atom_lab_admission_scopes_table)
                .where(
                    atom_lab_admission_scopes_table.c.tenant_id == tenant_id,
                    atom_lab_admission_scopes_table.c.region == region,
                )
                .with_for_update()
            )
            .mappings()
            .one()
        )
        state = AtomLabAdmissionScopeRecord(**dict(row))
        return state

    def advance_admission_day(
        self,
        state: AtomLabAdmissionScopeRecord,
        *,
        accepted_on: date,
        now: datetime,
    ) -> AtomLabAdmissionScopeRecord:
        if state.accepted_on >= accepted_on:
            return state
        result = self._session.execute(
            sa.update(atom_lab_admission_scopes_table)
            .where(
                atom_lab_admission_scopes_table.c.tenant_id == state.tenant_id,
                atom_lab_admission_scopes_table.c.region == state.region,
                atom_lab_admission_scopes_table.c.accepted_on == state.accepted_on,
                atom_lab_admission_scopes_table.c.accepted_count == state.accepted_count,
            )
            .values(accepted_on=accepted_on, accepted_count=0, updated_at=now)
        )
        if result.rowcount != 1:
            raise RuntimeError("Atom Lab admission day changed without holding its scope lock")
        self._session.flush()
        return replace(state, accepted_on=accepted_on, accepted_count=0, updated_at=now)

    def increment_accepted_count(
        self,
        state: AtomLabAdmissionScopeRecord,
        *,
        now: datetime,
    ) -> AtomLabAdmissionScopeRecord:
        result = self._session.execute(
            sa.update(atom_lab_admission_scopes_table)
            .where(
                atom_lab_admission_scopes_table.c.tenant_id == state.tenant_id,
                atom_lab_admission_scopes_table.c.region == state.region,
                atom_lab_admission_scopes_table.c.accepted_on == state.accepted_on,
                atom_lab_admission_scopes_table.c.accepted_count == state.accepted_count,
            )
            .values(accepted_count=state.accepted_count + 1, updated_at=now)
        )
        if result.rowcount != 1:
            raise RuntimeError("Atom Lab admission count changed without holding its scope lock")
        self._session.flush()
        return replace(state, accepted_count=state.accepted_count + 1, updated_at=now)

    @staticmethod
    def active_count_statement(
        *,
        tenant_id: str,
        region: str,
    ) -> sa.Select[tuple[int]]:
        return (
            sa.select(sa.func.count())
            .select_from(atom_lab_runs_table)
            .join(jobs_table, jobs_table.c.id == atom_lab_runs_table.c.job_id)
            .join(
                scenario_sessions_table,
                scenario_sessions_table.c.id == atom_lab_runs_table.c.scenario_session_id,
            )
            .where(
                atom_lab_runs_table.c.tenant_id == tenant_id,
                atom_lab_runs_table.c.region == region,
                jobs_table.c.status.in_((JobStatus.created, JobStatus.running)),
                scenario_sessions_table.c.status.in_(
                    (
                        ScenarioSessionStatus.started,
                        ScenarioSessionStatus.waiting_for_user,
                        ScenarioSessionStatus.running,
                    )
                ),
            )
        )

    def _get_admission_scope(
        self,
        *,
        tenant_id: str,
        region: str,
    ) -> AtomLabAdmissionScopeRecord | None:
        row = (
            self._session.execute(
                sa.select(atom_lab_admission_scopes_table).where(
                    atom_lab_admission_scopes_table.c.tenant_id == tenant_id,
                    atom_lab_admission_scopes_table.c.region == region,
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else AtomLabAdmissionScopeRecord(**dict(row))

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

    def _require_preset_link(self, record: AtomLabRunRecord) -> None:
        if (record.preset_id is None) != (record.preset_version is None):
            raise ValueError("Atom Lab preset reference is incomplete")
        if record.preset_id is None or record.preset_version is None:
            return
        preset = AtomLabPresetRepository(self._session).get_version(
            record.preset_id,
            record.preset_version,
            tenant_id=record.tenant_id,
            region=record.region,
        )
        if preset is None:
            raise ValueError("Atom Lab preset version does not exist in run scope")
        expected = (
            record.atom_id,
            record.action_config_id,
            record.input_schema_ref,
            record.input_schema_version,
            record.output_schema_ref,
            record.output_schema_version,
            record.prompt_ref,
        )
        actual = (
            preset.atom_id,
            preset.base_action_config_id,
            preset.input_schema_ref,
            preset.input_schema_version,
            preset.output_schema_ref,
            preset.output_schema_version,
            preset.prompt_ref,
        )
        if actual != expected:
            raise ValueError("Atom Lab preset provenance does not match run contract")

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
    def _from_row(row: Mapping[str, Any] | None) -> AtomLabRunRecord | None:
        if row is None:
            return None
        values = dict(row)
        reasoning_effort = values.get("reasoning_effort")
        values["reasoning_effort"] = (
            None if reasoning_effort is None else ReasoningEffort(reasoning_effort)
        )
        return AtomLabRunRecord(**values)
