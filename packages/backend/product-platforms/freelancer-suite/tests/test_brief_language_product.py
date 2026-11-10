"""ANY-761 language contract, canonical fixture shape and structured semantic invariants."""

import json

import jsonschema
import pytest
import yaml
from anytoolai_freelancer_suite.bundle import FreelancerSuiteBundle

from tests.support.brief_language import CANONICAL, CASES

PRODUCTS = {path.name: path for path in FreelancerSuiteBundle().config_roots()}
SOURCES = {
    "brief_decoder": {
        "extract_brief": "source_text",
        "detect_issues": "source_text",
        "generate_questions": "context",
        "generate_summary": "data.source_brief",
    },
    "acceptance_builder": {
        "extract": "source_text",
        "compare": "reference_text",
        "draft_document": "data.source_brief",
        "check_document": "data.source_brief",
    },
}


def schema_for(case, direction):
    product, scenario = case["scenario_id"].split(".")
    name = scenario.removesuffix("_v1")
    path = PRODUCTS[product] / "schemas" / f"{name}_{direction}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_same_language_policy_reaches_every_product_prompt_and_document_mapping():
    policies = set()
    for product, prompts in SOURCES.items():
        root = PRODUCTS[product]
        for prompt, source in prompts.items():
            text = (root / "prompts" / f"{prompt}.v1.md").read_text(encoding="utf-8")
            policy = text.split("## Output language\n\n")[1].split("\n\n", 1)[0]
            assert f"`{source}`" in policy
            policies.add(policy.replace(f"`{source}`", "`SOURCE`"))
        workflows = yaml.safe_load((root / "workflows.yaml").read_text(encoding="utf-8"))
        for workflow in workflows["workflows"]:
            step = workflow["steps"][-1]
            assert step["input_mapping"]["data.source_brief"] == "scenario.input.brief_text"
    assert len(policies) == 1


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_multilingual_inputs_satisfy_the_existing_public_contract(case):
    jsonschema.validate(case["input"], schema_for(case, "input"))


@pytest.mark.parametrize(
    "case", [c for c in CASES if c["id"] in CANONICAL], ids=lambda case: case["id"]
)
def test_full_canonical_fixture_and_semantic_invariants(case):
    output = CANONICAL[case["id"]]
    jsonschema.validate(output, schema_for(case, "output"))
    extracted = output.get("brief", output.get("extracted"))
    assert not set(extracted["values"]) & set(extracted["missing_fields"])
    if "brief" in output:
        assert output["brief_text"] == case["input"]["brief_text"]
        for question in output["questions"]:
            issue = output["issues"][question["source_issue_index"]]
            assert question["category"] == issue["category"]
        if case["family"] == "basic":
            assert set(extracted["missing_fields"]) == {"deadline", "budget"}
            assert "6–8" in json.dumps(output, ensure_ascii=False)
    else:
        sections = {section["id"]: section["content"] for section in output["document"]["sections"]}
        missing = {
            "ru": "Не указано в брифе.",
            "en": "Not specified in the brief.",
            "es": "No se especifica en el encargo.",
        }[case["expected_language"]]
        for name in ("acceptance_criteria", "assumptions", "deliverables"):
            content = sections[name.replace("_", "-")]
            if name in extracted["values"]:
                assert content.splitlines() == [f"- {item}" for item in extracted["values"][name]]
            else:
                assert content == missing
        if case["family"] == "basic":
            assert "500 EUR" in sections["acceptance-criteria"]
            assert '"Ready to ship"' in sections["acceptance-criteria"]
            assert "Acme" in sections["deliverables"]
    if "comparison" in output:
        comparison = output["comparison"]
        statuses = {delta["status"] for delta in comparison["deltas"]}
        expected = (
            "does_not_meet"
            if "mismatch" in statuses
            else "partially_meets"
            if "partial" in statuses
            else "meets_expectations"
        )
        assert comparison["verdict"] == expected
        assert output["document"]["summary"]
