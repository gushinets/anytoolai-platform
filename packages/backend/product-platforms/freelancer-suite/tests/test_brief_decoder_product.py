"""ANY-232 full-check-covered deeper evidence for the brief_decoder product: config-graph shape,
renderer-contract agreement, fixture/schema agreement, mapping-path safety, and the "product code
contains no PydanticAI/LiteLLM/provider SDK/model-string usage" acceptance criterion.

Reads raw YAML/JSON instead of ConfigLoader -- ATAI007 forbids product-platforms code, tests
included, from importing anytoolai_platform_core (same reason as
test_client_update_writer_product.py). Config-load through the real composition boundary and the
end-to-end runs live in
apps/platform-api/tests/test_brief_decoder_bundle.py (quick-check).
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import yaml
from anytoolai_freelancer_suite.bundle import FreelancerSuiteBundle

REPO_ROOT = Path(__file__).resolve().parents[5]
KERNEL_DIR = REPO_ROOT / "configs" / "kernel"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "provider" / "fake_provider_outputs"
(PRODUCT_DIR,) = (
    root for root in FreelancerSuiteBundle().config_roots() if root.name == "brief_decoder"
)

WORKFLOW_ID = "brief_decoder.decode_v1"
STEP_ACTION_TYPES = (
    "text.extract_structured_fields",
    "text.detect_issues_by_taxonomy",
    "text.generate_clarifying_questions",
    "document.generate_from_template",
)
# fixture stem -> kernel schema its response_json must satisfy (the atom's own output schema)
FIXTURE_KERNEL_SCHEMAS = {
    "brief_decoder.extract_brief_v1": "kernel.schemas.extract_output_v1",
    "brief_decoder.detect_issues_v1": "kernel.schemas.issue_detection_output_v1",
    "brief_decoder.generate_questions_v1": "kernel.schemas.generate_questions_output_v1",
    "brief_decoder.generate_summary_v1": "kernel.schemas.generate_document_output_v1",
}


def _load_test_support_module() -> Any:
    # Dynamic-load by explicit path, same pattern test_client_update_writer_product.py and
    # test_proposal_ai_product.py already use for this shared module (round #2 code review,
    # finding #2: this file used to duplicate _load_validate_architecture_module()/
    # FORBIDDEN_TOKENS/_load_yaml() verbatim instead of loading _test_support.py like its
    # siblings already do).
    path = Path(__file__).resolve().parent / "_test_support.py"
    spec = importlib.util.spec_from_file_location("freelancer_suite_test_support", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_test_support = _load_test_support_module()
FORBIDDEN_TOKENS = _test_support.FORBIDDEN_PROVIDER_TERMS


def _forbidden_token_pattern(token: str) -> re.Pattern[str]:
    if re.fullmatch(r"[A-Za-z_]+", token):
        return re.compile(rf"\b{re.escape(token)}\b", re.IGNORECASE)
    return re.compile(re.escape(token), re.IGNORECASE)


def _load_yaml(relative_path: str) -> dict[str, Any]:
    return _test_support.load_yaml(PRODUCT_DIR, relative_path)


def _load_schema(schema_ref: str) -> dict[str, Any]:
    if schema_ref.startswith("kernel."):
        manifest_dir = KERNEL_DIR
        manifest = yaml.safe_load((manifest_dir / "schemas.yaml").read_text(encoding="utf-8"))
    else:
        manifest_dir = PRODUCT_DIR
        manifest = _load_yaml("schemas.yaml")
    (entry,) = (item for item in manifest["schemas"] if item["schema_ref"] == schema_ref)
    return json.loads((manifest_dir / entry["file_path"]).read_text(encoding="utf-8"))


def _workflow() -> dict[str, Any]:
    (workflow,) = _load_yaml("workflows.yaml")["workflows"]
    return workflow


def _steps() -> dict[str, dict[str, Any]]:
    return {step["step_id"]: step for step in _workflow()["steps"]}


def _literal(value: str) -> Any:
    assert value.startswith("literal:"), value
    return json.loads(value[len("literal:") :])


def _fixture_response(stem: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / f"{stem}.json").read_text(encoding="utf-8"))["response_json"]


def test_product_directory_contains_no_python_or_forbidden_provider_references() -> None:
    all_files = [path for path in PRODUCT_DIR.rglob("*") if path.is_file()]
    assert all_files

    python_files = [path for path in all_files if path.suffix == ".py"]
    assert python_files == [], f"product config must be YAML/JSON/Markdown only: {python_files}"

    for path in all_files:
        content = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            assert _forbidden_token_pattern(token).search(content) is None, (path, token)


def test_workflow_uses_only_generic_atom_action_types_with_backend_resolved_policies() -> None:
    action_configs = {
        entry["action_config_id"]: entry
        for entry in _load_yaml("action_configs.yaml")["action_configs"]
    }
    steps = _workflow()["steps"]

    assert tuple(action_configs[step["action_config_id"]]["action_type"] for step in steps) == (
        STEP_ACTION_TYPES
    )
    # A policy ref is the only provider knob a product config may carry -- never a model string.
    assert {entry["provider_policy_ref"] for entry in action_configs.values()} == {
        "default_fake_provider_v1"
    }
    for entry in action_configs.values():
        assert set(entry) == {
            "action_config_id",
            "action_type",
            "prompt_ref",
            "provider_policy_ref",
        }


def test_product_has_exactly_one_scenario_and_one_workflow() -> None:
    """Brief Decoder is a one-run product (atom-ready-product-inventory.md): no second run, so no
    "explicit user-selected string" input exists to be indexed out of an array."""
    assert _load_yaml("product.yaml")["scenarios"] == [WORKFLOW_ID]
    (scenario,) = _load_yaml("scenarios.yaml")["scenarios"]
    assert scenario["scenario_id"] == scenario["workflow_id"] == WORKFLOW_ID
    assert _workflow()["workflow_id"] == WORKFLOW_ID
    assert scenario["allowed_next_actions"] == ["copy_result"]


def test_no_mapping_path_uses_brackets_or_numeric_segments() -> None:
    """Bracket indexing is rejected by config validation, but a numeric dotted segment
    (`...issues.0.description`) passes it and only fails at runtime -- pin both here."""
    paths: list[str] = []
    for step in _workflow()["steps"]:
        for mapping in (step.get("input_mapping", {}), step.get("output_mapping", {})):
            for target, source in mapping.items():
                paths.append(target)
                if not source.startswith("literal:"):
                    paths.append(source.removeprefix("?"))
        if "when" in step:
            paths.append(step["when"])

    assert paths
    for path in paths:
        assert "[" not in path and "]" not in path, path
        assert not any(segment.isdigit() for segment in path.split(".")), path


def test_every_step_writes_its_own_key_of_the_composed_workflow_output() -> None:
    output_keys = {
        target.removeprefix("context.workflow_output.")
        for step in _workflow()["steps"]
        for target in step.get("output_mapping", {})
        if target.startswith("context.workflow_output.")
    }
    all_targets = [t for step in _workflow()["steps"] for t in step.get("output_mapping", {})]
    schema = _load_schema("brief_decoder.decode_output_v1")

    assert all(t.startswith("context.workflow_output.") for t in all_targets)  # never whole
    assert output_keys == set(schema["properties"]) == set(schema["required"])


def test_a05_is_guarded_and_a10_reads_its_output_optionally() -> None:
    """A04's `issues` may be empty but A05's input requires at least one."""
    steps = _steps()
    assert steps["generate_questions"]["when"] == "steps.detect_issues.output.issues"
    seeded_questions = steps["detect_issues"]["output_mapping"]["context.workflow_output.questions"]
    assert _literal(seeded_questions) == []
    assert (
        steps["generate_document"]["input_mapping"]["data.questions"]
        == "?steps.generate_questions.output.questions"
    )


# A01 field-spec `type` -> the JSON-schema shape decode_output_v1 must declare for that field in
# `brief.values`. Code review finding (round #1, finding #8): a names-only comparison would miss
# e.g. `target_audience` silently changing from `string` to `array_of_strings` in the literal.
_A01_TYPE_TO_JSON_SCHEMA_TYPE = {
    "string": {"type": "string"},
    "array_of_strings": {"type": "array", "items": {"type": "string"}},
}


def test_config_owned_literals_agree_with_the_output_schema() -> None:
    """The A01 field list and A04 taxonomy live in workflows.yaml but bound the output schema's
    closed shapes; editing one -- including a field's *type*, not just its name -- without the
    other must fail here."""
    steps = _steps()
    fields = _literal(steps["extract"]["input_mapping"]["fields"])
    taxonomy = _literal(steps["detect_issues"]["input_mapping"]["taxonomy"])
    schema = _load_schema("brief_decoder.decode_output_v1")["properties"]
    value_properties = schema["brief"]["properties"]["values"]["properties"]

    field_names = [field["name"] for field in fields]
    assert set(value_properties) == set(field_names)
    assert set(schema["brief"]["properties"]["missing_fields"]["items"]["enum"]) == set(field_names)
    assert set(schema["brief"]["properties"]["confidence"]["properties"]) == set(field_names)
    assert set(schema["issues"]["items"]["properties"]["category"]["enum"]) == set(taxonomy)
    assert _literal(steps["extract"]["input_mapping"]["strict"]) is False

    for field in fields:
        expected_shape = _A01_TYPE_TO_JSON_SCHEMA_TYPE[field["type"]]
        declared_property = value_properties[field["name"]]
        assert declared_property["type"] == expected_shape["type"], field["name"]
        if expected_shape["type"] == "array":
            assert declared_property["items"]["type"] == expected_shape["items"]["type"], (
                field["name"]
            )


def test_schemas_are_closed() -> None:
    def assert_closed(node: Any, where: str) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                assert node.get("additionalProperties") is False, where
            for key, child in node.items():
                assert_closed(child, f"{where}.{key}")
        elif isinstance(node, list):
            for index, child in enumerate(node):
                assert_closed(child, f"{where}[{index}]")

    for schema_ref in ("brief_decoder.decode_input_v1", "brief_decoder.decode_output_v1"):
        assert_closed(_load_schema(schema_ref), schema_ref)


def test_quota_policy_ref_resolves_to_the_declared_lifetime_product_quota() -> None:
    """Mirrors proposal_ai's own quota test (round #1 code review, finding #6): nothing previously
    checked that `product.yaml`'s `quota_policy_ref` actually resolves to a real, sane policy --
    a typo'd ref or e.g. `limit_count: 300`/`dimension: scenario` would have passed every other
    test here."""
    product = _load_yaml("product.yaml")
    quotas = _load_yaml("quotas.yaml")["quota_policies"]

    assert product["quota_policy_ref"] == "brief_decoder.guest_quota_v1"
    (policy,) = [
        policy for policy in quotas if policy["quota_policy_id"] == "brief_decoder.guest_quota_v1"
    ]
    assert policy["unit"] == "scenario_run"
    assert policy["period"] == "lifetime"
    assert policy["dimension"] == "product"
    assert isinstance(policy["limit_count"], int) and policy["limit_count"] > 0


def _assert_same_shape(ours: dict[str, Any], kernel: dict[str, Any], where: str) -> None:
    """A locally-inlined copy of a kernel atom-output schema must keep its properties, required
    set, and per-property types in sync with the kernel original it was copied from, since
    cross-file `$ref` isn't supported. `category`'s `enum` is deliberately narrower than the
    kernel's plain string (our taxonomy is a subset), so it is excluded from the check."""
    assert set(ours.get("properties", {})) == set(kernel.get("properties", {})), where
    assert set(ours.get("required", [])) == set(kernel.get("required", [])), where
    for name, kernel_property in kernel.get("properties", {}).items():
        if name == "category":
            continue  # intentionally narrowed to our own taxonomy subset
        assert ours["properties"][name]["type"] == kernel_property["type"], (where, name)


def test_inlined_kernel_atom_output_copies_stay_in_sync_with_the_kernel_schemas() -> None:
    output_schema = _load_schema("brief_decoder.decode_output_v1")["properties"]

    _assert_same_shape(
        output_schema["issues"]["items"],
        _load_schema("kernel.schemas.issue_detection_output_v1")["properties"]["issues"]["items"],
        "issues.items",
    )
    _assert_same_shape(
        output_schema["questions"]["items"],
        _load_schema("kernel.schemas.generate_questions_output_v1")["properties"]["questions"][
            "items"
        ],
        "questions.items",
    )
    _assert_same_shape(
        output_schema["document"],
        _load_schema("kernel.schemas.generate_document_output_v1"),
        "document",
    )


def test_renderer_contract_agrees_with_workflow_and_scenario() -> None:
    contract = _load_yaml("renderer_contract.yaml")["renderer_contract"]
    (scenario,) = _load_yaml("scenarios.yaml")["scenarios"]
    output_schema = _load_schema(_workflow()["output_schema_ref"])

    assert contract["scenario_id"] == scenario["scenario_id"]
    assert contract["output_schema_ref"] == _workflow()["output_schema_ref"]
    assert contract["next_action"] in scenario["allowed_next_actions"]
    assert [part["part_id"] for part in contract["parts"]] == [
        "brief",
        "issues",
        "clarifying_questions",
        "summary_document",
    ]
    assert {part["field"] for part in contract["parts"]} == set(output_schema["properties"])
    assert contract["canonical_field"] in output_schema["properties"]
    # Code review finding (round #1, finding #10): `canonical_field` (`document`) is an object,
    # not a single string like sibling products' `text` -- pin that a serialization rule exists.
    assert contract["canonical_field_composition"].strip()


@pytest.mark.parametrize(
    "fixture_path", sorted(FIXTURE_ROOT.glob("brief_decoder.*.json")), ids=lambda p: p.stem
)
def test_fixture_satisfies_its_atoms_output_schema(fixture_path: Path) -> None:
    (stem,) = (s for s in FIXTURE_KERNEL_SCHEMAS if fixture_path.name.startswith(s + "."))
    schema = _load_schema(FIXTURE_KERNEL_SCHEMAS[stem])
    jsonschema.validate(_fixture_response(fixture_path.stem), schema)


def test_every_action_config_has_a_happy_and_a_weak_input_fixture() -> None:
    action_config_ids = {
        entry["action_config_id"] for entry in _load_yaml("action_configs.yaml")["action_configs"]
    }
    assert action_config_ids == set(FIXTURE_KERNEL_SCHEMAS)
    for action_config_id in action_config_ids:
        assert (FIXTURE_ROOT / f"{action_config_id}.json").is_file()
        assert (FIXTURE_ROOT / f"{action_config_id}.weak_input.json").is_file()


def test_prompt_and_schema_manifests_point_at_existing_files() -> None:
    for entry in _load_yaml("prompts.yaml")["prompts"]:
        assert (PRODUCT_DIR / entry["template_path"]).is_file(), entry["prompt_ref"]
    for entry in _load_yaml("schemas.yaml")["schemas"]:
        assert (PRODUCT_DIR / entry["file_path"]).is_file(), entry["schema_ref"]
