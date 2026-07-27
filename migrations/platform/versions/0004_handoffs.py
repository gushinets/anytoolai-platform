"""MVP-A backend-owned product handoffs."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from migrations.platform._handoffs_table import create_product_handoffs_table

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"


def _json_document_type() -> sa.TypeEngine:
    return sa.JSON(none_as_null=True).with_variant(
        postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
        "postgresql",
    )


def _enum_type(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    create_product_handoffs_table(
        platform_schema=PLATFORM_SCHEMA,
        json_document=_json_document_type(),
        handoff_status_type=_enum_type(
            "handoff_status",
            "created",
            "viewed",
            "accepted",
            "declined",
            "consumed",
            "expired",
            "failed",
        ),
        handoff_start_policy_type=_enum_type(
            "handoff_start_policy",
            "immediate",
            "deferred",
        ),
    )


def downgrade() -> None:
    op.drop_table("product_handoffs", schema=PLATFORM_SCHEMA)
