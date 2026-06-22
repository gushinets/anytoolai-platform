"""MVP-A runtime tables."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"


def _json_document_type() -> sa.TypeEngine:
    return sa.JSON(none_as_null=True).with_variant(
        postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
        "postgresql",
    )


def _enum_type(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {PLATFORM_SCHEMA}"))

    json_document = _json_document_type()

    op.create_table(
        "scenario_sessions",
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
            _enum_type(
                "scenario_session_status",
                "started",
                "waiting_for_user",
                "running",
                "completed",
                "failed",
                "expired",
            ),
            nullable=False,
        ),
        sa.Column("current_checkpoint_id", sa.String(length=128)),
        sa.Column("current_step", sa.String(length=128)),
        sa.Column("scenario_chain_id", sa.String(length=128)),
        sa.Column("parent_scenario_session_id", sa.String(length=128)),
        sa.Column("source_frontend_instance_id", sa.String(length=128)),
        sa.Column("metadata", json_document, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_scenario_sessions_product_id",
        "scenario_sessions",
        ["product_id"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_scenario_sessions_created_at",
        "scenario_sessions",
        ["created_at"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_scenario_sessions_status",
        "scenario_sessions",
        ["status"],
        schema=PLATFORM_SCHEMA,
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("region", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column("frontend_id", sa.String(length=128), nullable=False),
        sa.Column("scenario_session_id", sa.String(length=128), nullable=False),
        sa.Column("workflow_id", sa.String(length=128), nullable=False),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            _enum_type("job_status", "created", "running", "succeeded", "failed", "canceled"),
            nullable=False,
        ),
        sa.Column("input_artifact_id", sa.String(length=128)),
        sa.Column("result_artifact_id", sa.String(length=128)),
        sa.Column("error_code", sa.String(length=128)),
        sa.Column("error_message_safe", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", json_document, nullable=False),
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_jobs_scenario_session_id",
        "jobs",
        ["scenario_session_id"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_jobs_product_id",
        "jobs",
        ["product_id"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_jobs_created_at",
        "jobs",
        ["created_at"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_jobs_status",
        "jobs",
        ["status"],
        schema=PLATFORM_SCHEMA,
    )

    op.create_table(
        "action_runs",
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
            _enum_type(
                "action_run_status",
                "created",
                "running",
                "succeeded",
                "failed",
                "canceled",
                "skipped",
            ),
            nullable=False,
        ),
        sa.Column("input_artifact_id", sa.String(length=128)),
        sa.Column("output_artifact_id", sa.String(length=128)),
        sa.Column("error_code", sa.String(length=128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", json_document, nullable=False),
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_action_runs_scenario_session_id",
        "action_runs",
        ["scenario_session_id"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_action_runs_job_id",
        "action_runs",
        ["job_id"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_action_runs_product_id",
        "action_runs",
        ["product_id"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_action_runs_created_at",
        "action_runs",
        ["created_at"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_action_runs_status",
        "action_runs",
        ["status"],
        schema=PLATFORM_SCHEMA,
    )

    op.create_table(
        "provider_calls",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("region", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column("frontend_id", sa.String(length=128), nullable=False),
        sa.Column("scenario_session_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("action_run_id", sa.String(length=128), nullable=False),
        sa.Column("workflow_id", sa.String(length=128), nullable=False),
        sa.Column("step_id", sa.String(length=128), nullable=False),
        sa.Column("action_type", sa.String(length=128), nullable=False),
        sa.Column("action_config_id", sa.String(length=128), nullable=False),
        sa.Column("provider_policy_id", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("model", sa.String(length=256), nullable=False),
        sa.Column(
            "status",
            _enum_type(
                "provider_call_status",
                "created",
                "running",
                "succeeded",
                "failed",
                "timed_out",
            ),
            nullable=False,
        ),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=False),
        sa.Column("error_code", sa.String(length=128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", json_document, nullable=False),
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_provider_calls_scenario_session_id",
        "provider_calls",
        ["scenario_session_id"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_provider_calls_job_id",
        "provider_calls",
        ["job_id"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_provider_calls_product_id",
        "provider_calls",
        ["product_id"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_provider_calls_created_at",
        "provider_calls",
        ["created_at"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_provider_calls_status",
        "provider_calls",
        ["status"],
        schema=PLATFORM_SCHEMA,
    )

    op.create_table(
        "artifacts",
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
            _enum_type("artifact_status", "created", "stored", "failed"),
            nullable=False,
        ),
        sa.Column("content_text", sa.Text()),
        sa.Column("content_json", json_document),
        sa.Column("object_storage_key", sa.String(length=512)),
        sa.Column("metadata", json_document, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_artifacts_scenario_session_id",
        "artifacts",
        ["scenario_session_id"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_artifacts_job_id",
        "artifacts",
        ["job_id"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_artifacts_product_id",
        "artifacts",
        ["product_id"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_artifacts_created_at",
        "artifacts",
        ["created_at"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_artifacts_status",
        "artifacts",
        ["status"],
        schema=PLATFORM_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("artifacts", schema=PLATFORM_SCHEMA)
    op.drop_table("provider_calls", schema=PLATFORM_SCHEMA)
    op.drop_table("action_runs", schema=PLATFORM_SCHEMA)
    op.drop_table("jobs", schema=PLATFORM_SCHEMA)
    op.drop_table("scenario_sessions", schema=PLATFORM_SCHEMA)

    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.execute(sa.text(f"DROP SCHEMA IF EXISTS {PLATFORM_SCHEMA}"))
