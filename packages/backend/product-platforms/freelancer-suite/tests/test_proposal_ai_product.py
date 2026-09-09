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
import yaml

REPO_ROOT = Path(__file__).resolve().parents[5]
PRODUCT_DIR = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "anytoolai_freelancer_suite"
    / "products"
    / "proposal_ai"
)
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "provider" / "fake_provider_outputs"


def _load_validate_architecture_module() -> Any:
    # Dynamic-load, same pattern as tests/architecture/test_bundle_composition_parity.py's
    # _load_validate_configs_module -- validate_architecture.py is pure stdlib (no
    # anytoolai_platform_core import chain), so this stays within ATAI007/ATAI008's ban on
    # product-platforms code depending on platform-core internals.
    path = REPO_ROOT / "scripts" / "agent" / "validate_architecture.py"
    spec = importlib.util.spec_from_file_location("validate_architecture_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Provider-SDK names come from validate_architecture.py's own LLM_PROVIDER_IMPORTS -- the single
# source of truth ATAI006 already enforces repo-wide -- rather than a second, hand-maintained copy
# that could silently drift from it (code review finding, round 3). Model-string prefixes are a
# distinct concern (raw text, not an import name) with no central list to reuse.
FORBIDDEN_PROVIDER_TERMS = tuple(_load_validate_architecture_module().LLM_PROVIDER_IMPORTS) + (
    "gpt-",
    "claude-",
    "gemini-",
)


def _load_yaml(name: str) -> dict:
    return yaml.safe_load((PRODUCT_DIR / name).read_text(encoding="utf-8"))


def test_action_type_sequence_is_exactly_compose_persuasive_text() -> None:
    action_configs = _load_yaml("action_configs.yaml")["action_configs"]
    assert [config["action_type"] for config in action_configs] == [
        "text.compose_persuasive_text"
    ]

    workflow = _load_yaml("workflows.yaml")["workflows"][0]
    action_config_by_id = {config["action_config_id"]: config for config in action_configs}
    step_action_types = [
        action_config_by_id[step["action_config_id"]]["action_type"]
        for step in workflow["steps"]
    ]
    assert step_action_types == ["text.compose_persuasive_text"]


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
    assert isinstance(policy["limit_count"], int) and policy["limit_count"] > 0


def test_renderer_contract_pins_the_canonical_copy_ready_field_to_a06_text() -> None:
    """Code review finding: ANY-227 lists a renderer contract as a Bundle-And-Workflow scope item
    (also required at the MVP-B spec level,
    docs/product-specs/mvp-b-freelancer-validation-bundle.md), distinct from ANY-243's later
    `apps/web-mirror` renderer *implementation*. Nothing under
    `products/proposal_ai/` pinned it before this file. Cross-checked against workflows.yaml and
    scenarios.yaml so it can't silently drift from the actual output schema / next action."""
    contract = _load_yaml("renderer_contract.yaml")["renderer_contract"]
    workflow = _load_yaml("workflows.yaml")["workflows"][0]
    scenario = _load_yaml("scenarios.yaml")["scenarios"][0]

    assert contract["scenario_id"] == scenario["scenario_id"]
    assert contract["output_schema_ref"] == workflow["output_schema_ref"]
    assert contract["output_schema_ref"] == "kernel.schemas.compose_persuasive_text_output_v1"
    assert contract["canonical_field"] == "text"
    assert contract["next_action"] in scenario["allowed_next_actions"]
    assert set(contract["excluded_fields"]) >= {"angle", "rationale", "model", "provider"}


def test_workflow_input_mapping_uses_only_generic_mapping_dsl_syntax() -> None:
    """No mapping-DSL change was needed: the whole `context` maps in one entry (`scenario.input`,
    single-segment target -- the DSL only rejects a *dotted* `context.*` target key), and
    tone/language stay optional via the existing `?`-prefix, not a new operator."""
    workflow = _load_yaml("workflows.yaml")["workflows"][0]
    step = workflow["steps"][0]
    mapping = step["input_mapping"]

    assert mapping["context"] == "scenario.input"
    assert mapping["constraints.tone"] == "?scenario.input.tone"
    assert mapping["constraints.language"] == "?scenario.input.language"
    assert mapping["constraints.format"].startswith("literal:")
    assert mapping["constraints.length"].startswith("literal:")
    assert mapping["objective"].startswith("literal:")


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
