"""ANY-231 full-check-covered deeper evidence for the task_finder product: config-graph shape,
criteria agreement across the workflow/schema/fixtures, renderer-contract agreement, mapping-path
safety, and the "product code contains no PydanticAI/LiteLLM/provider SDK/model-string usage"
acceptance criterion.

Reads raw YAML/JSON instead of ConfigLoader -- ATAI007 forbids product-platforms code, tests
included, from importing anytoolai_platform_core (same reason as
test_acceptance_builder_product.py).
Config-load through the real composition boundary and the end-to-end runs live in
apps/platform-api/tests/test_task_finder_bundle.py (quick-check).
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
    root for root in FreelancerSuiteBundle().config_roots() if root.name == "task_finder"
)

FIT = "task_finder.fit_v1"
OUTPUT_SCHEMA_REF = "task_finder.fit_output_v1"
CRITERION_IDS = ["skills_fit", "experience_fit", "scope_fit", "constraints_fit"]
CATEGORIES = ["strong_fit", "partial_fit", "weak_fit"]
WEAK_SCORE_CEILING = 50
SCORE_TOLERANCE = 0.5  # the A02 cross-validator's tolerance
# fixture stem -> kernel schema its response_json must satisfy (the atom's own output schema)
FIXTURE_KERNEL_SCHEMAS = {
    "task_finder.compare_v1": "kernel.schemas.compare_classify_output_v1",
    "task_finder.score_v1": "kernel.schemas.score_match_output_v1",
}


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


def _load_schema(schema_ref: str) -> dict[str, Any]:
    manifest_dir = KERNEL_DIR if schema_ref.startswith("kernel.") else PRODUCT_DIR
    manifest = yaml.safe_load((manifest_dir / "schemas.yaml").read_text(encoding="utf-8"))
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

    assert [
        action_configs[step["action_config_id"]]["action_type"] for step in _workflow()["steps"]
    ] == [
        "text.compare_and_classify",
        "text.score_match_by_rubric",
    ]
    # A policy ref is the only provider knob a product config may carry -- never a model string.
    for entry in action_configs.values():
        assert set(entry) == {
            "action_config_id",
            "action_type",
            "prompt_ref",
            "provider_policy_ref",
        }
        assert entry["provider_policy_ref"] == "default_fake_provider_v1"


def test_product_has_exactly_one_one_run_scenario() -> None:
    """One workflow run (atom-ready-product-inventory.md: "Workflow runs: 1"), so no "explicit
    user-selected string" second-run input exists to be indexed out of an array. A01 and A09 are
    not steps: A09 needs `signals` objects that no step produces."""
    assert _load_yaml("product.yaml")["scenarios"] == [FIT]
    (scenario,) = _load_yaml("scenarios.yaml")["scenarios"]
    assert scenario["scenario_id"] == FIT
    assert scenario["workflow_id"] == _workflow()["workflow_id"] == FIT
    assert scenario["allowed_next_actions"] == ["copy_result"]
    assert list(_steps()) == ["compare", "score"]


def test_no_mapping_path_uses_brackets_or_numeric_segments() -> None:
    """Bracket indexing is rejected by config validation, but a numeric dotted segment passes it
    and only fails at runtime -- pin both here."""
    paths: list[str] = []
    for step in _workflow()["steps"]:
        for mapping in (step.get("input_mapping", {}), step.get("output_mapping", {})):
            for target, source in mapping.items():
                paths.append(target)
                if not source.startswith("literal:"):
                    paths.append(source.removeprefix("?"))
        assert "when" not in step

    assert paths
    for path in paths:
        assert "[" not in path and "]" not in path, path
        assert not any(segment.isdigit() for segment in path.split(".")), path


def test_steps_read_scenario_input_directly_and_write_the_output_keys() -> None:
    steps = _steps()
    schema = _load_schema(OUTPUT_SCHEMA_REF)

    assert (
        steps["compare"]["input_mapping"]["subject_text"] == "scenario.input.freelancer_positioning"
    )
    assert steps["compare"]["input_mapping"]["reference_text"] == "scenario.input.task_text"
    assert steps["score"]["input_mapping"]["text_a"] == "scenario.input.task_text"
    assert steps["score"]["input_mapping"]["text_b"] == "scenario.input.freelancer_positioning"
    written = {
        target.removeprefix("context.workflow_output.")
        for step in steps.values()
        for target in step["output_mapping"]
    }
    assert written == set(schema["properties"]) == set(schema["required"])
    # The echo keeps a later Task Finder -> ProposalAI handoff possible without a schema bump.
    assert (
        steps["compare"]["output_mapping"]["context.workflow_output.task_text"]
        == "scenario.input.task_text"
    )
    assert (
        steps["compare"]["output_mapping"]["context.workflow_output.freelancer_positioning"]
        == "scenario.input.freelancer_positioning"
    )


def test_criteria_agree_across_both_workflow_literals_the_schema_and_every_fixture() -> None:
    """Both atoms judge the same criteria; the comparison and score halves of the output schema
    pin the same ids in the same order, and so does every fixture (A11 deltas, A02 scores)."""
    steps = _steps()
    criteria = _literal(steps["compare"]["input_mapping"]["criteria"])
    rubric = _literal(steps["score"]["input_mapping"]["rubric"])

    assert criteria == rubric
    assert [c["id"] for c in criteria] == CRITERION_IDS
    assert len({c["id"] for c in criteria}) == len(criteria)
    assert all(c["weight"] > 0 and c["description"].strip() for c in criteria)  # A02 needs weights
    assert _literal(steps["compare"]["input_mapping"]["categories"]) == CATEGORIES

    output = _load_schema(OUTPUT_SCHEMA_REF)
    assert output["properties"]["comparison"]["properties"]["verdict"]["enum"] == CATEGORIES
    for def_name, holder, key in (
        ("delta", "comparison", "deltas"),
        ("criterion_score", "match", "criterion_scores"),
    ):
        array = output["properties"][holder]["properties"][key]
        assert array["items"] == {"$ref": f"#/$defs/{def_name}"}
        assert output["$defs"][def_name]["properties"]["criterion_id"] == {"enum": CRITERION_IDS}
        # one `contains` per id, with exactly four items: each id appears exactly once, any order
        assert (array["minItems"], array["maxItems"]) == (4, 4)
        assert [c["contains"]["properties"]["criterion_id"] for c in array["allOf"]] == [
            {"const": i} for i in CRITERION_IDS
        ]

    for suffix in ("", ".weak_input"):
        compare = _fixture_response("task_finder.compare_v1" + suffix)
        score = _fixture_response("task_finder.score_v1" + suffix)
        assert [d["criterion_id"] for d in compare["deltas"]] == CRITERION_IDS
        assert [s["criterion_id"] for s in score["criterion_scores"]] == CRITERION_IDS
        assert compare["verdict"] in CATEGORIES


@pytest.mark.parametrize("suffix", ["", ".weak_input"])
def test_fixture_verdict_follows_statuses_and_score_is_the_weighted_average(suffix: str) -> None:
    """The kernel cross-validators enforce the score arithmetic (tolerance 0.5) and category
    membership; keep the fixtures well inside both."""
    compare = _fixture_response("task_finder.compare_v1" + suffix)
    score = _fixture_response("task_finder.score_v1" + suffix)
    statuses = {d["status"] for d in compare["deltas"]}
    expected = (
        "weak_fit"
        if "mismatch" in statuses
        else "partial_fit"
        if "partial" in statuses
        else "strong_fit"
    )
    assert compare["verdict"] == expected

    weights = {c["id"]: c["weight"] for c in _literal(_steps()["score"]["input_mapping"]["rubric"])}
    weighted = sum(weights[s["criterion_id"]] * s["score"] for s in score["criterion_scores"])
    assert abs(score["score"] - weighted / sum(weights.values())) <= SCORE_TOLERANCE


def test_weak_input_fixtures_are_a_valid_low_result_not_an_error() -> None:
    assert _fixture_response("task_finder.compare_v1.weak_input")["verdict"] == "weak_fit"
    assert _fixture_response("task_finder.score_v1.weak_input")["score"] < WEAK_SCORE_CEILING


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


def test_input_schema_matches_proposal_ai_task_and_profile_fields() -> None:
    """Same names and limits as ProposalAI's input, so a later handoff maps fields one to one and
    both products can share a client-side validator."""
    ours = _load_schema("task_finder.fit_input_v1")["properties"]
    proposal_dir = next(
        r for r in FreelancerSuiteBundle().config_roots() if r.name == "proposal_ai"
    )
    theirs = json.loads(
        (proposal_dir / "schemas" / "generate_input.schema.json").read_text(encoding="utf-8")
    )["properties"]

    for field in ("task_text", "freelancer_positioning"):
        assert ours[field] == theirs[field]


def test_quota_policy_ref_resolves_to_the_declared_lifetime_product_quota() -> None:
    product = _load_yaml("product.yaml")
    quotas = _load_yaml("quotas.yaml")["quota_policies"]

    assert product["quota_policy_ref"] == "task_finder.guest_quota_v1"
    (policy,) = [p for p in quotas if p["quota_policy_id"] == "task_finder.guest_quota_v1"]
    assert policy["unit"] == "scenario_run"
    assert policy["period"] == "lifetime"
    assert policy["dimension"] == "product"
    assert isinstance(policy["limit_count"], int) and policy["limit_count"] > 0


def test_inlined_kernel_atom_output_copies_stay_in_sync_with_the_kernel_schemas() -> None:
    """Cross-file `$ref` is unsupported, so the product schema inlines the atom output shapes;
    properties, required sets and per-property types must follow the kernel originals."""
    output = _load_schema(OUTPUT_SCHEMA_REF)
    for ours, kernel_ref in (
        (output["properties"]["comparison"], "kernel.schemas.compare_classify_output_v1"),
        (output["properties"]["match"], "kernel.schemas.score_match_output_v1"),
    ):
        kernel = _load_schema(kernel_ref)
        assert set(ours["properties"]) == set(kernel["properties"]), kernel_ref
        assert set(ours["required"]) == set(kernel["required"]), kernel_ref
        for name, kernel_property in kernel["properties"].items():
            if "type" in ours["properties"][name]:
                assert ours["properties"][name]["type"] == kernel_property["type"], (
                    kernel_ref,
                    name,
                )

    kernel_compare = _load_schema("kernel.schemas.compare_classify_output_v1")
    kernel_score = _load_schema("kernel.schemas.score_match_output_v1")
    for ours, kernel in (
        (output["$defs"]["delta"], kernel_compare["properties"]["deltas"]["items"]),
        (
            output["$defs"]["criterion_score"],
            kernel_score["properties"]["criterion_scores"]["items"],
        ),
    ):
        assert set(ours["properties"]) == set(kernel["properties"])
        assert ours["required"] == kernel["required"]
    assert (
        output["$defs"]["delta"]["properties"]["status"]["enum"]
        == (kernel_compare["properties"]["deltas"]["items"]["properties"]["status"]["enum"])
    )

    # Limits the product schema repeats must equal the kernel's: a stricter copy rejects, after
    # both paid calls, an answer the atoms accepted; a looser one is dead weight.
    def limits(node: dict[str, Any]) -> dict[str, Any]:
        keys = ("minLength", "maxLength", "minimum", "maximum", "minItems")
        return {k: node[k] for k in keys if k in node}

    comparison, match = output["properties"]["comparison"], output["properties"]["match"]
    for name in ("confidence", "rationale"):
        assert limits(comparison["properties"][name]) == limits(kernel_compare["properties"][name])
    for name in ("score", "overall_rationale"):
        assert limits(match["properties"][name]) == limits(kernel_score["properties"][name])
    for name in ("strengths", "gaps"):
        assert limits(match["properties"][name]["items"]) == limits(
            kernel_score["properties"][name]["items"]
        )
    for name in ("score", "rationale"):
        assert limits(output["$defs"]["criterion_score"]["properties"][name]) == limits(
            kernel_score["properties"]["criterion_scores"]["items"]["properties"][name]
        )
    assert limits(output["$defs"]["delta"]["properties"]["evidence"]) == limits(
        kernel_compare["properties"]["deltas"]["items"]["properties"]["evidence"]
    )


def _resolves(schema: dict[str, Any], path: str) -> bool:
    """Whether dotted `path` names a property chain in the closed object schema `schema`."""
    node = schema
    for segment in path.split("."):
        if segment not in node.get("properties", {}):
            return False
        node = node["properties"][segment]
    return True


def test_renderer_contract_agrees_with_workflow_and_scenario() -> None:
    contract = _load_yaml("renderer_contract.yaml")["renderer_contract"]
    (entry,) = contract["scenarios"]
    parts = {part["part_id"]: part for part in contract["parts"]}
    schema = _load_schema(OUTPUT_SCHEMA_REF)

    assert entry["scenario_id"] == FIT
    assert entry["output_schema_ref"] == _workflow()["output_schema_ref"] == OUTPUT_SCHEMA_REF
    assert set(entry["parts"]) == set(parts)
    assert all(_resolves(schema, parts[p]["field"]) for p in entry["parts"])
    # Every top-level output property is either rendered or explicitly excluded (the echoed inputs).
    rendered = {parts[p]["field"].split(".")[0] for p in entry["parts"]}
    assert rendered | set(contract["excluded_fields"]) == set(schema["properties"])
    assert rendered.isdisjoint(contract["excluded_fields"])
    # Every property of the two atom outputs is shown by some part.
    fields = {parts[p]["field"] for p in entry["parts"]}
    assert {"comparison.verdict", "comparison.deltas", "comparison.rationale"} <= fields
    assert {
        "match.score",
        "match.criterion_scores",
        "match.strengths",
        "match.gaps",
        "match.overall_rationale",
    } <= fields
    assert (
        contract["next_action"]
        in _load_yaml("scenarios.yaml")["scenarios"][0]["allowed_next_actions"]
    )
    # Score and verdict come from two independent calls; the contract must say they may disagree.
    assert "independent" in " ".join(parts["fit_score"]["description"].split())
    assert "never joins" in " ".join(parts["criteria_comparison"]["description"].split())
    assert "not call it a check of the task" in " ".join(parts["verdict"]["description"].split())


def test_copy_text_is_derived_from_structured_fields() -> None:
    contract = _load_yaml("renderer_contract.yaml")["renderer_contract"]
    schema = _load_schema(OUTPUT_SCHEMA_REF)
    copy_text = contract["copy_text"]

    assert copy_text["authority"] == "structured_fields_only"
    assert [b["block_id"] for b in copy_text["blocks"]] == [
        "fit",
        "criteria",
        "criterion_scores",
        "strengths",
        "gaps",
    ]
    for block in copy_text["blocks"]:
        for path in [block["source"], *block.get("also_uses", [])]:
            assert _resolves(schema, path), (block["block_id"], path)
    # `strengths`/`gaps` may legitimately be empty arrays, so they carry a fallback text.
    blocks = {b["block_id"]: b for b in copy_text["blocks"]}
    assert blocks["strengths"]["when_empty"] == blocks["gaps"]["when_empty"] == "Not specified."
    assert (
        schema["properties"]["match"]["properties"]["strengths"].get("minItems", 0) == 0
        and schema["properties"]["match"]["properties"]["gaps"].get("minItems", 0) == 0
    )


@pytest.mark.parametrize(
    "fixture_path", sorted(FIXTURE_ROOT.glob("task_finder.*.json")), ids=lambda p: p.stem
)
def test_fixture_satisfies_its_atoms_output_schema(fixture_path: Path) -> None:
    (stem,) = (s for s in FIXTURE_KERNEL_SCHEMAS if fixture_path.name.startswith(s + "."))
    jsonschema.validate(
        _fixture_response(fixture_path.stem), _load_schema(FIXTURE_KERNEL_SCHEMAS[stem])
    )


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
