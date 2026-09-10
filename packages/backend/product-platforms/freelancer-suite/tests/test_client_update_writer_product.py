"""ANY-413 full-check-covered deeper evidence for the client_update_writer product: all three
modes' config-graph shape, weak-input schema rejection per mode, deterministic fixture/output
schema agreement, and the "product code contains no PydanticAI/LiteLLM/provider SDK/model-string
usage" acceptance criterion (config/prompts are YAML/JSON/Markdown only -- no Python at all).

Deliberately reads raw YAML/JSON here instead of anytoolai_platform_core.config.loader.ConfigLoader
-- ATAI007 (scripts/agent/validate_architecture.py) forbids product-platforms code, tests
included, from importing anytoolai_platform_core at all; product-platforms depends on
platform-sdk's ProductBundle contract only. Config-load-through-the-real-composition-boundary
proof already lives in apps/platform-api/tests/test_client_update_writer_bundle.py (quick-check
covers that file, not this package's tests), so this file goes deeper on the raw config content
instead of duplicating that proof.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import yaml
from anytoolai_freelancer_suite.bundle import FreelancerSuiteBundle

REPO_ROOT = Path(__file__).resolve().parents[5]
KERNEL_SCHEMAS_DIR = REPO_ROOT / "configs" / "kernel"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "provider" / "fake_provider_outputs"
# ANY-227 added a second product root (proposal_ai) ahead of this one in config_roots(), so pick
# this file's own root by name rather than assuming index 0.
(PRODUCT_DIR,) = (
    root for root in FreelancerSuiteBundle().config_roots() if root.name == "client_update_writer"
)

FORBIDDEN_TOKENS = (
    "pydantic_ai",
    "litellm",
    "openai",
    "anthropic",
    "google.genai",
    "@google/genai",
    "cohere",
    "mistralai",
)


def _forbidden_token_pattern(token: str) -> re.Pattern[str]:
    """Bare identifier-shaped tokens (e.g. "cohere") get word-boundary matching so ordinary prose
    ("...results were coherent...") can't false-positive; the two compound package-name tokens
    ("google.genai", "@google/genai") already contain non-word delimiters that make accidental
    collision implausible, so they stay plain substring matches. Case-insensitive throughout --
    "OpenAI"/"Anthropic" in prose must be caught the same as "openai"/"anthropic"."""
    if re.fullmatch(r"[A-Za-z_]+", token):
        return re.compile(rf"\b{re.escape(token)}\b", re.IGNORECASE)
    return re.compile(re.escape(token), re.IGNORECASE)


def _load_yaml(relative_path: str) -> dict[str, Any]:
    return yaml.safe_load((PRODUCT_DIR / relative_path).read_text(encoding="utf-8"))


def _action_type_by_config_id() -> dict[str, str]:
    return {
        entry["action_config_id"]: entry["action_type"]
        for entry in _load_yaml("action_configs.yaml")["action_configs"]
    }


def _workflow_by_id() -> dict[str, dict[str, Any]]:
    return {entry["workflow_id"]: entry for entry in _load_yaml("workflows.yaml")["workflows"]}


def _load_schema(schema_ref: str) -> dict[str, Any]:
    """Resolves a schema_ref against whichever schemas.yaml manifest owns it: the product's own
    (relative to PRODUCT_DIR) for `client_update_writer.*` refs, or the kernel's (relative to
    KERNEL_SCHEMAS_DIR) for `kernel.schemas.*` refs -- mirrors ConfigLoader._load_schemas's two
    manifests without importing it."""
    if schema_ref.startswith("kernel."):
        manifest_dir = KERNEL_SCHEMAS_DIR
        manifest = yaml.safe_load((manifest_dir / "schemas.yaml").read_text(encoding="utf-8"))
    else:
        manifest_dir = PRODUCT_DIR
        manifest = _load_yaml("schemas.yaml")
    (entry,) = (item for item in manifest["schemas"] if item["schema_ref"] == schema_ref)
    return json.loads((manifest_dir / entry["file_path"]).read_text(encoding="utf-8"))


def test_product_directory_contains_no_python_or_forbidden_provider_references() -> None:
    all_files = [path for path in PRODUCT_DIR.rglob("*") if path.is_file()]
    assert all_files, "expected the product directory to contain config files"

    python_files = [path for path in all_files if path.suffix == ".py"]
    assert python_files == [], f"product config must be YAML/JSON/Markdown only: {python_files}"

    for path in all_files:
        content = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            assert _forbidden_token_pattern(token).search(content) is None, (path, token)


@pytest.mark.parametrize(
    ("mode", "workflow_id", "expected_action_types"),
    [
        ("update", "client_update_writer.update_v1", ("text.compose_reply",)),
        ("reply_draft", "client_update_writer.reply_draft_v1", ("text.compose_reply",)),
        (
            "prepaid_request",
            "client_update_writer.prepaid_request_v1",
            ("text.compose_persuasive_text", "text.compose_reply"),
        ),
    ],
)
def test_each_mode_workflow_uses_only_generic_atom_action_types(
    mode: str,
    workflow_id: str,
    expected_action_types: tuple[str, ...],
) -> None:
    workflow = _workflow_by_id()[workflow_id]
    action_type_by_config_id = _action_type_by_config_id()

    actual_action_types = tuple(
        action_type_by_config_id[step["action_config_id"]] for step in workflow["steps"]
    )
    assert actual_action_types == expected_action_types, mode


@pytest.mark.parametrize(
    ("schema_ref", "weak_inputs"),
    [
        (
            "client_update_writer.update_input_v1",
            [
                {},  # missing every required field
                {"progress_notes": "", "tone": "warm"},  # empty string violates minLength
                {"progress_notes": "Notes.", "tone": "angry"},  # invalid enum
                {
                    "progress_notes": "Notes.",
                    "tone": "warm",
                    "extra_field": "nope",
                },  # additionalProperties: false
            ],
        ),
        (
            "client_update_writer.reply_draft_input_v1",
            [
                {},
                {"client_message": "Hi", "tone": "neutral"},  # missing reply_goal
                {
                    "client_message": "Hi",
                    "reply_goal": "Answer.",
                    "tone": "calm",  # invalid enum
                },
            ],
        ),
        (
            "client_update_writer.prepaid_request_input_v1",
            [
                {},
                {"billing_context": {"notes": "Phase 2"}, "tone": "firm"},  # missing amount
                {
                    "billing_context": {"notes": "Phase 2", "amount": "$500"},
                    "tone": "urgent",  # invalid enum
                },
            ],
        ),
    ],
)
def test_weak_inputs_are_rejected_per_mode(
    schema_ref: str,
    weak_inputs: list[dict[str, Any]],
) -> None:
    schema = _load_schema(schema_ref)

    for weak_input in weak_inputs:
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(weak_input, schema)


@pytest.mark.parametrize(
    ("action_config_id", "output_schema_ref"),
    [
        (
            "client_update_writer.update_compose_reply_v1",
            "kernel.schemas.compose_reply_output_v1",
        ),
        (
            "client_update_writer.reply_draft_compose_reply_v1",
            "kernel.schemas.compose_reply_output_v1",
        ),
        (
            "client_update_writer.prepaid_request_compose_persuasive_text_v1",
            "kernel.schemas.compose_persuasive_text_output_v1",
        ),
        (
            "client_update_writer.prepaid_request_compose_reply_v1",
            "kernel.schemas.compose_reply_output_v1",
        ),
    ],
)
def test_happy_path_fixture_matches_its_output_schema(
    action_config_id: str,
    output_schema_ref: str,
) -> None:
    schema = _load_schema(output_schema_ref)

    fixture_path = FIXTURE_ROOT / f"{action_config_id}.json"
    assert fixture_path.is_file(), fixture_path
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    jsonschema.validate(fixture["response_json"], schema)
