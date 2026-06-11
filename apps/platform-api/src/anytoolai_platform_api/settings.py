from pydantic import BaseModel


class Settings(BaseModel):
    app_env: str = "dev"
    default_tenant_id: str = "anytoolai"
    default_region: str = "default"
