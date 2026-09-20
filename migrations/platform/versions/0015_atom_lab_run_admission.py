"""Add durable Atom Lab run admission and scoped idempotency."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"


def _column_names(table_name: str) -> set[str]:
    if context.is_offline_mode():
        return set()
    return {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns(
            table_name,
            schema=PLATFORM_SCHEMA,
        )
    }


def _named_object_exists(
    table_name: str,
    object_name: str,
    inspector_method: str,
) -> bool:
    if context.is_offline_mode():
        return False
    objects = getattr(sa.inspect(op.get_bind()), inspector_method)(
        table_name,
        schema=PLATFORM_SCHEMA,
    )
    return object_name in {item["name"] for item in objects}


def upgrade() -> None:
    run_columns = _column_names("atom_lab_runs")
    for column in (
        sa.Column("guest_id", sa.String(128)),
        sa.Column("idempotency_key", sa.String(256)),
        sa.Column("idempotency_request_hash", sa.String(64)),
    ):
        if column.name not in run_columns:
            op.add_column("atom_lab_runs", column, schema=PLATFORM_SCHEMA)

    if not _named_object_exists(
        "atom_lab_runs",
        "uq_atom_lab_runs_scope_idempotency_key",
        "get_unique_constraints",
    ):
        op.create_unique_constraint(
            "uq_atom_lab_runs_scope_idempotency_key",
            "atom_lab_runs",
            ["tenant_id", "region", "idempotency_key"],
            schema=PLATFORM_SCHEMA,
        )
    if not _named_object_exists(
        "atom_lab_runs",
        "fk_atom_lab_runs_guest",
        "get_foreign_keys",
    ):
        op.create_foreign_key(
            "fk_atom_lab_runs_guest",
            "atom_lab_runs",
            "guest_identities",
            ["guest_id"],
            ["id"],
            source_schema=PLATFORM_SCHEMA,
            referent_schema=PLATFORM_SCHEMA,
        )
    if not _named_object_exists(
        "atom_lab_runs",
        "ix_atom_lab_runs_scope_created_at",
        "get_indexes",
    ):
        op.create_index(
            "ix_atom_lab_runs_scope_created_at",
            "atom_lab_runs",
            ["tenant_id", "region", "created_at", "id"],
            schema=PLATFORM_SCHEMA,
        )

    table_exists = not context.is_offline_mode() and sa.inspect(op.get_bind()).has_table(
        "atom_lab_admission_scopes",
        schema=PLATFORM_SCHEMA,
    )
    if not table_exists:
        op.create_table(
            "atom_lab_admission_scopes",
            sa.Column("tenant_id", sa.String(128), primary_key=True),
            sa.Column("region", sa.String(64), primary_key=True),
            sa.Column("accepted_on", sa.Date(), nullable=False),
            sa.Column("accepted_count", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "accepted_count >= 0",
                name="ck_atom_lab_admission_scopes_accepted_count",
            ),
            schema=PLATFORM_SCHEMA,
        )


def downgrade() -> None:
    op.drop_table("atom_lab_admission_scopes", schema=PLATFORM_SCHEMA)
    op.drop_index(
        "ix_atom_lab_runs_scope_created_at",
        table_name="atom_lab_runs",
        schema=PLATFORM_SCHEMA,
    )
    op.drop_constraint(
        "uq_atom_lab_runs_scope_idempotency_key",
        "atom_lab_runs",
        schema=PLATFORM_SCHEMA,
        type_="unique",
    )
    op.drop_constraint(
        "fk_atom_lab_runs_guest",
        "atom_lab_runs",
        schema=PLATFORM_SCHEMA,
        type_="foreignkey",
    )
    op.drop_column("atom_lab_runs", "idempotency_request_hash", schema=PLATFORM_SCHEMA)
    op.drop_column("atom_lab_runs", "idempotency_key", schema=PLATFORM_SCHEMA)
    op.drop_column("atom_lab_runs", "guest_id", schema=PLATFORM_SCHEMA)
