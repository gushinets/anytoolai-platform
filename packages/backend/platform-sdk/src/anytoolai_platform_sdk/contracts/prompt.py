from __future__ import annotations

from pydantic import Field

from anytoolai_platform_sdk.contracts.base import ContractModel


class PromptRef(ContractModel):
    prompt_ref: str
    version: int = Field(ge=1)
    output_schema_ref: str
    template_path: str | None = None
    input_variables: list[str] = Field(default_factory=list)
