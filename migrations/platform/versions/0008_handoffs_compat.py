"""Create product handoffs for databases stamped past placeholder revision 0004."""

from __future__ import annotations

from alembic import op
from migrations.platform._handoffs_table import (
    create_product_handoffs_table,
    product_handoffs_table_exists,
)

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"


def upgrade() -> None:
    bind = op.get_bind()
    if product_handoffs_table_exists(bind, platform_schema=PLATFORM_SCHEMA):
        return
    create_product_handoffs_table(op, platform_schema=PLATFORM_SCHEMA)


def downgrade() -> None:
    # Canonical revision 0004 owns the table. Keep it when returning to 0007.
    return
