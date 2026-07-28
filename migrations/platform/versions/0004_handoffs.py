"""MVP-A backend-owned product handoffs."""

from __future__ import annotations

from alembic import op
from migrations.platform._handoffs_table import create_product_handoffs_table

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"


def upgrade() -> None:
    create_product_handoffs_table(op, platform_schema=PLATFORM_SCHEMA)


def downgrade() -> None:
    op.drop_table("product_handoffs", schema=PLATFORM_SCHEMA)
