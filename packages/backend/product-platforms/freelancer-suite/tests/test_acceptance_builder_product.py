"""ANY-228 full-check-covered deeper evidence for the acceptance_builder product: config-graph
shape, renderer-contract agreement, fixture/schema agreement, mapping-path safety, and the
"product code contains no PydanticAI/LiteLLM/provider SDK/model-string usage" acceptance
criterion.

Reads raw YAML/JSON instead of ConfigLoader -- ATAI007 forbids product-platforms code, tests
included, from importing anytoolai_platform_core (same reason as test_brief_decoder_product.py).
Config-load through the real composition boundary and the end-to-end runs live in
apps/platform-api/tests/test_acceptance_builder_bundle.py (quick-check).
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
    root for root in FreelancerSuiteBundle().config_roots() if root.name == "acceptance_builder"
)
BRIEF_DECODER_DIR = PRODUCT_DIR.parent / "brief_decoder"

DRAFT = "acceptance_builder.draft_v1"
CHECK = "acceptance_builder.check_v1"
FROM_BRIEF = "acceptance_builder.draft_from_brief_v1"
STEP_ACTION_TYPES = {
    DRAFT: ("text.extract_structured_fields", "document.generate_from_template"),
    CHECK: (
        "text.extract_structured_fields",
        "text.compare_and_classify",
        "document.generate_from_template",
    ),
    FROM_BRIEF: ("document.generate_from_template",),
}
OUTPUT_SCHEMA_REFS = {
    DRAFT: "acceptance_builder.draft_output_v1",
    CHECK: "acceptance_builder.check_output_v1",
    FROM_BRIEF: "acceptance_builder.draft_from_brief_output_v1",
}
# fixture stem -> kernel schema its response_json must satisfy (the atom's own output schema)
FIXTURE_KERNEL_SCHEMAS = {
    "acceptance_builder.extract_v1": "kernel.schemas.extract_output_v1",
    "acceptance_builder.compare_v1": "kernel.schemas.compare_classify_output_v1",
    "acceptance_builder.draft_document_v1": "kernel.schemas.generate_document_output_v1",
    "acceptance_builder.check_document_v1": "kernel.schemas.generate_document_output_v1",
    "acceptance_builder.draft_from_brief_document_v1": "kernel.schemas.generate_document_output_v1",
}
EXTRACTED_FIELDS = ["acceptance_criteria", "assumptions", "deliverables"]


def _load_test_support_module() -> Any:
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


def _load_schema(schema_ref: str, *, product_dir: Path = PRODUCT_DIR) -> dict[str, Any]:
    if schema_ref.startswith("kernel."):
        manifest_dir = KERNEL_DIR
    else:
        manifest_dir = product_dir
    manifest = yaml.safe_load((manifest_dir / "schemas.yaml").read_text(encoding="utf-8"))
    (entry,) = (item for item in manifest["schemas"] if item["schema_ref"] == schema_ref)
    return json.loads((manifest_dir / entry["file_path"]).read_text(encoding="utf-8"))


def _workflows() -> dict[str, dict[str, Any]]:
    return {w["workflow_id"]: w for w in _load_yaml("workflows.yaml")["workflows"]}


def _steps(workflow_id: str) -> dict[str, dict[str, Any]]:
    return {step["step_id"]: step for step in _workflows()[workflow_id]["steps"]}


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


def test_workflows_use_only_generic_atom_action_types_with_backend_resolved_policies() -> None:
    action_configs = {
        entry["action_config_id"]: entry
        for entry in _load_yaml("action_configs.yaml")["action_configs"]
    }

    for workflow_id, workflow in _workflows().items():
        assert (
            tuple(action_configs[step["action_config_id"]]["action_type"] for step in workflow["steps"])
            == STEP_ACTION_TYPES[workflow_id]
        )
    # A policy ref is the only provider knob a product config may carry -- never a model string.
    assert {entry["provider_policy_ref"] for entry in action_configs.values()} == {
        "default_fake_provider_v1"
    }
    for entry in action_configs.values():
        assert set(entry) == {"action_config_id", "action_type", "prompt_ref", "provider_policy_ref"}


def test_product_has_exactly_the_three_one_run_scenarios() -> None:
    """Each scenario is one workflow run (atom-ready-product-inventory.md: "Workflow runs: 1"),
    so no "explicit user-selected string" second-run input exists to be indexed out of an array."""
    assert _load_yaml("product.yaml")["scenarios"] == [DRAFT, CHECK, FROM_BRIEF]
    scenarios = _load_yaml("scenarios.yaml")["scenarios"]
    assert [s["scenario_id"] for s in scenarios] == [DRAFT, CHECK, FROM_BRIEF]
    assert set(_workflows()) == {DRAFT, CHECK, FROM_BRIEF}
    for scenario in scenarios:
        assert scenario["workflow_id"] == scenario["scenario_id"]
        assert scenario["allowed_next_actions"] == ["copy_result"]


def test_no_mapping_path_uses_brackets_or_numeric_segments() -> None:
    """Bracket indexing is rejected by config validation, but a numeric dotted segment passes it
    and only fails at runtime -- pin both here."""
    paths: list[str] = []
    for workflow in _workflows().values():
        for step in workflow["steps"]:
            for mapping in (step.get("input_mapping", {}), step.get("output_mapping", {})):
                for target, source in mapping.items():
                    paths.append(target)
                    if not source.startswith("literal:"):
                        paths.append(source.removeprefix("?"))
            assert "when" not in step  # branching lives in the scenario split, not in `when`

    assert paths
    for path in paths:
        assert "[" not in path and "]" not in path, path
        assert not any(segment.isdigit() for segment in path.split(".")), path


@pytest.mark.parametrize("workflow_id", [DRAFT, CHECK, FROM_BRIEF])
def test_every_step_writes_its_own_key_of_the_composed_workflow_output(workflow_id: str) -> None:
    targets = [t for step in _workflows()[workflow_id]["steps"] for t in step["output_mapping"]]
    schema = _load_schema(OUTPUT_SCHEMA_REFS[workflow_id])

    assert all(t.startswith("context.workflow_output.") for t in targets)  # never the whole output
    keys = {t.removeprefix("context.workflow_output.") for t in targets}
    assert len(keys) == len(targets)
    assert keys == set(schema["properties"]) == set(schema["required"])


def test_config_owned_literals_agree_with_the_output_schemas() -> None:
    """The A01 field list and A11 categories/criteria live in workflows.yaml but bound the output
    schemas' closed shapes; editing one without the other must fail here."""
    for workflow_id in (DRAFT, CHECK):
        extract = _steps(workflow_id)["extract"]["input_mapping"]
        fields = _literal(extract["fields"])
        assert _literal(extract["strict"]) is False
        assert [f["name"] for f in fields] == EXTRACTED_FIELDS
        assert {f["type"] for f in fields} == {"array_of_strings"}
        extracted = _load_schema(OUTPUT_SCHEMA_REFS[workflow_id])["properties"]["extracted"][
            "properties"
        ]
        assert set(extracted["values"]["properties"]) == set(EXTRACTED_FIELDS)
        assert set(extracted["missing_fields"]["items"]["enum"]) == set(EXTRACTED_FIELDS)
        assert set(extracted["confidence"]["properties"]) == set(EXTRACTED_FIELDS)
        for name in EXTRACTED_FIELDS:
            assert extracted["values"]["properties"][name]["type"] == "array"

    compare = _steps(CHECK)["compare"]["input_mapping"]
    categories = _literal(compare["categories"])
    criteria = _literal(compare["criteria"])
    criterion_ids = [c["id"] for c in criteria]
    comparison = _load_schema(OUTPUT_SCHEMA_REFS[CHECK])["properties"]["comparison"]

    assert set(comparison["properties"]["verdict"]["enum"]) == set(categories)
    assert len(set(criterion_ids)) == len(criterion_ids)
    assert all(c["weight"] > 0 and c["description"].strip() for c in criteria)
    # deltas is fixed to one entry per criterion, in workflow order, each pinned to its id.
    assert comparison["properties"]["deltas"]["minItems"] == len(criteria)
    assert comparison["properties"]["deltas"]["maxItems"] == len(criteria)
    defs = _load_schema(OUTPUT_SCHEMA_REFS[CHECK])["$defs"]
    prefix = comparison["properties"]["deltas"]["prefixItems"]
    assert [defs[ref["$ref"].rsplit("/", 1)[1]]["properties"]["criterion_id"]["const"] for ref in prefix] == (
        criterion_ids
    )
    assert comparison["properties"]["rationale"]["maxLength"] == 500  # A11's own cap


@pytest.mark.parametrize("suffix", ["", ".weak_input"])
def test_fixture_deltas_cover_the_workflows_criterion_ids_in_order(suffix: str) -> None:
    criterion_ids = [c["id"] for c in _literal(_steps(CHECK)["compare"]["input_mapping"]["criteria"])]
    deltas = _fixture_response("acceptance_builder.compare_v1" + suffix)["deltas"]

    assert [d["criterion_id"] for d in deltas] == criterion_ids


@pytest.mark.parametrize("state", ["present_and_missing", "absent_from_both", "confidence_only"])
def test_a01_field_invariants_hold_for_every_configured_field(state: str) -> None:
    """The canonical schema must reject what A01's cross-validator rejects, for every field in the
    workflow's own A01 field list."""
    schema = _load_schema(OUTPUT_SCHEMA_REFS[DRAFT])
    validator = jsonschema.validators.validator_for(schema)(schema)
    complete = _fixture_response("acceptance_builder.extract_v1")
    document = _fixture_response("acceptance_builder.draft_document_v1")

    def output(extracted: dict[str, Any]) -> dict[str, Any]:
        return {"extracted": extracted, "document": document}

    assert validator.is_valid(output(complete))  # control: every field present, none missing
    for name in EXTRACTED_FIELDS:
        extracted = json.loads(json.dumps(complete))
        if state == "present_and_missing":
            extracted["missing_fields"] = [name]
        elif state == "absent_from_both":
            del extracted["values"][name]
            extracted["confidence"].pop(name, None)
        else:
            del extracted["values"][name]
            extracted["missing_fields"] = [name]
        assert not validator.is_valid(output(extracted)), (state, name)


_GAPS_KEYWORD = {
    "acceptance_criteria": "acceptance criteria",
    "assumptions": "assumptions",
    "deliverables": "deliverables",
}
_DOCUMENT_FIXTURES = [  # (A10 stem, A01 stem)
    ("acceptance_builder.draft_document_v1" + s, "acceptance_builder.extract_v1" + s)
    for s in ("", ".weak_input")
] + [
    ("acceptance_builder.check_document_v1" + s, "acceptance_builder.extract_v1" + s)
    for s in ("", ".weak_input")
]


@pytest.mark.parametrize(("document_stem", "extract_stem"), _DOCUMENT_FIXTURES)
def test_document_fixtures_obey_the_a10_prompts(document_stem: str, extract_stem: str) -> None:
    """Both A10 prompts: list sections carry every extracted item verbatim (or "Not specified in
    the brief."), and `open-gaps` names every entry of `missing_fields`. Checked against the A01
    fixture that feeds the same run, so a fixture cannot narrate items the run did not extract."""
    extracted = _fixture_response(extract_stem)
    document = _fixture_response(document_stem)
    sections = {s["id"]: s["content"] for s in document["sections"]}

    assert set(_GAPS_KEYWORD) == set(EXTRACTED_FIELDS)
    for name in EXTRACTED_FIELDS:
        content = sections[name.replace("_", "-")]
        if name in extracted["values"]:
            assert content.splitlines() == [f"- {item}" for item in extracted["values"][name]], name
        else:
            assert content == "Not specified in the brief.", name
    for name in extracted["missing_fields"]:
        assert _GAPS_KEYWORD[name] in sections["open-gaps"].lower(), name


@pytest.mark.parametrize("suffix", ["", ".weak_input"])
def test_check_document_verdict_section_agrees_with_the_comparison(suffix: str) -> None:
    comparison = _fixture_response("acceptance_builder.compare_v1" + suffix)
    document = _fixture_response("acceptance_builder.check_document_v1" + suffix)
    verdict_section = document["sections"][0]
    text = verdict_section["content"].lower()

    assert verdict_section["id"] == "verdict"
    assert comparison["verdict"].replace("_", " ") in text
    for delta in comparison["deltas"]:
        assert delta["criterion_id"].replace("_", " ") in text, delta["criterion_id"]
        assert delta["status"] in text, delta["criterion_id"]
    # The verdict is on the general criteria, never presented as a per-extracted-criterion check.
    assert "not item by item" in text


_BRIEF_GAPS_KEYWORD = {
    "project_goal": "goal",
    "deliverables": "deliverables",
    "deadline": "deadline",
    "budget": "budget",
    "target_audience": "audience",
    "constraints": "constraint",
}
# (draft_from_brief fixture suffix, the Brief Decoder A01 fixture whose `brief` feeds that run)
_FROM_BRIEF_RUNS = [("", ""), (".weak_input", ".weak_input")]


@pytest.mark.parametrize(("suffix", "brief_suffix"), _FROM_BRIEF_RUNS)
def test_draft_from_brief_fixtures_are_grounded_in_the_brief_decoder_brief(
    suffix: str, brief_suffix: str
) -> None:
    """draft_from_brief_document.v1.md: criteria restate only deliverables/constraints/deadline/
    budget entries, `deliverables` is verbatim, `open-gaps` names every missing field. Checked
    against the real Brief Decoder brief fixture the same run would receive."""
    brief = _fixture_response("brief_decoder.extract_brief_v1" + brief_suffix)
    values = brief["values"]
    sections = {
        s["id"]: s["content"]
        for s in _fixture_response("acceptance_builder.draft_from_brief_document_v1" + suffix)[
            "sections"
        ]
    }

    sources = (
        len(values.get("deliverables", []))
        + len(values.get("constraints", []))
        + sum(1 for key in ("deadline", "budget") if key in values)
    )
    criteria = sections["acceptance-criteria"]
    if sources:
        lines = criteria.splitlines()
        assert lines and all(line.startswith("- ") for line in lines)
        assert len(lines) <= sources
    else:
        assert criteria == "Not specified in the brief."
    if "deliverables" in values:
        assert sections["deliverables"].splitlines() == [f"- {d}" for d in values["deliverables"]]
    else:
        assert sections["deliverables"] == "Not specified in the brief."
    for name in brief["missing_fields"]:
        assert _BRIEF_GAPS_KEYWORD[name] in sections["open-gaps"].lower(), name


def test_draft_from_brief_input_is_exactly_brief_decoders_brief_contract() -> None:
    """ANY-26's Brief Decoder -> Acceptance Builder `create draft` handoff maps Brief Decoder's
    always-present `brief` object here. Schema equality proves every valid Brief Decoder `brief`
    is valid input (and nothing else is); Brief Decoder's `document.summary` is a readiness note,
    not a faithful brief, so it is deliberately not the handoff source."""
    target = _load_schema("acceptance_builder.draft_from_brief_input_v1")
    source = _load_schema("brief_decoder.decode_output_v1", product_dir=BRIEF_DECODER_DIR)

    assert target["required"] == ["brief"]
    assert target["additionalProperties"] is False
    assert target["properties"] == {"brief": source["properties"]["brief"]}
    assert "brief" in source["required"]  # always present, so the mapped path always exists


@pytest.mark.parametrize("suffix", ["", ".weak_input", ".no_issues"])
def test_real_brief_decoder_briefs_are_valid_draft_from_brief_input(suffix: str) -> None:
    schema = _load_schema("acceptance_builder.draft_from_brief_input_v1")
    brief = _fixture_response("brief_decoder.extract_brief_v1" + suffix)

    jsonschema.validate({"brief": brief}, schema)


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

    for entry in _load_yaml("schemas.yaml")["schemas"]:
        assert_closed(_load_schema(entry["schema_ref"]), entry["schema_ref"])


def test_quota_policy_ref_resolves_to_the_declared_lifetime_product_quota() -> None:
    product = _load_yaml("product.yaml")
    quotas = _load_yaml("quotas.yaml")["quota_policies"]

    assert product["quota_policy_ref"] == "acceptance_builder.guest_quota_v1"
    (policy,) = [p for p in quotas if p["quota_policy_id"] == "acceptance_builder.guest_quota_v1"]
    assert policy["unit"] == "scenario_run"
    assert policy["period"] == "lifetime"
    assert policy["dimension"] == "product"
    assert isinstance(policy["limit_count"], int) and policy["limit_count"] > 0


def _assert_same_shape(ours: dict[str, Any], kernel: dict[str, Any], where: str) -> None:
    """A locally-inlined copy of a kernel atom-output schema must keep its properties, required
    set, and per-property types in sync with the kernel original, since cross-file `$ref` isn't
    supported. Properties this product deliberately narrows (enum/const) are compared by name
    only."""
    assert set(ours["properties"]) == set(kernel["properties"]), where
    assert set(ours["required"]) == set(kernel["required"]), where
    for name, kernel_property in kernel["properties"].items():
        if "type" in ours["properties"][name]:
            assert ours["properties"][name]["type"] == kernel_property["type"], (where, name)


def test_inlined_kernel_atom_output_copies_stay_in_sync_with_the_kernel_schemas() -> None:
    check = _load_schema(OUTPUT_SCHEMA_REFS[CHECK])
    draft = _load_schema(OUTPUT_SCHEMA_REFS[DRAFT])
    kernel_extract = _load_schema("kernel.schemas.extract_output_v1")
    kernel_compare = _load_schema("kernel.schemas.compare_classify_output_v1")
    kernel_document = _load_schema("kernel.schemas.generate_document_output_v1")

    # The extract copy is identical in both product schemas.
    assert draft["properties"]["extracted"] == check["properties"]["extracted"]
    for output in (draft, check):
        _assert_same_shape(output["properties"]["extracted"], kernel_extract, "extracted")
        _assert_same_shape(output["properties"]["document"], kernel_document, "document")
    from_brief = _load_schema(OUTPUT_SCHEMA_REFS[FROM_BRIEF])
    _assert_same_shape(from_brief["properties"]["document"], kernel_document, "from_brief document")
    comparison = check["properties"]["comparison"]
    _assert_same_shape(comparison, kernel_compare, "comparison")
    _assert_same_shape(
        check["$defs"]["delta_clarity"], kernel_compare["properties"]["deltas"]["items"], "delta"
    )
    assert comparison["properties"]["confidence"] == kernel_compare["properties"]["confidence"]


def test_renderer_contract_agrees_with_workflows_and_scenarios() -> None:
    contract = _load_yaml("renderer_contract.yaml")["renderer_contract"]
    scenarios = {s["scenario_id"]: s for s in _load_yaml("scenarios.yaml")["scenarios"]}
    parts = {part["part_id"]: part for part in contract["parts"]}

    assert {s["scenario_id"] for s in contract["scenarios"]} == set(scenarios)
    for entry in contract["scenarios"]:
        workflow = _workflows()[entry["scenario_id"]]
        assert entry["output_schema_ref"] == workflow["output_schema_ref"]
        output_schema = _load_schema(workflow["output_schema_ref"])
        assert set(entry["parts"]) <= set(parts)
        top_level_fields = {parts[p]["field"].split(".")[0] for p in entry["parts"]}
        assert top_level_fields == set(output_schema["properties"]), entry["scenario_id"]
        assert contract["canonical_field"] in output_schema["properties"]
    assert contract["next_action"] in scenarios[DRAFT]["allowed_next_actions"]
    assert contract["next_action"] in scenarios[CHECK]["allowed_next_actions"]
    assert contract["next_action"] in scenarios[FROM_BRIEF]["allowed_next_actions"]
    assert contract["canonical_field_composition"].strip()
    assert parts["comparison_verdict"]["field"] == "comparison"
    # Only check_v1 has a verdict; the contract must not present it for draft_v1.
    draft_parts = next(s for s in contract["scenarios"] if s["scenario_id"] == DRAFT)["parts"]
    assert "comparison_verdict" not in draft_parts
    from_brief_parts = next(s for s in contract["scenarios"] if s["scenario_id"] == FROM_BRIEF)
    assert from_brief_parts["parts"] == ["copy_document"]
    # The verdict is on general criteria, not the extracted list -- the contract must say so.
    assert "not item by item" in " ".join(parts["comparison_verdict"]["description"].split()).lower()


@pytest.mark.parametrize(
    "fixture_path", sorted(FIXTURE_ROOT.glob("acceptance_builder.*.json")), ids=lambda p: p.stem
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
    prompt_refs = set()
    for entry in _load_yaml("prompts.yaml")["prompts"]:
        assert (PRODUCT_DIR / entry["template_path"]).is_file(), entry["prompt_ref"]
        prompt_refs.add(entry["prompt_ref"])
    for entry in _load_yaml("schemas.yaml")["schemas"]:
        assert (PRODUCT_DIR / entry["file_path"]).is_file(), entry["schema_ref"]
    for entry in _load_yaml("action_configs.yaml")["action_configs"]:
        assert entry["prompt_ref"] in prompt_refs, entry["action_config_id"]
