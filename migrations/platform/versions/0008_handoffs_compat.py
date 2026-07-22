"""Create product handoffs for databases stamped past placeholder revision 0004."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("product_handoffs", schema=PLATFORM_SCHEMA):
        return
    migration_path = Path(__file__).with_name("0004_handoffs.py")
    spec = importlib.util.spec_from_file_location("anytoolai_migration_0004", migration_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load canonical handoff migration")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade()


def downgrade() -> None:
    # Canonical revision 0004 owns the table. Keep it when returning to 0007.
    return
