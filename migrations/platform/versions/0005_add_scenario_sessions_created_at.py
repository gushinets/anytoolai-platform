"""Backfill scenario session created_at for existing databases."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"
SCENARIO_SESSIONS_TABLE = "scenario_sessions"
SCENARIO_SESSIONS_CREATED_AT_INDEX = "ix_scenario_sessions_created_at"


def _has_column(bind: sa.Connection, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(
        column["name"] == column_name
        for column in inspector.get_columns(table_name, schema=PLATFORM_SCHEMA)
    )


def _has_index(bind: sa.Connection, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(
        index["name"] == index_name
        for index in inspector.get_indexes(table_name, schema=PLATFORM_SCHEMA)
    )


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_column(bind, SCENARIO_SESSIONS_TABLE, "created_at"):
        op.add_column(
            SCENARIO_SESSIONS_TABLE,
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            schema=PLATFORM_SCHEMA,
        )
        op.execute(
            sa.text(
                f"""
                UPDATE {PLATFORM_SCHEMA}.{SCENARIO_SESSIONS_TABLE}
                SET created_at = COALESCE(started_at, last_event_at, CURRENT_TIMESTAMP)
                WHERE created_at IS NULL
                """
            )
        )
        with op.batch_alter_table(SCENARIO_SESSIONS_TABLE, schema=PLATFORM_SCHEMA) as batch_op:
            batch_op.alter_column(
                "created_at",
                existing_type=sa.DateTime(timezone=True),
                nullable=False,
            )

    if not _has_index(bind, SCENARIO_SESSIONS_TABLE, SCENARIO_SESSIONS_CREATED_AT_INDEX):
        op.create_index(
            SCENARIO_SESSIONS_CREATED_AT_INDEX,
            SCENARIO_SESSIONS_TABLE,
            ["created_at"],
            schema=PLATFORM_SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()

    if _has_index(bind, SCENARIO_SESSIONS_TABLE, SCENARIO_SESSIONS_CREATED_AT_INDEX):
        op.drop_index(
            SCENARIO_SESSIONS_CREATED_AT_INDEX,
            table_name=SCENARIO_SESSIONS_TABLE,
            schema=PLATFORM_SCHEMA,
        )

    if _has_column(bind, SCENARIO_SESSIONS_TABLE, "created_at"):
        with op.batch_alter_table(SCENARIO_SESSIONS_TABLE, schema=PLATFORM_SCHEMA) as batch_op:
            batch_op.drop_column("created_at")
