"""Repair legacy handoff indexes for already-upgraded databases."""

from __future__ import annotations

from alembic import context, op
from migrations.platform._handoffs_table import (
    ensure_product_handoffs_indexes,
    ensure_product_handoffs_indexes_offline,
    product_handoffs_table_exists,
    restore_legacy_product_handoffs_target_session_index,
    restore_legacy_product_handoffs_target_session_index_offline,
)

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"


def upgrade() -> None:
    if context.is_offline_mode():
        ensure_product_handoffs_indexes_offline(op, platform_schema=PLATFORM_SCHEMA)
        return
    bind = op.get_bind()
    if not product_handoffs_table_exists(bind, platform_schema=PLATFORM_SCHEMA):
        return
    ensure_product_handoffs_indexes(op, platform_schema=PLATFORM_SCHEMA)


def downgrade() -> None:
    if context.is_offline_mode():
        restore_legacy_product_handoffs_target_session_index_offline(
            op,
            platform_schema=PLATFORM_SCHEMA,
        )
        return
    bind = op.get_bind()
    if not product_handoffs_table_exists(bind, platform_schema=PLATFORM_SCHEMA):
        return
    restore_legacy_product_handoffs_target_session_index(
        op,
        platform_schema=PLATFORM_SCHEMA,
    )
