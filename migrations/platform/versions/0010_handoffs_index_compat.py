"""Repair legacy handoff indexes for already-upgraded databases."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"
LEGACY_TARGET_SESSION_INDEX = "ix_product_handoffs_target_session"
STATUS_EXPIRY_INDEX = "ix_product_handoffs_status_expiry"


def _product_handoffs_table_exists(bind: sa.Connection) -> bool:
    return sa.inspect(bind).has_table("product_handoffs", schema=PLATFORM_SCHEMA)


def _ensure_product_handoffs_indexes() -> None:
    op.execute(sa.text(f"DROP INDEX IF EXISTS {PLATFORM_SCHEMA}.{LEGACY_TARGET_SESSION_INDEX}"))
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS "
            f"{STATUS_EXPIRY_INDEX} "
            f"ON {PLATFORM_SCHEMA}.product_handoffs (status, expires_at)"
        )
    )


def _restore_legacy_product_handoffs_target_session_index() -> None:
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS "
            f"{LEGACY_TARGET_SESSION_INDEX} "
            f"ON {PLATFORM_SCHEMA}.product_handoffs (target_scenario_session_id)"
        )
    )


def upgrade() -> None:
    if context.is_offline_mode():
        _ensure_product_handoffs_indexes()
        return
    bind = op.get_bind()
    if not _product_handoffs_table_exists(bind):
        return
    _ensure_product_handoffs_indexes()


def downgrade() -> None:
    if context.is_offline_mode():
        _restore_legacy_product_handoffs_target_session_index()
        return
    bind = op.get_bind()
    if not _product_handoffs_table_exists(bind):
        return
    _restore_legacy_product_handoffs_target_session_index()
