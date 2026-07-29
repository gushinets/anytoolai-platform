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
