"""Add immutable Atom Lab run snapshots."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"


def _json_document_type() -> sa.TypeEngine:
    return sa.JSON(none_as_null=True).with_variant(
        postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), "postgresql"
    )


def upgrade() -> None:
    json_document = _json_document_type()
    op.create_table(
        "atom_lab_runs",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("region", sa.String(64), nullable=False),
        sa.Column("product_id", sa.String(128), nullable=False),
        sa.Column("frontend_id", sa.String(128), nullable=False),
        sa.Column("scenario_session_id", sa.String(128), nullable=False, unique=True),
        sa.Column("job_id", sa.String(128), nullable=False, unique=True),
        sa.Column("atom_id", sa.String(16), nullable=False),
        sa.Column("scenario_id", sa.String(128), nullable=False),
        sa.Column("scenario_version", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.String(128), nullable=False),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column("step_id", sa.String(128), nullable=False),
        sa.Column("action_type", sa.String(128), nullable=False),
        sa.Column("action_definition_version", sa.Integer(), nullable=False),
        sa.Column("action_config_id", sa.String(128), nullable=False),
        sa.Column("action_config_schema_version", sa.Integer(), nullable=False),
        sa.Column("prompt_ref", sa.String(128), nullable=False),
        sa.Column("prompt_version", sa.Integer(), nullable=False),
        sa.Column("base_prompt", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("input_schema_ref", sa.String(128), nullable=False),
        sa.Column("input_schema_version", sa.Integer(), nullable=False),
        sa.Column("input_schema", json_document, nullable=False),
        sa.Column("output_schema_ref", sa.String(128), nullable=False),
        sa.Column("output_schema_version", sa.Integer(), nullable=False),
        sa.Column("output_schema", json_document, nullable=False),
        sa.Column("input_payload", json_document, nullable=False),
        sa.Column("provider_policy_ref", sa.String(128), nullable=False),
        sa.Column("provider_policy", json_document, nullable=False),
        sa.Column("model_id", sa.String(256), nullable=False),
        sa.Column("reasoning_effort", sa.String(32)),
        sa.Column("capability_snapshot_id", sa.String(128), nullable=False),
        sa.Column("capability_provenance", json_document, nullable=False),
        sa.Column("workflow_definition", json_document, nullable=False),
        sa.Column("action_definition", json_document, nullable=False),
        sa.Column("action_config_definition", json_document, nullable=False),
        sa.Column("execution_definition_hash", sa.String(64), nullable=False),
        sa.Column("preset_id", sa.String(128)),
        sa.Column("preset_version", sa.Integer()),
        sa.Column("action_run_id", sa.String(128)),
        sa.Column("artifact_id", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["scenario_session_id"],
            ["platform.scenario_sessions.id"],
            name="fk_atom_lab_runs_scenario_session",
        ),
        sa.ForeignKeyConstraint(["job_id"], ["platform.jobs.id"], name="fk_atom_lab_runs_job"),
        sa.ForeignKeyConstraint(
            ["action_run_id"], ["platform.action_runs.id"], name="fk_atom_lab_runs_action_run"
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"], ["platform.artifacts.id"], name="fk_atom_lab_runs_artifact"
        ),
        schema=PLATFORM_SCHEMA,
    )
    op.create_index(
        "ix_atom_lab_runs_created_at", "atom_lab_runs", ["created_at"], schema=PLATFORM_SCHEMA
    )
    op.create_index(
        "ix_atom_lab_runs_scope",
        "atom_lab_runs",
        ["tenant_id", "region", "product_id"],
        schema=PLATFORM_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_atom_lab_runs_scope", table_name="atom_lab_runs", schema=PLATFORM_SCHEMA)
    op.drop_index("ix_atom_lab_runs_created_at", table_name="atom_lab_runs", schema=PLATFORM_SCHEMA)
    op.drop_table("atom_lab_runs", schema=PLATFORM_SCHEMA)
