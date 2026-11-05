"""Add standalone saved Atom Lab prompts and run provenance."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = None if context.is_offline_mode() else sa.inspect(op.get_bind())
    if inspector is None or not inspector.has_table("atom_lab_prompts", schema="platform"):
        op.create_table(
            "atom_lab_prompts",
            sa.Column("ref", sa.String(128), primary_key=True),
            sa.Column("tenant_id", sa.String(128), nullable=False),
            sa.Column("region", sa.String(64), nullable=False),
            sa.Column("atom_id", sa.String(16), nullable=False),
            sa.Column("name", sa.String(80), nullable=False),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column("source_ref", sa.String(128), nullable=False),
            sa.Column("schema_refs", postgresql.JSONB(), nullable=False),
            sa.Column("source_run_id", sa.String(128)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            schema="platform",
        )
        op.create_index(
            "ix_atom_lab_prompts_scope", "atom_lab_prompts",
            ["tenant_id", "region", "atom_id"], schema="platform",
        )
    if inspector is None or "prompt_source_ref" not in {
        column["name"] for column in inspector.get_columns("atom_lab_runs", schema="platform")
    }:
        op.add_column(
            "atom_lab_runs", sa.Column("prompt_source_ref", sa.String(128)), schema="platform",
        )


def downgrade() -> None:
    op.drop_column("atom_lab_runs", "prompt_source_ref", schema="platform")
    op.drop_table("atom_lab_prompts", schema="platform")
