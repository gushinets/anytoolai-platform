from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from anytoolai_platform_api.schemas import (
    AtomLabAtomId,
    AtomLabAtomResponse,
    AtomLabSchemaRefsResponse,
    AtomLabVersionedSchemaRefResponse,
)
from anytoolai_platform_core.config.registry import ConfigRegistry

ATOM_LAB_METADATA_KEY = "atom_lab"
EXPECTED_ATOM_IDS = tuple(atom_id.value for atom_id in AtomLabAtomId)
LIVE_PROVIDER_POLICY_REF = "default_text_generation_v1"


class AtomLabCatalogConfigError(RuntimeError):
    pass


def build_atom_catalog(registry: ConfigRegistry) -> tuple[AtomLabAtomResponse, ...]:
    entries: dict[str, AtomLabAtomResponse] = {}
    for configuration in registry.action_configurations.values():
        raw_metadata = configuration.metadata.get(ATOM_LAB_METADATA_KEY)
        if raw_metadata is None:
            continue
        if not isinstance(raw_metadata, Mapping):
            raise AtomLabCatalogConfigError(
                f"Atom Lab metadata must be an object: {configuration.action_config_id}"
            )
        atom_id = raw_metadata.get("atom_id")
        description = raw_metadata.get("description")
        example_input = raw_metadata.get("example_input")
        if (
            not isinstance(atom_id, str)
            or atom_id not in EXPECTED_ATOM_IDS
            or not isinstance(description, str)
            or not description.strip()
            or not isinstance(example_input, Mapping)
        ):
            raise AtomLabCatalogConfigError(
                f"Atom Lab metadata is invalid: {configuration.action_config_id}"
            )
        if atom_id in entries:
            raise AtomLabCatalogConfigError(f"Duplicate Atom Lab atom_id: {atom_id}")
        if configuration.provider_policy_ref != LIVE_PROVIDER_POLICY_REF:
            raise AtomLabCatalogConfigError(
                f"Atom Lab action configuration is not live: {configuration.action_config_id}"
            )

        action = registry.get_action_definition(configuration.action_type)
        prompt = registry.get_prompt(configuration.prompt_ref)
        if action is None or prompt is None:
            raise AtomLabCatalogConfigError(
                f"Atom Lab registry references are incomplete: {configuration.action_config_id}"
            )
        input_schema = registry.get_schema(action.input_schema_ref)
        output_schema = registry.get_schema(action.output_schema_ref)
        if input_schema is None or output_schema is None:
            raise AtomLabCatalogConfigError(
                f"Atom Lab schemas are missing: {configuration.action_config_id}"
            )

        entries[atom_id] = AtomLabAtomResponse(
            atom_id=AtomLabAtomId(atom_id),
            action_type=configuration.action_type,
            base_action_config_id=configuration.action_config_id,
            prompt=prompt.content,
            prompt_ref=prompt.prompt_ref,
            input_schema=_mutable_json(input_schema.schema),
            output_schema=_mutable_json(output_schema.schema),
            schema_refs=AtomLabSchemaRefsResponse(
                input=AtomLabVersionedSchemaRefResponse(
                    schema_ref=input_schema.schema_ref,
                    version=input_schema.version,
                ),
                output=AtomLabVersionedSchemaRefResponse(
                    schema_ref=output_schema.schema_ref,
                    version=output_schema.version,
                ),
            ),
            description=description,
            example_input=_mutable_json(example_input),
        )

    missing = set(EXPECTED_ATOM_IDS) - entries.keys()
    unexpected = entries.keys() - set(EXPECTED_ATOM_IDS)
    if missing or unexpected:
        raise AtomLabCatalogConfigError(
            "Atom Lab catalog coverage mismatch: "
            f"missing={sorted(missing)}, unexpected={sorted(unexpected)}"
        )
    return tuple(entries[atom_id] for atom_id in EXPECTED_ATOM_IDS)


def get_atom_catalog_entry(registry: ConfigRegistry, atom_id: str) -> AtomLabAtomResponse | None:
    return next((entry for entry in build_atom_catalog(registry) if entry.atom_id == atom_id), None)


def _mutable_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _mutable_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_mutable_json(item) for item in value]
    if isinstance(value, list):
        return [_mutable_json(item) for item in value]
    return value
