"""ANY-227 (B02a) product-level evidence for ProposalAI's raw config, kept free of any
`anytoolai_platform_core` import (ATAI007/ATAI008 forbid product-platforms code -- including its
own tests -- from depending on platform-core internals; only the composition boundaries may).
Everything here is plain YAML/JSON parsing over the checked-in product directory and fixtures."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
PRODUCT_DIR = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "anytoolai_freelancer_suite"
    / "products"
    / "proposal_ai"
)
# Shared, kernel-level directory (same one kernel_demo uses) -- see Design decision 5 in the
# exec plan: a product-local fixture directory can't be resolved by build_worker()'s *bare*
# default provider-adapter composition without either violating the "no adapter imports outside
# providers/adapters or providers/gateway" architecture gate or changing Platform Core, and
# ANY-227 forbids the latter outright.
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "provider" / "fake_provider_outputs"


def _load_test_support_module() -> Any:
    # Dynamic-load by explicit path, same pattern this file already used for
    # validate_architecture.py -- code review finding: _load_validate_architecture_module(),
    # FORBIDDEN_PROVIDER_TERMS, and _load_yaml() were each duplicated verbatim in
    # test_client_update_writer_product.py; both now load this one shared module instead.
    path = Path(__file__).resolve().parent / "_test_support.py"
    spec = importlib.util.spec_from_file_location("freelancer_suite_test_support", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_test_support = _load_test_support_module()
FORBIDDEN_PROVIDER_TERMS = _test_support.FORBIDDEN_PROVIDER_TERMS


def _load_yaml(name: str) -> dict:
    return _test_support.load_yaml(PRODUCT_DIR, name)


def _load_prompt(name: str) -> str:
    return (PRODUCT_DIR / name).read_text(encoding="utf-8")


def test_action_type_sequence_is_gap_detection_then_compose_persuasive_text() -> None:
    action_configs = _load_yaml("action_configs.yaml")["action_configs"]
    assert [config["action_type"] for config in action_configs] == [
        "text.detect_issues_by_taxonomy",
        "text.compose_persuasive_text",
    ]

    workflow = _load_yaml("workflows.yaml")["workflows"][0]
    action_config_by_id = {config["action_config_id"]: config for config in action_configs}
    step_action_types = [
        action_config_by_id[step["action_config_id"]]["action_type"]
        for step in workflow["steps"]
    ]
    assert step_action_types == ["text.detect_issues_by_taxonomy", "text.compose_persuasive_text"]


def test_prompt_refs_resolve_to_existing_templates() -> None:
    prompts = {entry["prompt_ref"]: entry for entry in _load_yaml("prompts.yaml")["prompts"]}
    for config in _load_yaml("action_configs.yaml")["action_configs"]:
        entry = prompts[config["prompt_ref"]]
        assert (PRODUCT_DIR / entry["template_path"]).is_file()
    assert prompts["proposal_ai.compose_persuasive_text.v2"]["version"] == 2


def test_product_contains_no_forbidden_provider_sdk_or_model_string_tokens() -> None:
    for path in PRODUCT_DIR.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").lower()
        for term in FORBIDDEN_PROVIDER_TERMS:
            assert term not in text, f"forbidden provider term {term!r} found in {path}"


def test_quota_policy_ref_resolves_to_the_declared_lifetime_product_quota() -> None:
    product = _load_yaml("product.yaml")
    quotas = _load_yaml("quotas.yaml")["quota_policies"]

    assert product["quota_policy_ref"] == "proposal_ai.guest_quota_v1"
    (policy,) = [
        policy for policy in quotas if policy["quota_policy_id"] == "proposal_ai.guest_quota_v1"
    ]
    assert policy["unit"] == "scenario_run"
    assert policy["period"] == "lifetime"
    assert policy["dimension"] == "product"
    assert policy["limit_count"] == 10


def test_renderer_contract_pins_the_copy_ready_text_and_the_informational_gaps() -> None:
    """The renderer contract is cross-checked against workflows.yaml, scenarios.yaml and the
    output schema so it cannot silently drift from the actual output."""
    contract = _load_yaml("renderer_contract.yaml")["renderer_contract"]
    workflow = _load_yaml("workflows.yaml")["workflows"][0]
    scenario = _load_yaml("scenarios.yaml")["scenarios"][0]
    output_schema = json.loads(
        (PRODUCT_DIR / "schemas" / "generate_output.schema.json").read_text(encoding="utf-8")
    )

    assert contract["scenario_id"] == scenario["scenario_id"]
    assert contract["output_schema_ref"] == workflow["output_schema_ref"]
    assert contract["output_schema_ref"] == "proposal_ai.generate_output_v1"
    assert contract["canonical_field"] == "text"
    assert [part["field"] for part in contract["parts"]] == ["text", "gaps"]
    assert {part["field"] for part in contract["parts"]} == set(output_schema["properties"])
    assert contract["next_action"] in scenario["allowed_next_actions"]
    assert set(contract["excluded_fields"]) >= {"angle", "rationale", "model", "provider"}


def test_workflow_input_mapping_uses_only_generic_mapping_dsl_syntax() -> None:
    """No mapping-DSL change: the whole `context` maps in one entry (the DSL rejects a dotted
    `context.*` input target, so gaps travel as `constraints.claims_to_avoid`), tone/language stay
    optional via the existing `?` prefix, and the post-checks are config literals."""
    detect, compose = _load_yaml("workflows.yaml")["workflows"][0]["steps"]

    assert detect["input_mapping"]["source_text"] == "scenario.input.task_text"
    assert detect["input_mapping"]["context"] == "scenario.input.freelancer_positioning"
    assert json.loads(detect["input_mapping"]["taxonomy"].removeprefix("literal:")) == [
        "experience_gap"
    ]
    assert detect["output_mapping"] == {"context.workflow_output.gaps": "steps.detect_gaps.output.issues"}

    mapping = compose["input_mapping"]
    assert mapping["context"] == "scenario.input"
    assert mapping["constraints.tone"] == "?scenario.input.tone"
    assert mapping["constraints.language"] == "?scenario.input.language"
    assert mapping["constraints.claims_to_avoid"] == "steps.detect_gaps.output.issues"
    assert mapping["constraints.format"] == 'literal:"plain_text"'
    assert mapping["constraints.length"] == "literal:1800"
    assert mapping["constraints.plain_text_lists"] == 'literal:"forbidden"'
    assert mapping["constraints.numbers_must_appear_in_context"] == "literal:true"
    assert mapping["objective"].startswith("literal:")
    assert compose["output_mapping"] == {
        "context.workflow_output.text": "steps.compose_persuasive_text.output.text"
    }


def _forbidden_patterns() -> list[str]:
    compose = _load_yaml("workflows.yaml")["workflows"][0]["steps"][1]
    raw = compose["input_mapping"]["constraints.forbidden_patterns"]
    return json.loads(raw.removeprefix("literal:"))


@pytest.mark.parametrize(
    "bad_text",
    [
        "Hello [Client Name], I can help.",
        "Hello {{name}}, I can help.",
        "Best regards, Your Name",
        "Based on the information I'm working from here, I can help.",
        "I can't truthfully claim HubSpot experience.",
    ],
)
def test_forbidden_patterns_catch_placeholders_and_meta_phrases(bad_text: str) -> None:
    assert any(re.search(pattern, bad_text, re.IGNORECASE) for pattern in _forbidden_patterns())


@pytest.mark.parametrize(
    "fine_text",
    [
        "As an AI automation engineer I build Telegram bots.",
        "Based on the information in your brief, I would start with the API.",
        "I build AI agents and describe the information flow first.",
        "I will follow your namespace conventions.",
    ],
)
def test_ordinary_phrases_are_not_meta_commentary(fine_text: str) -> None:
    assert not any(re.search(pattern, fine_text, re.IGNORECASE) for pattern in _forbidden_patterns())


@pytest.mark.parametrize(
    "bad_text",
    [
        "As an AI language model, I cannot promise this.",
        "As an AI, I can only use what is written here.",
        "Based on the information I have, I fit.",
        "Based on the information I\u2019m working from here, I fit.",
    ],
)
def test_first_person_ai_meta_commentary_is_caught(bad_text: str) -> None:
    assert any(re.search(pattern, bad_text, re.IGNORECASE) for pattern in _forbidden_patterns())


def test_a_long_dash_is_a_style_rule_not_a_validation_failure() -> None:
    """A run failed twice in a row over an em dash in a Russian text; the prompt keeps the rule,
    the eval script counts it, the validator no longer rejects it."""
    assert not any(re.search(pattern, "Fast \u2014 and clean. Fast \u2013 too.") for pattern in _forbidden_patterns())


@pytest.mark.parametrize(
    "fixture_name",
    ["proposal_ai.compose_persuasive_text_v1", "proposal_ai.compose_persuasive_text_v1.weak_input"],
)
def test_compose_fixtures_pass_the_workflow_forbidden_patterns(fixture_name: str) -> None:
    text = json.loads((FIXTURE_ROOT / f"{fixture_name}.json").read_text(encoding="utf-8"))[
        "response_json"
    ]["text"]
    for pattern in _forbidden_patterns():
        assert not re.search(pattern, text, re.IGNORECASE), pattern


@pytest.mark.parametrize(
    "fixture_name",
    [
        "proposal_ai.detect_experience_gaps_v1",
        "proposal_ai.detect_experience_gaps_v1.with_gaps",
    ],
)
def test_gap_fixtures_only_use_the_experience_gap_taxonomy(fixture_name: str) -> None:
    issues = json.loads((FIXTURE_ROOT / f"{fixture_name}.json").read_text(encoding="utf-8"))[
        "response_json"
    ]["issues"]
    assert {issue["category"] for issue in issues} <= {"experience_gap"}


def test_generate_output_schema_requires_text_and_gaps() -> None:
    schema = json.loads(
        (PRODUCT_DIR / "schemas" / "generate_output.schema.json").read_text(encoding="utf-8")
    )
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"text", "gaps"}
    jsonschema.validate({"text": "Hi", "gaps": []}, schema)
    jsonschema.validate(
        {"text": "Hi", "gaps": [{"category": "experience_gap", "description": "d", "severity": "low"}]},
        schema,
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"text": "Hi"}, schema)


def test_prompt_uses_task_language_by_default_and_preserves_explicit_override() -> None:
    prompt = " ".join(_load_prompt("prompts/compose_persuasive_text.v2.md").split())

    assert "constraints.language" in prompt
    assert "language of `context.task_text`" in prompt
    assert "cannot be determined" in prompt
    assert "never decides the language" in prompt


def test_prompt_v2_pins_the_quality_rules_from_the_qa_report() -> None:
    prompt = " ".join(_load_prompt("prompts/compose_persuasive_text.v2.md").split())

    for fragment in (
        "Never rename, generalize",  # D-01
        "constraints.claims_to_avoid",  # D-15
        "Do not name an amount, rate, currency, deadline or duration",  # D-04
        "is not your offer",  # D-04 client budget
        "No placeholders",  # D-03
        "must not retell the client's task",  # D-05
        "No headings",  # D-06
        "No long dashes",  # D-06
        "A Russian positioning does not make an English order a Russian one",  # D-02
        "Do not list the whole profile",  # no padding with unrelated cases
        "Answer with one JSON object that has the single field `text`",  # no bare-text replies
        "similar project",  # D-08
        "`warm`:",  # D-07
        "`neutral`:",
        "`firm`:",
        "tie the text to a grammatical gender",  # D-13
    ):
        assert fragment in prompt, fragment


def test_gap_prompt_is_scoped_to_experience_gaps() -> None:
    prompt = _load_prompt("prompts/detect_experience_gaps.v1.md")
    assert "`experience_gap`" in prompt
    assert "Do not report routine steps" in " ".join(prompt.split())
    assert "empty `issues` array" in prompt


@pytest.mark.parametrize(
    "fixture_name",
    ["proposal_ai.compose_persuasive_text_v1", "proposal_ai.compose_persuasive_text_v1.weak_input"],
)
def test_fixtures_agree_with_the_a06_output_schema_shape(fixture_name: str) -> None:
    fixture = json.loads((FIXTURE_ROOT / f"{fixture_name}.json").read_text(encoding="utf-8"))
    output = fixture["response_json"]

    assert set(output) == {"text"}
    assert isinstance(output["text"], str)
    assert 1 <= len(output["text"]) <= 4000


def test_weak_input_fixture_is_a_distinct_bounded_draft_with_no_invented_specifics() -> None:
    happy = json.loads(
        (FIXTURE_ROOT / "proposal_ai.compose_persuasive_text_v1.json").read_text(encoding="utf-8")
    )["response_json"]["text"]
    weak = json.loads(
        (FIXTURE_ROOT / "proposal_ai.compose_persuasive_text_v1.weak_input.json").read_text(
            encoding="utf-8"
        )
    )["response_json"]["text"]

    assert weak != happy
    # No fabricated concrete numbers/dates that a vague brief could not have supplied -- digit
    # form ("4 years"), spelled-out form ("four years"), and hyphenated compound-adjective form
    # ("4-year", "three-week") all count. The happy fixture itself uses the spelled-out form, so a
    # digit-only pattern would prove nothing; a space-only separator would miss the hyphenated form
    # (code review finding, round 3).
    number_words = r"one|two|three|four|five|six|seven|eight|nine|ten|\d+"
    assert not re.search(rf"\b({number_words})[\s-]*(year|week|day)s?\b", weak, re.IGNORECASE)


# Code review finding: a year/week/day regex only catches invented *quantities* -- it cannot
# catch an invented concrete delivery commitment ("a first draft ready within the first week")
# or an invented claim about the freelancer's usual process ("here's how I typically work: a
# discovery step, a draft, then revisions"), neither of which is stated in either fixture's own
# task_text/freelancer_positioning. Denylisted here, checked against both fixtures -- the happy
# fixture is just as capable of inventing an unsupported commitment as the weak one.
INVENTED_COMMITMENT_PHRASES = (
    "first draft",
    "draft ready",
    "typically work",
    "how i work",
    "discovery step",
    "no ramp-up",
    "ramp up",
)


@pytest.mark.parametrize(
    "fixture_name",
    ["proposal_ai.compose_persuasive_text_v1", "proposal_ai.compose_persuasive_text_v1.weak_input"],
)
def test_fixtures_make_no_delivery_or_process_commitment_the_input_never_stated(
    fixture_name: str,
) -> None:
    text = json.loads((FIXTURE_ROOT / f"{fixture_name}.json").read_text(encoding="utf-8"))[
        "response_json"
    ]["text"].lower()
    for phrase in INVENTED_COMMITMENT_PHRASES:
        assert phrase not in text, f"{fixture_name} invents an unsupported commitment: {phrase!r}"


def test_language_pattern_rejects_a_trailing_newline() -> None:
    """Code review finding: Python's `re` (what jsonschema's `pattern` keyword actually runs)
    matches a trailing `$` just before a final `\\n`, so a naive `^...$` pattern silently accepts
    `"en\\n"` -- verified live against this repo's jsonschema. A bare `\\Z` anchor would close that
    gap too, but `\\Z` isn't part of ECMA-262 (the regex dialect JSON Schema's `pattern` keyword is
    defined against) and reads as a literal `Z` character under an ECMA-262 engine -- a portability
    regression the first fix introduced. `(?!\\n)$` closes the same gap with syntax that is valid,
    and means the same thing, under both engines: this pins the fix against a regression to either
    a bare `$` or back to `\\Z`."""
    schema = json.loads(
        (PRODUCT_DIR / "schemas" / "generate_input.schema.json").read_text(encoding="utf-8")
    )
    language_schema = schema["properties"]["language"]

    jsonschema.validate("en", language_schema)
    jsonschema.validate("en-US", language_schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate("en\n", language_schema)


@pytest.mark.parametrize("field_name", ["task_text", "freelancer_positioning"])
def test_required_text_fields_reject_untrimmed_values(field_name: str) -> None:
    """Code review finding: ANY-227 specifies both fields as a `required trimmed string`, but
    `pattern: "\\S"` only rejects an all-whitespace value -- `"  Build a site  "` passed, and
    nothing downstream (`normalize_mapping`) strips the padding before it reaches A06. Verified
    live against this repo's jsonschema. The fixed pattern requires the first and last character
    to be non-whitespace (an internal newline, e.g. a multi-line task description, stays legal --
    only leading/trailing whitespace is rejected), with the same `(?!\\n)` guard against Python
    `re`'s trailing-newline-tolerant `$` used for `language` above."""
    schema = json.loads(
        (PRODUCT_DIR / "schemas" / "generate_input.schema.json").read_text(encoding="utf-8")
    )
    field_schema = schema["properties"][field_name]

    jsonschema.validate("Build a site", field_schema)
    jsonschema.validate("a", field_schema)
    jsonschema.validate("Build a site\nwith two pages.", field_schema)
    untrimmed_values = (
        "  Build a site",
        "Build a site  ",
        "  Build a site  ",
        " ",
        "Build a site\n",
    )
    for untrimmed in untrimmed_values:
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(untrimmed, field_schema)


def test_generate_input_schema_matches_the_ticket_field_contract() -> None:
    schema = json.loads(
        (PRODUCT_DIR / "schemas" / "generate_input.schema.json").read_text(encoding="utf-8")
    )
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"task_text", "freelancer_positioning"}
    assert schema["properties"]["tone"]["enum"] == ["neutral", "warm", "firm"]
    assert schema["properties"]["language"]["pattern"] == "^[a-z]{2}(-[A-Z]{2})?(?!\\n)$"
    trimmed_pattern = "^\\S([\\s\\S]*\\S)?(?!\\n)$"
    assert schema["properties"]["task_text"]["pattern"] == trimmed_pattern
    assert schema["properties"]["freelancer_positioning"]["pattern"] == trimmed_pattern
