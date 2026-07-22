"""Add policy-driven guest quota dimensions."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"
TABLE_NAME = "guest_quota_usage"


def _column_names() -> set[str]:
    bind = op.get_bind()
    return {
        column["name"]
        for column in sa.inspect(bind).get_columns(TABLE_NAME, schema=PLATFORM_SCHEMA)
    }


def upgrade() -> None:
    existing_columns = _column_names()
    if "quota_dimension" in existing_columns:
        return

    op.add_column(
        TABLE_NAME,
        sa.Column("quota_dimension", sa.String(length=64), nullable=True),
        schema=PLATFORM_SCHEMA,
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("dimension_key", sa.String(length=128), nullable=True),
        schema=PLATFORM_SCHEMA,
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("scenario_id", sa.String(length=128)),
        schema=PLATFORM_SCHEMA,
    )
    op.execute(
        sa.text(
            f"UPDATE {PLATFORM_SCHEMA}.{TABLE_NAME} "
            "SET quota_dimension = 'product', dimension_key = product_id "
            "WHERE quota_dimension IS NULL"
        )
    )

    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            TABLE_NAME,
            "quota_dimension",
            existing_type=sa.String(length=64),
            nullable=False,
            schema=PLATFORM_SCHEMA,
        )
        op.alter_column(
            TABLE_NAME,
            "dimension_key",
            existing_type=sa.String(length=128),
            nullable=False,
            schema=PLATFORM_SCHEMA,
        )
        op.drop_constraint(
            "uq_guest_quota_usage_dimension",
            TABLE_NAME,
            schema=PLATFORM_SCHEMA,
            type_="unique",
        )
        op.create_unique_constraint(
            "uq_guest_quota_usage_dimension",
            TABLE_NAME,
            [
                "tenant_id",
                "region",
                "guest_id",
                "product_id",
                "quota_policy_id",
                "quota_dimension",
                "dimension_key",
                "period_key",
            ],
            schema=PLATFORM_SCHEMA,
        )

    op.create_index(
        "ix_guest_quota_usage_dimension",
        TABLE_NAME,
        ["quota_dimension", "dimension_key"],
        schema=PLATFORM_SCHEMA,
    )


def downgrade() -> None:
    existing_columns = _column_names()
    if "quota_dimension" not in existing_columns:
        return

    op.drop_index(
        "ix_guest_quota_usage_dimension",
        table_name=TABLE_NAME,
        schema=PLATFORM_SCHEMA,
    )
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint(
            "uq_guest_quota_usage_dimension",
            TABLE_NAME,
            schema=PLATFORM_SCHEMA,
            type_="unique",
        )
        op.create_unique_constraint(
            "uq_guest_quota_usage_dimension",
            TABLE_NAME,
            [
                "tenant_id",
                "region",
                "guest_id",
                "product_id",
                "quota_policy_id",
                "period_key",
            ],
            schema=PLATFORM_SCHEMA,
        )
    op.drop_column(TABLE_NAME, "scenario_id", schema=PLATFORM_SCHEMA)
    op.drop_column(TABLE_NAME, "dimension_key", schema=PLATFORM_SCHEMA)
    op.drop_column(TABLE_NAME, "quota_dimension", schema=PLATFORM_SCHEMA)
