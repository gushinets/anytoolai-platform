from __future__ import annotations

from enum import StrEnum

from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord

RUNTIME_SCOPE_METADATA_KEY = "runtime_scope"


class RuntimeScope(StrEnum):
    public = "public"
    atom_lab = "atom_lab"


def runtime_scope_metadata(scope: RuntimeScope) -> dict[str, str]:
    if scope is RuntimeScope.public:
        return {}
    return {RUNTIME_SCOPE_METADATA_KEY: scope.value}


def is_public_runtime_session(record: ScenarioSessionRecord) -> bool:
    value = record.metadata.get(RUNTIME_SCOPE_METADATA_KEY)
    return value is None or value == RuntimeScope.public.value


def is_atom_lab_session(record: ScenarioSessionRecord) -> bool:
    return record.metadata.get(RUNTIME_SCOPE_METADATA_KEY) == RuntimeScope.atom_lab.value
