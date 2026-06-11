from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    tenant_id: str
    region: str
    frontend_id: str | None = None
