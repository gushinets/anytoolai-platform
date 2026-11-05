"""Prepare execution reservation storage without activating new metering."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

PLATFORM_SCHEMA = "platform"
MAX_ALLOWANCE_QUANTITY = 2**53 - 1


def upgrade() -> None:
    op.add_column(
        "guest_quota_usage",
        sa.Column(
            "reserved_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        schema=PLATFORM_SCHEMA,
    )
    op.add_column(
        "guest_quota_usage",
        sa.Column(
            "legacy_used_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        schema=PLATFORM_SCHEMA,
    )
    op.execute("UPDATE platform.guest_quota_usage SET legacy_used_count = used_count")
    op.create_check_constraint(
        "ck_guest_quota_usage_reserved_count",
        "guest_quota_usage",
        "reserved_count >= 0",
        schema=PLATFORM_SCHEMA,
    )
    op.create_check_constraint(
        "ck_guest_quota_usage_legacy_used_count",
        "guest_quota_usage",
        "legacy_used_count >= 0 AND legacy_used_count <= used_count",
        schema=PLATFORM_SCHEMA,
    )
    op.add_column(
        "jobs",
        sa.Column(
            "consumption_mode",
            sa.String(9),
            nullable=False,
            server_default="legacy",
        ),
        schema=PLATFORM_SCHEMA,
    )
    op.create_check_constraint(
        "job_consumption_mode",
        "jobs",
        "consumption_mode IN ('legacy', 'unmetered', 'reserved')",
        schema=PLATFORM_SCHEMA,
    )
    op.create_table(
        "paid_allowance_usage",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("region", sa.String(64), nullable=False),
        sa.Column("owner_id", sa.String(128), nullable=False),
        sa.Column("allowance_id", sa.String(128), nullable=False),
        sa.Column("product_id", sa.String(128), nullable=False),
        sa.Column("metric_key", sa.String(128), nullable=False),
        sa.Column("unit", sa.String(128), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("used_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reserved_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "region",
            "allowance_id",
            name="uq_paid_allowance_usage_scope_allowance",
        ),
        sa.CheckConstraint(
            f"quantity BETWEEN 0 AND {MAX_ALLOWANCE_QUANTITY}",
            name="ck_paid_allowance_usage_quantity",
        ),
        sa.CheckConstraint(
            "used_count >= 0 AND reserved_count >= 0 AND used_count + reserved_count <= quantity",
            name="ck_paid_allowance_usage_counts",
        ),
        sa.Index("ix_paid_allowance_usage_owner", "tenant_id", "region", "owner_id"),
        schema=PLATFORM_SCHEMA,
    )

    op.create_table(
        "execution_reservations",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("region", sa.String(64), nullable=False),
        sa.Column(
            "owner_kind",
            sa.Enum(
                "guest",
                "portal_user",
                name="execution_owner_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("owner_id", sa.String(128), nullable=False),
        sa.Column("product_id", sa.String(128), nullable=False),
        sa.Column("scenario_id", sa.String(128), nullable=False),
        sa.Column("frontend_id", sa.String(128), nullable=False),
        sa.Column("scenario_session_id", sa.String(128), nullable=False),
        sa.Column("job_id", sa.String(128), nullable=False),
        sa.Column("guest_quota_usage_id", sa.String(128)),
        sa.Column("paid_allowance_usage_id", sa.String(128)),
        sa.Column(
            "replay_namespace",
            sa.Enum(
                "start",
                "handoff",
                name="execution_replay_namespace",
                native_enum=False,
                create_constraint=True,
            ),
        ),
        sa.Column("replay_key", sa.String(256)),
        sa.Column("request_hash", sa.String(64)),
        sa.Column("handoff_id", sa.String(128)),
        sa.Column(
            "state",
            sa.Enum(
                "reserved",
                "consumed",
                "released",
                name="execution_reservation_state",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("result_artifact_id", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("scenario_session_id", name="uq_execution_reservations_session"),
        sa.UniqueConstraint("job_id", name="uq_execution_reservations_job"),
        sa.UniqueConstraint(
            "tenant_id",
            "region",
            "owner_kind",
            "owner_id",
            "product_id",
            "scenario_id",
            "replay_namespace",
            "replay_key",
            name="uq_execution_reservations_owner_replay",
        ),
        sa.CheckConstraint(
            "(owner_kind = 'guest' AND guest_quota_usage_id IS NOT NULL "
            "AND paid_allowance_usage_id IS NULL) OR "
            "(owner_kind = 'portal_user' AND guest_quota_usage_id IS NULL "
            "AND paid_allowance_usage_id IS NOT NULL)",
            name="ck_execution_reservations_bucket",
        ),
        sa.CheckConstraint(
            "(replay_namespace IS NULL AND replay_key IS NULL AND request_hash IS NULL "
            "AND owner_kind = 'guest') OR "
            "(replay_namespace IS NOT NULL AND replay_key IS NOT NULL AND replay_key <> '' "
            "AND request_hash IS NOT NULL AND length(request_hash) = 64)",
            name="ck_execution_reservations_replay",
        ),
        sa.CheckConstraint(
            "replay_namespace <> 'handoff' OR (handoff_id IS NOT NULL AND replay_key = handoff_id)",
            name="ck_execution_reservations_handoff_replay",
        ),
        sa.CheckConstraint(
            "(state = 'consumed' AND result_artifact_id IS NOT NULL AND finalized_at IS NOT NULL) "
            "OR (state = 'released' AND result_artifact_id IS NULL AND finalized_at IS NOT NULL) "
            "OR (state = 'reserved' AND result_artifact_id IS NULL AND finalized_at IS NULL)",
            name="ck_execution_reservations_final_result",
        ),
        *(
            sa.ForeignKeyConstraint(
                [column],
                [f"{PLATFORM_SCHEMA}.{table}.id"],
                name=f"fk_execution_reservations_{name}",
            )
            for column, table, name in (
                ("scenario_session_id", "scenario_sessions", "session"),
                ("job_id", "jobs", "job"),
                ("guest_quota_usage_id", "guest_quota_usage", "guest_bucket"),
                ("paid_allowance_usage_id", "paid_allowance_usage", "paid_bucket"),
                ("result_artifact_id", "artifacts", "result"),
                ("handoff_id", "product_handoffs", "handoff"),
            )
        ),
        sa.Index("ix_execution_reservations_guest_bucket", "guest_quota_usage_id"),
        sa.Index("ix_execution_reservations_paid_bucket", "paid_allowance_usage_id"),
        schema=PLATFORM_SCHEMA,
    )

    # Database enforcement protects the accepted tuple even from direct SQL writers.
    op.execute("""
        CREATE FUNCTION platform.reject_paid_allowance_rebinding() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF ROW(OLD.id, OLD.tenant_id, OLD.region, OLD.owner_id, OLD.allowance_id,
                   OLD.product_id, OLD.metric_key, OLD.unit, OLD.quantity)
               IS DISTINCT FROM
               ROW(NEW.id, NEW.tenant_id, NEW.region, NEW.owner_id, NEW.allowance_id,
                   NEW.product_id, NEW.metric_key, NEW.unit, NEW.quantity) THEN
                RAISE EXCEPTION 'paid allowance binding cannot change' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER paid_allowance_immutable_binding
        BEFORE UPDATE ON platform.paid_allowance_usage
        FOR EACH ROW EXECUTE FUNCTION platform.reject_paid_allowance_rebinding()
    """)
    # Deferred validation allows job then reservation inserts in one caller-owned transaction.
    op.execute("""
        CREATE FUNCTION platform.require_job_reservation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            job_ids varchar[];
            checked_job_id varchar;
            mode varchar;
        BEGIN
            IF TG_TABLE_NAME = 'jobs' THEN
                job_ids := ARRAY[COALESCE(NEW.id, OLD.id)];
            ELSIF TG_OP = 'UPDATE' THEN
                job_ids := ARRAY[OLD.job_id, NEW.job_id];
            ELSIF TG_OP = 'DELETE' THEN
                job_ids := ARRAY[OLD.job_id];
            ELSE
                job_ids := ARRAY[NEW.job_id];
            END IF;
            FOREACH checked_job_id IN ARRAY job_ids LOOP
                SELECT consumption_mode INTO mode FROM platform.jobs WHERE id = checked_job_id;
                IF FOUND AND ((mode = 'reserved') IS DISTINCT FROM EXISTS (
                    SELECT 1 FROM platform.execution_reservations WHERE job_id = checked_job_id
                )) THEN
                    RAISE EXCEPTION 'job consumption mode and reservation disagree: %',
                        checked_job_id
                        USING ERRCODE = '23514';
                END IF;
            END LOOP;
            RETURN NULL;
        END;
        $$
    """)
    for table_name in ("jobs", "execution_reservations"):
        op.execute(f"""
            CREATE CONSTRAINT TRIGGER require_job_reservation
            AFTER INSERT OR UPDATE OR DELETE ON platform.{table_name}
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION platform.require_job_reservation()
        """)


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM platform.execution_reservations)
               OR EXISTS (SELECT 1 FROM platform.paid_allowance_usage) THEN
                RAISE EXCEPTION 'reservation history requires backup restore for rollback';
            END IF;
        END $$
    """)
    for table_name in ("jobs", "execution_reservations"):
        op.execute(f"DROP TRIGGER require_job_reservation ON platform.{table_name}")
    op.execute("DROP FUNCTION platform.require_job_reservation()")
    op.execute("DROP TRIGGER paid_allowance_immutable_binding ON platform.paid_allowance_usage")
    op.execute("DROP FUNCTION platform.reject_paid_allowance_rebinding()")
    op.drop_table("execution_reservations", schema=PLATFORM_SCHEMA)
    op.drop_table("paid_allowance_usage", schema=PLATFORM_SCHEMA)
    op.drop_constraint("job_consumption_mode", "jobs", schema=PLATFORM_SCHEMA, type_="check")
    op.drop_column("jobs", "consumption_mode", schema=PLATFORM_SCHEMA)
    op.drop_constraint(
        "ck_guest_quota_usage_legacy_used_count",
        "guest_quota_usage",
        schema=PLATFORM_SCHEMA,
        type_="check",
    )
    op.drop_constraint(
        "ck_guest_quota_usage_reserved_count",
        "guest_quota_usage",
        schema=PLATFORM_SCHEMA,
        type_="check",
    )
    op.drop_column("guest_quota_usage", "legacy_used_count", schema=PLATFORM_SCHEMA)
    op.drop_column("guest_quota_usage", "reserved_count", schema=PLATFORM_SCHEMA)
