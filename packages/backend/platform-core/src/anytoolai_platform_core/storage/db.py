from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Engine

from anytoolai_platform_core.actions.models import ActionRunStatus
from anytoolai_platform_core.artifacts.models import ArtifactStatus
from anytoolai_platform_core.providers.models import ProviderCallStatus
from anytoolai_platform_core.scenarios.models import ScenarioSessionStatus
from anytoolai_platform_core.workflows.models import JobStatus

PLATFORM_SCHEMA = "platform"


class UtcDateTime(sa.TypeDecorator[datetime]):
    impl = sa.DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: sa.Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("timezone-aware UTC datetime required")
        return value.astimezone(UTC)

    def process_result_value(
        self, value: datetime | None, dialect: sa.Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def create_sync_engine(database_url: str, **kwargs: Any) -> Engine:
    return sa.create_engine(database_url, future=True, **kwargs)


def _json_document_type() -> sa.TypeEngine[Any]:
    return sa.JSON(none_as_null=True).with_variant(
        postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
        "postgresql",
    )


def _enum_type(enum_type: type[Any], name: str) -> sa.Enum:
    return sa.Enum(
        enum_type,
        name=name,
        create_constraint=True,
        native_enum=False,
        validate_strings=True,
        values_callable=lambda enum_cls: [member.value for member in enum_cls],
    )


runtime_metadata = sa.MetaData(schema=PLATFORM_SCHEMA)
json_document = _json_document_type()
utc_datetime = UtcDateTime()

scenario_sessions_table = sa.Table(
    "scenario_sessions",
    runtime_metadata,
    sa.Column("id", sa.String(length=128), primary_key=True),
    sa.Column("tenant_id", sa.String(length=128), nullable=False),
    sa.Column("region", sa.String(length=64), nullable=False),
    sa.Column("product_id", sa.String(length=128), nullable=False),
    sa.Column("frontend_id", sa.String(length=128), nullable=False),
    sa.Column("scenario_id", sa.String(length=128), nullable=False),
    sa.Column("scenario_version", sa.Integer(), nullable=False),
    sa.Column("guest_id", sa.String(length=128)),
    sa.Column("user_id", sa.String(length=128)),
    sa.Column(
        "status",
        _enum_type(ScenarioSessionStatus, "scenario_session_status"),
        nullable=False,
    ),
    sa.Column("current_checkpoint_id", sa.String(length=128)),
    sa.Column("current_step", sa.String(length=128)),
    sa.Column("scenario_chain_id", sa.String(length=128)),
    sa.Column("parent_scenario_session_id", sa.String(length=128)),
    sa.Column("source_frontend_instance_id", sa.String(length=128)),
    sa.Column("metadata", json_document, nullable=False),
    sa.Column("created_at", utc_datetime, nullable=False),
    sa.Column("started_at", utc_datetime, nullable=False),
    sa.Column("last_event_at", utc_datetime, nullable=False),
    sa.Column("completed_at", utc_datetime),
    sa.Column("expires_at", utc_datetime),
    sa.Index("ix_scenario_sessions_product_id", "product_id"),
    sa.Index("ix_scenario_sessions_created_at", "created_at"),
    sa.Index("ix_scenario_sessions_status", "status"),
)

jobs_table = sa.Table(
    "jobs",
    runtime_metadata,
    sa.Column("id", sa.String(length=128), primary_key=True),
    sa.Column("tenant_id", sa.String(length=128), nullable=False),
    sa.Column("region", sa.String(length=64), nullable=False),
    sa.Column("product_id", sa.String(length=128), nullable=False),
    sa.Column("frontend_id", sa.String(length=128), nullable=False),
    sa.Column("scenario_session_id", sa.String(length=128), nullable=False),
    sa.Column("workflow_id", sa.String(length=128), nullable=False),
    sa.Column("workflow_version", sa.Integer(), nullable=False),
    sa.Column("status", _enum_type(JobStatus, "job_status"), nullable=False),
    sa.Column("input_artifact_id", sa.String(length=128)),
    sa.Column("result_artifact_id", sa.String(length=128)),
    sa.Column("error_code", sa.String(length=128)),
    sa.Column("error_message_safe", sa.Text()),
    sa.Column("started_at", utc_datetime),
    sa.Column("completed_at", utc_datetime),
    sa.Column("created_at", utc_datetime, nullable=False),
    sa.Column("metadata", json_document, nullable=False),
    sa.Index("ix_jobs_scenario_session_id", "scenario_session_id"),
    sa.Index("ix_jobs_product_id", "product_id"),
    sa.Index("ix_jobs_created_at", "created_at"),
    sa.Index("ix_jobs_status", "status"),
)

action_runs_table = sa.Table(
    "action_runs",
    runtime_metadata,
    sa.Column("id", sa.String(length=128), primary_key=True),
    sa.Column("tenant_id", sa.String(length=128), nullable=False),
    sa.Column("region", sa.String(length=64), nullable=False),
    sa.Column("product_id", sa.String(length=128), nullable=False),
    sa.Column("frontend_id", sa.String(length=128), nullable=False),
    sa.Column("scenario_session_id", sa.String(length=128), nullable=False),
    sa.Column("job_id", sa.String(length=128), nullable=False),
    sa.Column("workflow_id", sa.String(length=128), nullable=False),
    sa.Column("step_id", sa.String(length=128), nullable=False),
    sa.Column("action_type", sa.String(length=128), nullable=False),
    sa.Column("action_config_id", sa.String(length=128), nullable=False),
    sa.Column(
        "status",
        _enum_type(ActionRunStatus, "action_run_status"),
        nullable=False,
    ),
    sa.Column("input_artifact_id", sa.String(length=128)),
    sa.Column("output_artifact_id", sa.String(length=128)),
    sa.Column("error_code", sa.String(length=128)),
    sa.Column("created_at", utc_datetime, nullable=False),
    sa.Column("started_at", utc_datetime),
    sa.Column("completed_at", utc_datetime),
    sa.Column("metadata", json_document, nullable=False),
    sa.Index("ix_action_runs_scenario_session_id", "scenario_session_id"),
    sa.Index("ix_action_runs_job_id", "job_id"),
    sa.Index("ix_action_runs_product_id", "product_id"),
    sa.Index("ix_action_runs_created_at", "created_at"),
    sa.Index("ix_action_runs_status", "status"),
)

provider_calls_table = sa.Table(
    "provider_calls",
    runtime_metadata,
    sa.Column("id", sa.String(length=128), primary_key=True),
    sa.Column("tenant_id", sa.String(length=128), nullable=False),
    sa.Column("region", sa.String(length=64), nullable=False),
    sa.Column("product_id", sa.String(length=128), nullable=False),
    sa.Column("frontend_id", sa.String(length=128), nullable=False),
    sa.Column("scenario_session_id", sa.String(length=128), nullable=False),
    sa.Column("job_id", sa.String(length=128), nullable=False),
    sa.Column("action_run_id", sa.String(length=128), nullable=False),
    sa.Column("workflow_id", sa.String(length=128), nullable=False),
    sa.Column("workflow_version", sa.Integer(), nullable=False),
    sa.Column("step_id", sa.String(length=128), nullable=False),
    sa.Column("action_type", sa.String(length=128), nullable=False),
    sa.Column("action_config_id", sa.String(length=128), nullable=False),
    sa.Column("provider_policy_ref", sa.String(length=128), nullable=False),
    sa.Column("provider", sa.String(length=128), nullable=False),
    sa.Column("model", sa.String(length=256), nullable=False),
    sa.Column("gateway_backend", sa.String(length=128), nullable=False),
    sa.Column("gateway_model", sa.String(length=256), nullable=False),
    sa.Column("semantic_attempt_index", sa.Integer(), nullable=False),
    sa.Column("transport_attempt_index", sa.Integer(), nullable=False),
    sa.Column("physical_call_index", sa.Integer(), nullable=False),
    sa.Column(
        "status",
        _enum_type(ProviderCallStatus, "provider_call_status"),
        nullable=False,
    ),
    sa.Column("input_tokens", sa.Integer(), nullable=False),
    sa.Column("output_tokens", sa.Integer(), nullable=False),
    sa.Column("total_tokens", sa.Integer(), nullable=False),
    sa.Column("latency_ms", sa.Integer(), nullable=False),
    sa.Column("estimated_cost", sa.Float(), nullable=False),
    sa.Column("error_code", sa.String(length=128)),
    sa.Column("error_message_safe", sa.Text()),
    sa.Column("failure_kind", sa.String(length=128)),
    sa.Column("http_status", sa.Integer()),
    sa.Column("pydantic_run_id", sa.String(length=128)),
    sa.Column("litellm_response_id", sa.String(length=256)),
    sa.Column("created_at", utc_datetime, nullable=False),
    sa.Column("started_at", utc_datetime),
    sa.Column("completed_at", utc_datetime),
    sa.Column("metadata", json_document, nullable=False),
    sa.Index("ix_provider_calls_scenario_session_id", "scenario_session_id"),
    sa.Index("ix_provider_calls_job_id", "job_id"),
    sa.Index("ix_provider_calls_product_id", "product_id"),
    sa.Index("ix_provider_calls_created_at", "created_at"),
    sa.Index("ix_provider_calls_status", "status"),
)

artifacts_table = sa.Table(
    "artifacts",
    runtime_metadata,
    sa.Column("id", sa.String(length=128), primary_key=True),
    sa.Column("tenant_id", sa.String(length=128), nullable=False),
    sa.Column("region", sa.String(length=64), nullable=False),
    sa.Column("product_id", sa.String(length=128), nullable=False),
    sa.Column("frontend_id", sa.String(length=128), nullable=False),
    sa.Column("scenario_session_id", sa.String(length=128), nullable=False),
    sa.Column("job_id", sa.String(length=128)),
    sa.Column("action_run_id", sa.String(length=128)),
    sa.Column("artifact_type", sa.String(length=128), nullable=False),
    sa.Column(
        "status",
        _enum_type(ArtifactStatus, "artifact_status"),
        nullable=False,
    ),
    sa.Column("content_text", sa.Text()),
    sa.Column("content_json", json_document),
    sa.Column("object_storage_key", sa.String(length=512)),
    sa.Column("metadata", json_document, nullable=False),
    sa.Column("created_at", utc_datetime, nullable=False),
    sa.Index("ix_artifacts_scenario_session_id", "scenario_session_id"),
    sa.Index("ix_artifacts_job_id", "job_id"),
    sa.Index("ix_artifacts_product_id", "product_id"),
    sa.Index("ix_artifacts_created_at", "created_at"),
    sa.Index("ix_artifacts_status", "status"),
)

guest_identities_table = sa.Table(
    "guest_identities",
    runtime_metadata,
    sa.Column("id", sa.String(length=128), primary_key=True),
    sa.Column("tenant_id", sa.String(length=128), nullable=False),
    sa.Column("region", sa.String(length=64), nullable=False),
    sa.Column("created_at", utc_datetime, nullable=False),
    sa.Column("last_seen_at", utc_datetime),
    sa.Column("metadata", json_document, nullable=False),
    sa.Index("ix_guest_identities_tenant_region", "tenant_id", "region"),
    sa.Index("ix_guest_identities_created_at", "created_at"),
)

guest_quota_usage_table = sa.Table(
    "guest_quota_usage",
    runtime_metadata,
    sa.Column("id", sa.String(length=128), primary_key=True),
    sa.Column("tenant_id", sa.String(length=128), nullable=False),
    sa.Column("region", sa.String(length=64), nullable=False),
    sa.Column("guest_id", sa.String(length=128), nullable=False),
    sa.Column("product_id", sa.String(length=128), nullable=False),
    sa.Column("quota_policy_id", sa.String(length=128), nullable=False),
    sa.Column("quota_dimension", sa.String(length=64), nullable=False),
    sa.Column("dimension_key", sa.String(length=128), nullable=False),
    sa.Column("scenario_id", sa.String(length=128)),
    sa.Column("period_key", sa.String(length=128), nullable=False),
    sa.Column("limit_count", sa.Integer(), nullable=False),
    sa.Column("used_count", sa.Integer(), nullable=False),
    sa.Column("created_at", utc_datetime, nullable=False),
    sa.Column("updated_at", utc_datetime, nullable=False),
    sa.Column("metadata", json_document, nullable=False),
    sa.CheckConstraint("limit_count >= 0", name="ck_guest_quota_usage_limit_count"),
    sa.CheckConstraint("used_count >= 0", name="ck_guest_quota_usage_used_count"),
    sa.ForeignKeyConstraint(
        ["guest_id"],
        [f"{PLATFORM_SCHEMA}.guest_identities.id"],
        name="fk_guest_quota_usage_guest_id",
    ),
    sa.UniqueConstraint(
        "tenant_id",
        "region",
        "guest_id",
        "product_id",
        "quota_policy_id",
        "quota_dimension",
        "dimension_key",
        "period_key",
        name="uq_guest_quota_usage_dimension",
    ),
    sa.Index("ix_guest_quota_usage_guest_product", "guest_id", "product_id"),
    sa.Index("ix_guest_quota_usage_dimension", "quota_dimension", "dimension_key"),
    sa.Index(
        "ix_guest_quota_usage_product_policy",
        "product_id",
        "quota_policy_id",
    ),
)

event_log_table = sa.Table(
    "event_log",
    runtime_metadata,
    sa.Column("event_id", sa.String(length=128), primary_key=True),
    sa.Column("event_type", sa.String(length=128), nullable=False),
    sa.Column("timestamp", utc_datetime, nullable=False),
    sa.Column("tenant_id", sa.String(length=128), nullable=False),
    sa.Column("region", sa.String(length=64), nullable=False),
    sa.Column("product_id", sa.String(length=128)),
    sa.Column("frontend_id", sa.String(length=128)),
    sa.Column("guest_id", sa.String(length=128)),
    sa.Column("user_id", sa.String(length=128)),
    sa.Column("scenario_session_id", sa.String(length=128)),
    sa.Column("scenario_chain_id", sa.String(length=128)),
    sa.Column("job_id", sa.String(length=128)),
    sa.Column("workflow_id", sa.String(length=128)),
    sa.Column("workflow_version", sa.Integer()),
    sa.Column("action_run_id", sa.String(length=128)),
    sa.Column("action_type", sa.String(length=128)),
    sa.Column("action_config_id", sa.String(length=128)),
    sa.Column("provider_policy_ref", sa.String(length=128)),
    sa.Column("provider_call_id", sa.String(length=128)),
    sa.Column("provider", sa.String(length=128)),
    sa.Column("model", sa.String(length=256)),
    sa.Column("physical_call_index", sa.Integer()),
    sa.Column("pydantic_run_id", sa.String(length=128)),
    sa.Column("litellm_response_id", sa.String(length=256)),
    sa.Column("artifact_id", sa.String(length=128)),
    sa.Column("handoff_id", sa.String(length=128)),
    sa.Column("result_status", sa.String(length=64)),
    sa.Column("error_code", sa.String(length=128)),
    sa.Column("acquisition_source", sa.String(length=128)),
    sa.Column(
        "properties",
        json_document,
        nullable=False,
        server_default=sa.text("'{}'"),
    ),
    sa.Index("ix_event_log_timestamp", "timestamp"),
    sa.Index("ix_event_log_event_type", "event_type"),
    sa.Index("ix_event_log_product_id", "product_id"),
    sa.Index("ix_event_log_scenario_session_id", "scenario_session_id"),
    sa.Index("ix_event_log_job_id", "job_id"),
    sa.Index("ix_event_log_action_run_id", "action_run_id"),
    sa.Index("ix_event_log_provider_call_id", "provider_call_id"),
    sa.Index("ix_event_log_handoff_id", "handoff_id"),
)

runtime_tables = {
    "scenario_sessions": scenario_sessions_table,
    "jobs": jobs_table,
    "action_runs": action_runs_table,
    "provider_calls": provider_calls_table,
    "artifacts": artifacts_table,
    "guest_identities": guest_identities_table,
    "guest_quota_usage": guest_quota_usage_table,
    "event_log": event_log_table,
}
