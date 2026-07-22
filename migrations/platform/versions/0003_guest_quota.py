"""MVP-A guest identity and quota tables."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
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
        "guest_identities",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("region", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", json_document, nullable=False),
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_guest_identities_tenant_region",
        "guest_identities",
        ["tenant_id", "region"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_guest_identities_created_at",
        "guest_identities",
        ["created_at"],
        schema=PLATFORM_SCHEMA,
    )

    op.create_table(
        "guest_quota_usage",
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
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
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
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_guest_quota_usage_guest_product",
        "guest_quota_usage",
        ["guest_id", "product_id"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_guest_quota_usage_dimension",
        "guest_quota_usage",
        ["quota_dimension", "dimension_key"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_guest_quota_usage_product_policy",
        "guest_quota_usage",
        ["product_id", "quota_policy_id"],
        schema=PLATFORM_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("guest_quota_usage", schema=PLATFORM_SCHEMA)
    op.drop_table("guest_identities", schema=PLATFORM_SCHEMA)
