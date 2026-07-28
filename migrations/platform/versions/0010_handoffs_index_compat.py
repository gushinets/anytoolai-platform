"""Repair legacy handoff indexes for already-upgraded databases."""

from __future__ import annotations

from alembic import op
from migrations.platform._handoffs_table import (
    ensure_product_handoffs_indexes,
    product_handoffs_table_exists,
    restore_legacy_product_handoffs_target_session_index,
)

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"


def upgrade() -> None:
    bind = op.get_bind()
    if not product_handoffs_table_exists(bind, platform_schema=PLATFORM_SCHEMA):
        return
    ensure_product_handoffs_indexes(op, platform_schema=PLATFORM_SCHEMA)


def downgrade() -> None:
    bind = op.get_bind()
    if not product_handoffs_table_exists(bind, platform_schema=PLATFORM_SCHEMA):
        return
    restore_legacy_product_handoffs_target_session_index(
        op,
        platform_schema=PLATFORM_SCHEMA,
    )
