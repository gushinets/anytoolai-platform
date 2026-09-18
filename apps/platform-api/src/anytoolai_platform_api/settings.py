from pydantic import BaseModel, Field

DEFAULT_ATOM_LAB_PRESET_EXAMPLE_INPUT_MAX_BYTES = 256 * 1024


class Settings(BaseModel):
    app_env: str = "dev"
    default_tenant_id: str = "anytoolai"
    default_region: str = "default"
    atom_lab_preset_example_input_max_bytes: int = Field(
        default=DEFAULT_ATOM_LAB_PRESET_EXAMPLE_INPUT_MAX_BYTES,
        gt=0,
    )
