"""Persist immutable exhaustion edges independently of workflow and delivery lifetimes."""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "allowance_exhaustion_outbox",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("region", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("allowance_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("product_id", sa.String(128), nullable=False),
        sa.Column("metric_key", sa.String(255), nullable=False),
        sa.Column("unit", sa.String(128), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_owner", sa.String(64)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(64)),
        sa.UniqueConstraint(
            "tenant_id",
            "region",
            "user_id",
            "allowance_id",
            "event_type",
            name="uq_allowance_exhaustion_identity",
        ),
        sa.CheckConstraint(
            "event_type = 'allowance_exhausted'", name="ck_allowance_exhaustion_event"
        ),
        sa.CheckConstraint(
            "quantity >= 0 AND quantity <= 9007199254740991 AND attempt_count >= 0",
            name="ck_allowance_exhaustion_counts",
        ),
        sa.CheckConstraint(
            "(lease_owner IS NULL) = (lease_expires_at IS NULL)",
            name="ck_allowance_exhaustion_lease",
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'delivered', 'parked')", name="ck_allowance_exhaustion_state"
        ),
        schema="platform",
    )
    op.create_index(
        "ix_allowance_exhaustion_due",
        "allowance_exhaustion_outbox",
        ["state", "next_attempt_at"],
        schema="platform",
    )


def downgrade() -> None:
    raise RuntimeError("Exhaustion delivery history requires a compatible backup restore.")
