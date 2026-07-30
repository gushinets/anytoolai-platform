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


def _product_handoffs_index_names(bind: sa.Connection) -> set[str]:
    return {
        index["name"]
        for index in sa.inspect(bind).get_indexes(
            "product_handoffs",
            schema=PLATFORM_SCHEMA,
        )
    }


def _ensure_product_handoffs_indexes() -> None:
    bind = op.get_bind()
    index_names = _product_handoffs_index_names(bind)
    if LEGACY_TARGET_SESSION_INDEX in index_names:
        op.drop_index(
            LEGACY_TARGET_SESSION_INDEX,
            table_name="product_handoffs",
            schema=PLATFORM_SCHEMA,
        )
    if STATUS_EXPIRY_INDEX not in index_names:
        op.create_index(
            STATUS_EXPIRY_INDEX,
            "product_handoffs",
            ["status", "expires_at"],
            schema=PLATFORM_SCHEMA,
        )


def _ensure_product_handoffs_indexes_offline() -> None:
    op.execute(sa.text(f"DROP INDEX IF EXISTS {PLATFORM_SCHEMA}.{LEGACY_TARGET_SESSION_INDEX}"))
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS "
            f"{PLATFORM_SCHEMA}.{STATUS_EXPIRY_INDEX} "
            f"ON {PLATFORM_SCHEMA}.product_handoffs (status, expires_at)"
        )
    )


def _restore_legacy_product_handoffs_target_session_index() -> None:
    bind = op.get_bind()
    index_names = _product_handoffs_index_names(bind)
    if LEGACY_TARGET_SESSION_INDEX not in index_names:
        op.create_index(
            LEGACY_TARGET_SESSION_INDEX,
            "product_handoffs",
            ["target_scenario_session_id"],
            schema=PLATFORM_SCHEMA,
        )


def _restore_legacy_product_handoffs_target_session_index_offline() -> None:
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS "
            f"{PLATFORM_SCHEMA}.{LEGACY_TARGET_SESSION_INDEX} "
            f"ON {PLATFORM_SCHEMA}.product_handoffs (target_scenario_session_id)"
        )
    )


def upgrade() -> None:
    if context.is_offline_mode():
        _ensure_product_handoffs_indexes_offline()
        return
    bind = op.get_bind()
    if not _product_handoffs_table_exists(bind):
        return
    _ensure_product_handoffs_indexes()


def downgrade() -> None:
    if context.is_offline_mode():
        _restore_legacy_product_handoffs_target_session_index_offline()
        return
    bind = op.get_bind()
    if not _product_handoffs_table_exists(bind):
        return
    _restore_legacy_product_handoffs_target_session_index()
