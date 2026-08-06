"""Add event-log quota recovery audit lookup index."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"
INDEX_NAME = "ix_event_log_quota_recovery_audit"


def _event_log_table_exists(bind: sa.Connection) -> bool:
    return sa.inspect(bind).has_table("event_log", schema=PLATFORM_SCHEMA)


def _create_index() -> None:
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS "
            f"{INDEX_NAME} "
            f"ON {PLATFORM_SCHEMA}.event_log ("
            "event_type, tenant_id, region, product_id, frontend_id, guest_id, "
            "scenario_session_id, scenario_chain_id, handoff_id, error_code"
            ")"
        )
    )


def _drop_index() -> None:
    op.execute(sa.text(f"DROP INDEX IF EXISTS {PLATFORM_SCHEMA}.{INDEX_NAME}"))


def upgrade() -> None:
    if context.is_offline_mode():
        _create_index()
        return
    bind = op.get_bind()
    if not _event_log_table_exists(bind):
        return
    _create_index()


def downgrade() -> None:
    if context.is_offline_mode():
        _drop_index()
        return
    bind = op.get_bind()
    if not _event_log_table_exists(bind):
        return
    _drop_index()
