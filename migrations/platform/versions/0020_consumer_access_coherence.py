"""Scope paid coherence by consumer; retain the paid floor and all usage history."""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "paid_access_coherence",
        sa.Column("consumer_id", sa.String(64), nullable=False, server_default="platform-kernel"),
        schema="platform",
    )
    op.add_column(
        "paid_access_coherence",
        sa.Column("policy_floor", sa.BigInteger(), nullable=False, server_default="1"),
        schema="platform",
    )
    op.add_column(
        "paid_access_coherence",
        sa.Column("snapshot_policy_revision", sa.BigInteger()),
        schema="platform",
    )
    # V2 metadata is incompatible with V3 semantic identity. Retain R and every
    # bucket/reservation/job: only the document and its semantic metadata expire.
    op.execute(
        "UPDATE platform.paid_access_coherence "
        "SET snapshot = NULL, snapshot_revision = NULL, semantic_digest = NULL"
    )
    op.drop_constraint(
        "paid_access_coherence_pkey", "paid_access_coherence", schema="platform", type_="primary"
    )
    op.create_primary_key(
        "paid_access_coherence_pkey",
        "paid_access_coherence",
        ["consumer_id", "tenant_id", "region", "user_id"],
        schema="platform",
    )
    op.alter_column("paid_access_coherence", "consumer_id", server_default=None, schema="platform")
    op.create_check_constraint(
        "ck_paid_policy_floor_positive",
        "paid_access_coherence",
        "policy_floor >= 1",
        schema="platform",
    )


def downgrade() -> None:
    raise RuntimeError(
        "Consumer-scoped authority requires the synchronized V3 reader; "
        "restore a compatible backup instead."
    )
