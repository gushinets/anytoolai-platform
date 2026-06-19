"""Ensure event log exists for databases that applied old placeholder revisions."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"
EVENT_LOG_TABLE = "event_log"
EVENT_LOG_INDEXES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ix_event_log_timestamp", ("timestamp",)),
    ("ix_event_log_event_type", ("event_type",)),
    ("ix_event_log_product_id", ("product_id",)),
    ("ix_event_log_scenario_session_id", ("scenario_session_id",)),
    ("ix_event_log_job_id", ("job_id",)),
    ("ix_event_log_handoff_id", ("handoff_id",)),
)


def _json_document_type() -> sa.TypeEngine:
    return sa.JSON(none_as_null=True).with_variant(
        postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
        "postgresql",
    )


def _has_table(bind: sa.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name, schema=PLATFORM_SCHEMA)


def _has_index(bind: sa.Connection, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(
        index["name"] == index_name
        for index in inspector.get_indexes(table_name, schema=PLATFORM_SCHEMA)
    )


def _create_event_log_table() -> None:
    json_document = _json_document_type()
    op.create_table(
        EVENT_LOG_TABLE,
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


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, EVENT_LOG_TABLE):
        _create_event_log_table()

    for index_name, columns in EVENT_LOG_INDEXES:
        if not _has_index(bind, EVENT_LOG_TABLE, index_name):
            op.create_index(
                index_name,
                EVENT_LOG_TABLE,
                list(columns),
                schema=PLATFORM_SCHEMA,
            )


def downgrade() -> None:
    # This migration is a corrective backfill for databases that already recorded the
    # old placeholder 0002/0004 revisions. Event-log ownership remains with 0002.
    return None
