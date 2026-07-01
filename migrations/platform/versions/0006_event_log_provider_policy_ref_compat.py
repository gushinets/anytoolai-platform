"""Rename event-log provider policy column to provider_policy_ref."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"
TABLE_NAME = "event_log"
OLD_COLUMN_NAME = "provider_policy_id"
NEW_COLUMN_NAME = "provider_policy_ref"


def _has_column(bind: sa.Connection, *, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name, schema=PLATFORM_SCHEMA)
    return any(column["name"] == column_name for column in columns)


def _rename_column(old_name: str, new_name: str) -> None:
    op.execute(
        sa.text(
            "ALTER TABLE "
            f"{PLATFORM_SCHEMA}.{TABLE_NAME} "
            f"RENAME COLUMN {old_name} TO {new_name}"
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    has_old_column = _has_column(
        bind,
        table_name=TABLE_NAME,
        column_name=OLD_COLUMN_NAME,
    )
    has_new_column = _has_column(
        bind,
        table_name=TABLE_NAME,
        column_name=NEW_COLUMN_NAME,
    )
    if not has_old_column or has_new_column:
        return
    _rename_column(OLD_COLUMN_NAME, NEW_COLUMN_NAME)


def downgrade() -> None:
    bind = op.get_bind()
    has_old_column = _has_column(
        bind,
        table_name=TABLE_NAME,
        column_name=OLD_COLUMN_NAME,
    )
    has_new_column = _has_column(
        bind,
        table_name=TABLE_NAME,
        column_name=NEW_COLUMN_NAME,
    )
    if has_old_column or not has_new_column:
        return
    _rename_column(NEW_COLUMN_NAME, OLD_COLUMN_NAME)
