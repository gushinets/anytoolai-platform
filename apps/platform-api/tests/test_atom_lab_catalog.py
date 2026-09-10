from __future__ import annotations

from pathlib import Path

import pytest
from anytoolai_platform_actions.structured_llm.cross_validation import (
    build_input_validators,
)
from anytoolai_platform_api.atom_lab.catalog import EXPECTED_ATOM_IDS, build_atom_catalog
from anytoolai_platform_core.config.loader import ConfigLoader
from jsonschema import validate as validate_json_schema

CONFIG_ROOT = Path(__file__).resolve().parents[3] / "configs" / "kernel"


@pytest.fixture(scope="module")
def catalog_payloads() -> list[dict[str, object]]:
    registry = ConfigLoader(CONFIG_ROOT).load()
    return [item.model_dump(mode="json") for item in build_atom_catalog(registry)]


def test_atom_lab_catalog_contains_all_eleven_atoms_in_stable_order(
    catalog_payloads: list[dict[str, object]],
) -> None:
    assert [item["atom_id"] for item in catalog_payloads] == [
        "A01",
        "A02",
        "A03",
        "A04",
        "A05",
        "A06",
        "A07",
        "A08",
        "A09",
        "A10",
        "A11",
    ]
    assert len({item["action_type"] for item in catalog_payloads}) == len(EXPECTED_ATOM_IDS)
    assert all(str(item["base_action_config_id"]).endswith("_live_v1") for item in catalog_payloads)


def test_atom_lab_catalog_serializes_the_exact_public_contract(
    catalog_payloads: list[dict[str, object]],
) -> None:
    expected_keys = {
        "atom_id",
        "action_type",
        "base_action_config_id",
        "prompt",
        "prompt_ref",
        "input_schema",
        "output_schema",
        "schema_refs",
        "description",
        "example_input",
    }
    assert all(set(item) == expected_keys for item in catalog_payloads)

    extract = catalog_payloads[0]
    assert extract["action_type"] == "text.extract_structured_fields"
    assert extract["base_action_config_id"] == "kernel_demo.extract_structured_fields_live_v1"
    assert extract["prompt_ref"] == "kernel_demo.extract_structured_fields.v1"
    assert extract["schema_refs"] == {
        "input": {"schema_ref": "kernel.schemas.extract_input_v1", "version": 1},
        "output": {"schema_ref": "kernel.schemas.extract_output_v1", "version": 1},
    }
    assert extract["description"] == (
        "Извлекает из исходного текста значения полей, заданных типизированным списком."
    )
    assert extract["example_input"] == {
        "source_text": "Срок проекта — 30 сентября, бюджет — 120 000 рублей.",
        "fields": [
            {
                "name": "deadline",
                "type": "date",
                "description": "Срок завершения проекта.",
                "required": True,
            },
            {
                "name": "budget",
                "type": "number",
                "description": "Бюджет проекта в рублях.",
                "required": False,
            },
        ],
        "strict": True,
    }
    assert isinstance(extract["prompt"], str) and extract["prompt"]

    document = catalog_payloads[9]
    assert document["action_type"] == "document.generate_from_template"
    assert document["example_input"] == {
        "template_ref": "project_summary_v1",
        "data": {
            "project": "Внутренняя лаборатория атомов",
            "status": "готово к проверке",
        },
        "style": "concise",
    }


def test_every_atom_lab_example_passes_the_runtime_input_contracts() -> None:
    registry = ConfigLoader(CONFIG_ROOT).load()
    input_validators = build_input_validators(registry.action_definitions)

    for atom in build_atom_catalog(registry):
        action = registry.get_action_definition(atom.action_type)
        assert action is not None
        validate_json_schema(instance=atom.example_input, schema=atom.input_schema)
        validator = input_validators.get(atom.action_type)
        if validator is not None:
            validator.validate(input_payload=atom.example_input)


def test_catalog_uses_config_metadata_instead_of_a_parallel_python_mapping() -> None:
    registry = ConfigLoader(CONFIG_ROOT).load()
    configuration = registry.get_action_configuration(
        "kernel_demo.extract_structured_fields_live_v1"
    )
    assert configuration is not None
    assert configuration.metadata["atom_lab"]["atom_id"] == "A01"
