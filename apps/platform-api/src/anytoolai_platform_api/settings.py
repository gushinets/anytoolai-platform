import os
import re

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

DEPLOYMENT_ACTIVATION_NAME_ENV = "ANYTOOLAI_DEPLOYMENT_ACTIVATION_NAME"
DEPLOYMENT_ACTIVATION_MARKER_ENV = "ANYTOOLAI_DEPLOYMENT_ACTIVATION_MARKER"
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
    model_config = ConfigDict(hide_input_in_errors=True)

    app_env: str = "dev"
    enabled_product_ids: frozenset[str] | None = None
    deployment_activation_name: str | None = None
    deployment_activation_marker: str | None = None
    default_tenant_id: str = "anytoolai"
    default_region: str = "ru"
    portal_service_token: SecretStr | None = Field(default=None, repr=False)
    portal_service_token_previous: SecretStr | None = Field(default=None, repr=False)
    atom_lab_run_body_max_bytes: int = Field(default=384 * 1024, gt=0)
    atom_lab_run_input_max_bytes: int = Field(default=256 * 1024, gt=0)
    atom_lab_run_prompt_max_bytes: int = Field(default=64 * 1024, gt=0)
    atom_lab_run_daily_limit: int = Field(default=100, gt=0)
    atom_lab_run_active_limit: int = Field(default=1, gt=0)
    atom_lab_preset_example_input_max_bytes: int = Field(
        default=DEFAULT_ATOM_LAB_PRESET_EXAMPLE_INPUT_MAX_BYTES,
        gt=0,
    )

    @field_validator("default_tenant_id", "default_region")
    @classmethod
    def validate_scope_identity(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("Scope identities must be nonblank without surrounding whitespace")
        return value

    @field_validator("portal_service_token", "portal_service_token_previous")
    @classmethod
    def validate_service_token(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not re.fullmatch(
            r"[A-Za-z0-9._~+/-]{32,256}={0,2}", value.get_secret_value()
        ):
            raise ValueError("Service tokens require 32–256 Bearer-safe characters")
        return value

    @model_validator(mode="after")
    def validate_service_token_rotation(self) -> "Settings":
        if self.portal_service_token_previous is not None:
            if self.portal_service_token is None:
                raise ValueError("A previous service token requires a current token")
            if self.portal_service_token_previous == self.portal_service_token:
                raise ValueError("Current and previous service tokens must differ")
        return self

    @classmethod
    def from_env(cls, *, include_atom_lab_run_limits: bool = True) -> "Settings":
        values = (
            {
                field: os.environ[env_name]
                for env_name, field in ATOM_LAB_RUN_LIMIT_ENV_FIELDS.items()
                if env_name in os.environ
            }
            if include_atom_lab_run_limits
            else {}
        )
        if "ANYTOOLAI_ENABLED_PRODUCT_IDS" in os.environ:
            values["enabled_product_ids"] = parse_product_ids(
                os.environ["ANYTOOLAI_ENABLED_PRODUCT_IDS"]
            )
        for env_name, field in {
            "ANYTOOLAI_TENANT_ID": "default_tenant_id",
            "ANYTOOLAI_REGION": "default_region",
            "ANYTOOLAI_PORTAL_SERVICE_TOKEN": "portal_service_token",
            "ANYTOOLAI_PORTAL_SERVICE_TOKEN_PREVIOUS": "portal_service_token_previous",
        }.items():
            if env_name in os.environ:
                values[field] = os.environ[env_name]
        activation_name = os.getenv(DEPLOYMENT_ACTIVATION_NAME_ENV)
        activation_marker = os.getenv(DEPLOYMENT_ACTIVATION_MARKER_ENV)
        if bool(activation_name) != bool(activation_marker):
            raise ValueError(
                f"{DEPLOYMENT_ACTIVATION_NAME_ENV} and {DEPLOYMENT_ACTIVATION_MARKER_ENV} "
                "must be set together"
            )
        if activation_name and activation_marker:
            values["deployment_activation_name"] = activation_name
            values["deployment_activation_marker"] = activation_marker
        return cls.model_validate(values)
