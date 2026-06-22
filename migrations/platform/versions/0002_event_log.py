"""MVP-A durable runtime event log."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"


def _json_document_type() -> sa.TypeEngine:
    return sa.JSON(none_as_null=True).with_variant(
        postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
        "postgresql",
    )


def upgrade() -> None:
    json_document = _json_document_type()
    op.create_table(
        "event_log",
        sa.Column("event_id", sa.String(length=128), primary_key=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
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
        sa.Column("action_type", sa.String(length=128)),
        sa.Column("action_config_id", sa.String(length=128)),
        sa.Column("provider", sa.String(length=128)),
        sa.Column("model", sa.String(length=256)),
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
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_event_log_timestamp",
        "event_log",
        ["timestamp"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_event_log_event_type",
        "event_log",
        ["event_type"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_event_log_product_id",
        "event_log",
        ["product_id"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_event_log_scenario_session_id",
        "event_log",
        ["scenario_session_id"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_event_log_job_id",
        "event_log",
        ["job_id"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_event_log_handoff_id",
        "event_log",
        ["handoff_id"],
        schema=PLATFORM_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("event_log", schema=PLATFORM_SCHEMA)
