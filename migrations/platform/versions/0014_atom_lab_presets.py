"""Add immutable Atom Lab preset identities and versions."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"


def _json_document_type() -> sa.TypeEngine:
    return sa.JSON(none_as_null=True).with_variant(
        postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "postgresql"
    )


def upgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        if sa.inspect(bind).has_table("atom_lab_presets", schema=PLATFORM_SCHEMA):
            return
    op.create_table(
        "atom_lab_presets",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("region", sa.String(64), nullable=False),
        sa.Column("latest_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_atom_lab_presets_scope",
        "atom_lab_presets",
        ["tenant_id", "region"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_atom_lab_presets_created_at",
        "atom_lab_presets",
        ["created_at", "id"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_table(
        "atom_lab_preset_versions",
        sa.Column("preset_id", sa.String(128), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("region", sa.String(64), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("atom_id", sa.String(16), nullable=False),
        sa.Column("base_action_config_id", sa.String(128), nullable=False),
        sa.Column("input_schema_ref", sa.String(128), nullable=False),
        sa.Column("input_schema_version", sa.Integer(), nullable=False),
        sa.Column("output_schema_ref", sa.String(128), nullable=False),
        sa.Column("output_schema_version", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("prompt_ref", sa.String(128), nullable=False),
        sa.Column("model_id", sa.String(256), nullable=False),
        sa.Column("reasoning_effort", sa.String(32)),
        sa.Column("fixed_fields", _json_document_type(), nullable=False),
        sa.Column("example_input", _json_document_type(), nullable=False),
        sa.Column("source_run_id", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["preset_id"],
            [f"{PLATFORM_SCHEMA}.atom_lab_presets.id"],
            name="fk_atom_lab_preset_versions_preset",
        ),
        sa.ForeignKeyConstraint(
            ["source_run_id"],
            [f"{PLATFORM_SCHEMA}.atom_lab_runs.id"],
            name="fk_atom_lab_preset_versions_source_run",
        ),
        sa.UniqueConstraint(
            "preset_id",
            "version",
            name="uq_atom_lab_preset_versions_identity",
        ),
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_atom_lab_preset_versions_scope",
        "atom_lab_preset_versions",
        ["tenant_id", "region"],
        schema=PLATFORM_SCHEMA,
    )
    op.create_check_constraint(
        "ck_atom_lab_runs_complete_preset_ref",
        "atom_lab_runs",
        "(preset_id IS NULL AND preset_version IS NULL) OR "
        "(preset_id IS NOT NULL AND preset_version IS NOT NULL)",
        schema=PLATFORM_SCHEMA,
    )
    op.create_foreign_key(
        "fk_atom_lab_runs_preset_version",
        "atom_lab_runs",
        "atom_lab_preset_versions",
        ["preset_id", "preset_version"],
        ["preset_id", "version"],
        source_schema=PLATFORM_SCHEMA,
        referent_schema=PLATFORM_SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_atom_lab_runs_preset_version",
        "atom_lab_runs",
        schema=PLATFORM_SCHEMA,
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_atom_lab_runs_complete_preset_ref",
        "atom_lab_runs",
        schema=PLATFORM_SCHEMA,
        type_="check",
    )
    op.drop_table("atom_lab_preset_versions", schema=PLATFORM_SCHEMA)
    op.drop_table("atom_lab_presets", schema=PLATFORM_SCHEMA)
