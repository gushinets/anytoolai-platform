"""Shared helpers for handoff migration revisions.

Historical compatibility revision ``0008_handoffs_compat.py`` intentionally keeps its original
inline table-existence guard so that the revision remains self-contained. New handoff revisions
should use the helpers in this module instead of introducing another inline
``sa.inspect(...).has_table(...)`` variant.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa

PLATFORM_SCHEMA = "platform"
LEGACY_TARGET_SESSION_INDEX = "ix_product_handoffs_target_session"
STATUS_EXPIRY_INDEX = "ix_product_handoffs_status_expiry"


def product_handoffs_table_exists(
    bind: Any,
    *,
    platform_schema: str = PLATFORM_SCHEMA,
) -> bool:
    """Return whether the schema-qualified handoff table exists.

    This is the canonical table-existence check for new handoff migration revisions.
    """
    return sa.inspect(bind).has_table("product_handoffs", schema=platform_schema)


def product_handoffs_index_names(
    bind: Any,
    *,
    platform_schema: str = PLATFORM_SCHEMA,
) -> set[str]:
    return {
        index["name"]
        for index in sa.inspect(bind).get_indexes(
            "product_handoffs",
            schema=platform_schema,
        )
    }


def ensure_product_handoffs_indexes(
    op_module: Any,
    *,
    platform_schema: str = PLATFORM_SCHEMA,
) -> None:
    bind = op_module.get_bind()
    index_names = product_handoffs_index_names(bind, platform_schema=platform_schema)
    if LEGACY_TARGET_SESSION_INDEX in index_names:
        op_module.drop_index(
            LEGACY_TARGET_SESSION_INDEX,
            table_name="product_handoffs",
            schema=platform_schema,
        )
    if STATUS_EXPIRY_INDEX not in index_names:
        op_module.create_index(
            STATUS_EXPIRY_INDEX,
            "product_handoffs",
            ["status", "expires_at"],
            schema=platform_schema,
        )


def ensure_product_handoffs_indexes_offline(
    op_module: Any,
    *,
    platform_schema: str = PLATFORM_SCHEMA,
) -> None:
    op_module.execute(sa.text(f"DROP INDEX IF EXISTS {platform_schema}.{LEGACY_TARGET_SESSION_INDEX}"))
    op_module.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS "
            f"{platform_schema}.{STATUS_EXPIRY_INDEX} "
            f"ON {platform_schema}.product_handoffs (status, expires_at)"
        )
    )


def restore_legacy_product_handoffs_target_session_index(
    op_module: Any,
    *,
    platform_schema: str = PLATFORM_SCHEMA,
) -> None:
    bind = op_module.get_bind()
    index_names = product_handoffs_index_names(bind, platform_schema=platform_schema)
    if LEGACY_TARGET_SESSION_INDEX not in index_names:
        op_module.create_index(
            LEGACY_TARGET_SESSION_INDEX,
            "product_handoffs",
            ["target_scenario_session_id"],
            schema=platform_schema,
        )


def restore_legacy_product_handoffs_target_session_index_offline(
    op_module: Any,
    *,
    platform_schema: str = PLATFORM_SCHEMA,
) -> None:
    op_module.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS "
            f"{platform_schema}.{LEGACY_TARGET_SESSION_INDEX} "
            f"ON {platform_schema}.product_handoffs (target_scenario_session_id)"
        )
    )
