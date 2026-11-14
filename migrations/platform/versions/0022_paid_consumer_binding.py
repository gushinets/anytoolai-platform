"""Bind retained paid history without changing ANY-507 identity or counters."""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paid_consumer_binding",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("consumer_id", sa.String(64), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_paid_consumer_singleton"),
        schema="platform",
    )
    # Keep the same ownership checks in online upgrades and emitted offline SQL.
    # Alembic's transaction also rolls back the table if history is ambiguous.
    op.execute("""
        DO $$
        DECLARE
            consumer_count integer;
            retained_consumer varchar(64);
        BEGIN
            SELECT COUNT(DISTINCT consumer_id), MIN(consumer_id)
                INTO consumer_count, retained_consumer
                FROM platform.paid_access_coherence;
            IF consumer_count > 1 THEN
                RAISE EXCEPTION
                    'Paid history has multiple consumers; reconcile ownership before migration.';
            END IF;
            IF (
                EXISTS (SELECT 1 FROM platform.paid_allowance_usage)
                OR EXISTS (SELECT 1 FROM platform.execution_reservations
                           WHERE owner_kind = 'portal_user')
                OR EXISTS (SELECT 1 FROM platform.allowance_exhaustion_outbox)
                OR EXISTS (SELECT 1 FROM platform.scenario_sessions
                           WHERE metadata->'execution_owner'->>'owner_kind' = 'portal_user')
            ) THEN
                -- Coherence can postdate paid history, including for the same
                -- user. It cannot attribute consumer-less legacy records to a
                -- custom audience; refuse rather than silently transfer them.
                IF retained_consumer IS NOT NULL AND retained_consumer <> 'platform-kernel' THEN
                    RAISE EXCEPTION
                        'Paid history has unproven consumer ownership; reconcile before migration.';
                END IF;
                retained_consumer := 'platform-kernel';
            END IF;
            IF retained_consumer IS NOT NULL THEN
                INSERT INTO platform.paid_consumer_binding (id, consumer_id)
                    VALUES (1, retained_consumer);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    raise RuntimeError("Paid consumer ownership requires a compatible backup restore.")
