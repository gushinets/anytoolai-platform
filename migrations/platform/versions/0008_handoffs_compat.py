"""Create product handoffs for databases stamped past placeholder revision 0004."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
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
    bind = op.get_bind()
    if sa.inspect(bind).has_table("product_handoffs", schema=PLATFORM_SCHEMA):
        return
    json_document = _json_document_type()
    op.create_table(
        "product_handoffs",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("handoff_definition_id", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("region", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column(
            "status",
            _enum_type(
                "handoff_status",
                "created",
                "viewed",
                "accepted",
                "declined",
                "consumed",
                "expired",
                "failed",
            ),
            nullable=False,
        ),
        sa.Column("source_product_id", sa.String(length=128), nullable=False),
        sa.Column("source_frontend_id", sa.String(length=128), nullable=False),
        sa.Column("source_scenario_id", sa.String(length=128), nullable=False),
        sa.Column("source_scenario_session_id", sa.String(length=128), nullable=False),
        sa.Column("source_job_id", sa.String(length=128), nullable=False),
        sa.Column("source_artifact_id", sa.String(length=128), nullable=False),
        sa.Column("target_product_id", sa.String(length=128), nullable=False),
        sa.Column("target_frontend_id", sa.String(length=128), nullable=False),
        sa.Column("target_scenario_id", sa.String(length=128), nullable=False),
        sa.Column("target_scenario_session_id", sa.String(length=128), unique=True),
        sa.Column("target_job_id", sa.String(length=128)),
        sa.Column("scenario_chain_id", sa.String(length=128), nullable=False),
        sa.Column("created_by_guest_id", sa.String(length=128)),
        sa.Column("accepted_by_guest_id", sa.String(length=128)),
        sa.Column("accepted_from_frontend_instance_id", sa.String(length=128)),
        sa.Column("consent_required", sa.Boolean(), nullable=False),
        sa.Column(
            "target_start_policy",
            _enum_type("handoff_start_policy", "immediate", "deferred"),
            nullable=False,
        ),
        sa.Column("context_payload", json_document, nullable=False),
        sa.Column("preview_payload", json_document, nullable=False),
        sa.Column("error_code", sa.String(length=128)),
        sa.Column("metadata", json_document, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True)),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("declined_at", sa.DateTime(timezone=True)),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("expired_at", sa.DateTime(timezone=True)),
        sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["source_scenario_session_id"],
            [f"{PLATFORM_SCHEMA}.scenario_sessions.id"],
            name="fk_product_handoffs_source_session",
        ),
        sa.ForeignKeyConstraint(
            ["source_job_id"],
            [f"{PLATFORM_SCHEMA}.jobs.id"],
            name="fk_product_handoffs_source_job",
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_id"],
            [f"{PLATFORM_SCHEMA}.artifacts.id"],
            name="fk_product_handoffs_source_artifact",
        ),
        sa.ForeignKeyConstraint(
            ["target_scenario_session_id"],
            [f"{PLATFORM_SCHEMA}.scenario_sessions.id"],
            name="fk_product_handoffs_target_session",
        ),
        sa.ForeignKeyConstraint(
            ["target_job_id"],
            [f"{PLATFORM_SCHEMA}.jobs.id"],
            name="fk_product_handoffs_target_job",
        ),
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_product_handoffs_definition",
        "product_handoffs",
        ["handoff_definition_id"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_product_handoffs_source_session",
        "product_handoffs",
        ["source_scenario_session_id"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_product_handoffs_target_session",
        "product_handoffs",
        ["target_scenario_session_id"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_product_handoffs_status_expiry",
        "product_handoffs",
        ["status", "expires_at"],
        schema=PLATFORM_SCHEMA,
    )


def downgrade() -> None:
    # Canonical revision 0004 owns the table. Keep it when returning to 0007.
    return
