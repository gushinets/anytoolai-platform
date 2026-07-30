"""Add idempotency key/hash and unique constraint to scenario_sessions."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"
TABLE_NAME = "scenario_sessions"
CONSTRAINT_NAME = "uq_scenario_sessions_idempotency_key"
CONSTRAINT_COLUMNS = [
    "tenant_id",
    "region",
    "product_id",
    "scenario_id",
    "guest_id",
    "idempotency_key",
]


def _column_names() -> set[str]:
    bind = op.get_bind()
    return {
        column["name"]
        for column in sa.inspect(bind).get_columns(TABLE_NAME, schema=PLATFORM_SCHEMA)
    }


def upgrade() -> None:
    if context.is_offline_mode():
        op.add_column(
            TABLE_NAME,
            sa.Column("idempotency_key", sa.String(length=256), nullable=True),
            schema=PLATFORM_SCHEMA,
        )
        op.add_column(
            TABLE_NAME,
            sa.Column("idempotency_request_hash", sa.String(length=64), nullable=True),
            schema=PLATFORM_SCHEMA,
        )
        op.create_unique_constraint(
            CONSTRAINT_NAME,
            TABLE_NAME,
            CONSTRAINT_COLUMNS,
            schema=PLATFORM_SCHEMA,
        )
        return

    if "idempotency_key" in _column_names():
        return

    op.add_column(
        TABLE_NAME,
        sa.Column("idempotency_key", sa.String(length=256), nullable=True),
        schema=PLATFORM_SCHEMA,
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("idempotency_request_hash", sa.String(length=64), nullable=True),
        schema=PLATFORM_SCHEMA,
    )

    if op.get_bind().dialect.name == "sqlite":
        # SQLite has no ALTER TABLE ... ADD CONSTRAINT; batch mode recreates the table
        # (copy -> drop -> rename) to apply the constraint, including against the
        # ATTACH DATABASE ... AS platform schema alias this repo's tests use.
        with op.batch_alter_table(
            TABLE_NAME, schema=PLATFORM_SCHEMA, recreate="always"
        ) as batch_op:
            batch_op.create_unique_constraint(CONSTRAINT_NAME, CONSTRAINT_COLUMNS)
    else:
        op.create_unique_constraint(
            CONSTRAINT_NAME,
            TABLE_NAME,
            CONSTRAINT_COLUMNS,
            schema=PLATFORM_SCHEMA,
        )


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_constraint(
            CONSTRAINT_NAME, TABLE_NAME, schema=PLATFORM_SCHEMA, type_="unique"
        )
        op.drop_column(TABLE_NAME, "idempotency_request_hash", schema=PLATFORM_SCHEMA)
        op.drop_column(TABLE_NAME, "idempotency_key", schema=PLATFORM_SCHEMA)
        return

    if "idempotency_key" not in _column_names():
        return

    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(
            TABLE_NAME, schema=PLATFORM_SCHEMA, recreate="always"
        ) as batch_op:
            batch_op.drop_constraint(CONSTRAINT_NAME, type_="unique")
            batch_op.drop_column("idempotency_request_hash")
            batch_op.drop_column("idempotency_key")
    else:
        op.drop_constraint(
            CONSTRAINT_NAME, TABLE_NAME, schema=PLATFORM_SCHEMA, type_="unique"
        )
        op.drop_column(TABLE_NAME, "idempotency_request_hash", schema=PLATFORM_SCHEMA)
        op.drop_column(TABLE_NAME, "idempotency_key", schema=PLATFORM_SCHEMA)
