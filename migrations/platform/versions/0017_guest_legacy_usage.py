"""Reconcile guest history accumulated after execution storage preparation."""

from __future__ import annotations

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Stabilize both sides of the accounting equation before taking the UPDATE snapshot.
    op.execute("""
        LOCK TABLE platform.guest_quota_usage, platform.execution_reservations
        IN EXCLUSIVE MODE
    """)
    op.execute("""
        UPDATE platform.guest_quota_usage AS usage
        SET legacy_used_count = usage.used_count - counts.successful_used
        FROM (
            SELECT bucket.id, count(reservation.id) AS successful_used
            FROM platform.guest_quota_usage AS bucket
            LEFT JOIN platform.execution_reservations AS reservation
              ON reservation.guest_quota_usage_id = bucket.id
             AND reservation.state = 'consumed'
            GROUP BY bucket.id
        ) AS counts
        WHERE usage.id = counts.id
          AND usage.legacy_used_count <> usage.used_count - counts.successful_used
    """)


def downgrade() -> None:
    # The corrected historical classification remains valid for the 0016 schema/runtime.
    pass
