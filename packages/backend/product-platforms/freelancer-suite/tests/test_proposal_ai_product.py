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


def test_language_pattern_rejects_a_trailing_newline() -> None:
    """Code review finding: Python's `re` (what jsonschema's `pattern` keyword actually runs)
    matches a trailing `$` just before a final `\\n`, so a naive `^...$` pattern silently accepts
    `"en\\n"` -- verified live against this repo's jsonschema. `\\Z` closes that gap; this pins
    the fix against a regression back to `$`."""
    schema = json.loads(
        (PRODUCT_DIR / "schemas" / "generate_input.schema.json").read_text(encoding="utf-8")
    )
    language_schema = schema["properties"]["language"]

    jsonschema.validate("en", language_schema)
    jsonschema.validate("en-US", language_schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate("en\n", language_schema)


def test_generate_input_schema_matches_the_ticket_field_contract() -> None:
    schema = json.loads(
        (PRODUCT_DIR / "schemas" / "generate_input.schema.json").read_text(encoding="utf-8")
    )
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"task_text", "freelancer_positioning"}
    assert schema["properties"]["tone"]["enum"] == ["neutral", "warm", "firm"]
    assert schema["properties"]["language"]["pattern"] == "^[a-z]{2}(-[A-Z]{2})?\\Z"
