"""Add durable OpenAI model catalog cache and refresh lease."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"


def _json_document_type() -> sa.TypeEngine:
    return sa.JSON(none_as_null=True).with_variant(
        postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "postgresql"
    )


def upgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        if sa.inspect(bind).has_table("model_catalog_state", schema=PLATFORM_SCHEMA):
            return
    op.create_table(
        "model_catalog_state",
        sa.Column("account_scope", sa.String(128), primary_key=True),
        sa.Column("snapshot_id", sa.String(128)),
        sa.Column("snapshot", _json_document_type()),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_requested_at", sa.DateTime(timezone=True)),
        sa.Column("lease_id", sa.String(128)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(512)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=PLATFORM_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("model_catalog_state", schema=PLATFORM_SCHEMA)
