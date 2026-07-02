"""Add safe provider error message column to provider calls."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"
TABLE_NAME = "provider_calls"
COLUMN_NAME = "error_message_safe"


def _has_column(bind: sa.Connection, *, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name, schema=PLATFORM_SCHEMA)
    return any(column["name"] == column_name for column in columns)


def upgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, table_name=TABLE_NAME, column_name=COLUMN_NAME):
        return
    op.add_column(
        TABLE_NAME,
        sa.Column(COLUMN_NAME, sa.Text(), nullable=True),
        schema=PLATFORM_SCHEMA,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, table_name=TABLE_NAME, column_name=COLUMN_NAME):
        return
    op.drop_column(TABLE_NAME, COLUMN_NAME, schema=PLATFORM_SCHEMA)
