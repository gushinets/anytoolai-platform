from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

PLATFORM_SCHEMA = "platform"
LEGACY_TARGET_SESSION_INDEX = "ix_product_handoffs_target_session"
STATUS_EXPIRY_INDEX = "ix_product_handoffs_status_expiry"


def json_document_type() -> sa.TypeEngine:
    return sa.JSON(none_as_null=True).with_variant(
        postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
        "postgresql",
    )


def enum_type(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def product_handoffs_table_exists(bind: Any, *, platform_schema: str = PLATFORM_SCHEMA) -> bool:
    return sa.inspect(bind).has_table("product_handoffs", schema=platform_schema)


def product_handoffs_index_names(bind: Any, *, platform_schema: str = PLATFORM_SCHEMA) -> set[str]:
    return {
        index["name"]
        for index in sa.inspect(bind).get_indexes(
            "product_handoffs",
            schema=platform_schema,
        )
    }


def ensure_product_handoffs_indexes(op_module: Any, *, platform_schema: str = PLATFORM_SCHEMA) -> None:
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
    if STATUS_EXPIRY_INDEX in index_names:
        op_module.drop_index(
            STATUS_EXPIRY_INDEX,
            table_name="product_handoffs",
            schema=platform_schema,
        )
    if LEGACY_TARGET_SESSION_INDEX not in index_names:
        op_module.create_index(
            LEGACY_TARGET_SESSION_INDEX,
            "product_handoffs",
            ["target_scenario_session_id"],
            schema=platform_schema,
        )


def create_product_handoffs_table(op_module: Any, *, platform_schema: str = PLATFORM_SCHEMA) -> None:
    json_document = json_document_type()
    op_module.create_table(
        "product_handoffs",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("handoff_definition_id", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("region", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column(
            "status",
            enum_type(
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
            enum_type("handoff_start_policy", "immediate", "deferred"),
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
            [f"{platform_schema}.scenario_sessions.id"],
            name="fk_product_handoffs_source_session",
        ),
        sa.ForeignKeyConstraint(
            ["source_job_id"],
            [f"{platform_schema}.jobs.id"],
            name="fk_product_handoffs_source_job",
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_id"],
            [f"{platform_schema}.artifacts.id"],
            name="fk_product_handoffs_source_artifact",
        ),
        sa.ForeignKeyConstraint(
            ["target_scenario_session_id"],
            [f"{platform_schema}.scenario_sessions.id"],
            name="fk_product_handoffs_target_session",
        ),
        sa.ForeignKeyConstraint(
            ["target_job_id"],
            [f"{platform_schema}.jobs.id"],
            name="fk_product_handoffs_target_job",
        ),
        schema=platform_schema,
    )
    op_module.create_index(
        "ix_product_handoffs_definition",
        "product_handoffs",
        ["handoff_definition_id"],
        schema=platform_schema,
    )
    op_module.create_index(
        "ix_product_handoffs_source_session",
        "product_handoffs",
        ["source_scenario_session_id"],
        schema=platform_schema,
    )
    op_module.create_index(
        STATUS_EXPIRY_INDEX,
        "product_handoffs",
        ["status", "expires_at"],
        schema=platform_schema,
    )
