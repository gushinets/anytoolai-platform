import os

from pydantic import BaseModel, Field

DEFAULT_ATOM_LAB_PRESET_EXAMPLE_INPUT_MAX_BYTES = 256 * 1024
ATOM_LAB_RUN_LIMIT_ENV_FIELDS = {
    "ANYTOOLAI_ATOM_LAB_RUN_BODY_MAX_BYTES": "atom_lab_run_body_max_bytes",
    "ANYTOOLAI_ATOM_LAB_RUN_INPUT_MAX_BYTES": "atom_lab_run_input_max_bytes",
    "ANYTOOLAI_ATOM_LAB_RUN_PROMPT_MAX_BYTES": "atom_lab_run_prompt_max_bytes",
    "ANYTOOLAI_ATOM_LAB_RUN_DAILY_LIMIT": "atom_lab_run_daily_limit",
    "ANYTOOLAI_ATOM_LAB_RUN_ACTIVE_LIMIT": "atom_lab_run_active_limit",
}


def parse_product_ids(raw: str) -> frozenset[str]:
    product_ids = [item.strip() for item in raw.split(",")]
    if any(not product_id for product_id in product_ids):
        raise ValueError("ANYTOOLAI_ENABLED_PRODUCT_IDS has an empty CSV member")
    return frozenset(product_ids)


class Settings(BaseModel):
    app_env: str = "dev"
    enabled_product_ids: frozenset[str] | None = None
    default_tenant_id: str = "anytoolai"
    default_region: str = "default"
    atom_lab_run_body_max_bytes: int = Field(default=384 * 1024, gt=0)
    atom_lab_run_input_max_bytes: int = Field(default=256 * 1024, gt=0)
    atom_lab_run_prompt_max_bytes: int = Field(default=64 * 1024, gt=0)
    atom_lab_run_daily_limit: int = Field(default=100, gt=0)
    atom_lab_run_active_limit: int = Field(default=1, gt=0)
    atom_lab_preset_example_input_max_bytes: int = Field(
        default=DEFAULT_ATOM_LAB_PRESET_EXAMPLE_INPUT_MAX_BYTES,
        gt=0,
    )

    @classmethod
    def from_env(cls) -> "Settings":
        values = {
            field: os.environ[env_name]
            for env_name, field in ATOM_LAB_RUN_LIMIT_ENV_FIELDS.items()
            if env_name in os.environ
        }
        if "ANYTOOLAI_ENABLED_PRODUCT_IDS" in os.environ:
            values["enabled_product_ids"] = parse_product_ids(
                os.environ["ANYTOOLAI_ENABLED_PRODUCT_IDS"]
            )
        return cls.model_validate(values)
