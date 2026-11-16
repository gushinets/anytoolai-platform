"""Serialize paid authority installation, invalidation and execution admission."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paid_access_coherence",
        sa.Column("tenant_id", sa.String(128), primary_key=True),
        sa.Column("region", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(128), primary_key=True),
        sa.Column("revision_floor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("snapshot_revision", sa.BigInteger()),
        sa.Column("semantic_digest", sa.String(64)),
        sa.Column("snapshot", postgresql.JSONB()),
        sa.CheckConstraint("revision_floor >= 0", name="ck_paid_access_floor_nonnegative"),
        schema="platform",
    )


def downgrade() -> None:
    op.drop_table("paid_access_coherence", schema="platform")
