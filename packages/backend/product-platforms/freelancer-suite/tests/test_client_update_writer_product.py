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
KERNEL_SCHEMAS_DIR = REPO_ROOT / "configs" / "kernel"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "provider" / "fake_provider_outputs"
# ANY-227 added a second product root (proposal_ai) ahead of this one in config_roots(), so pick
# this file's own root by name rather than assuming index 0.
(PRODUCT_DIR,) = (
    root for root in FreelancerSuiteBundle().config_roots() if root.name == "client_update_writer"
)


def _load_test_support_module() -> Any:
    # Dynamic-load by explicit path, same pattern this file already used for
    # validate_architecture.py -- code review finding: _load_validate_architecture_module(),
    # FORBIDDEN_TOKENS, and _load_yaml() were each duplicated verbatim in
    # test_proposal_ai_product.py; both now load this one shared module instead.
    path = Path(__file__).resolve().parent / "_test_support.py"
    spec = importlib.util.spec_from_file_location("freelancer_suite_test_support", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_test_support = _load_test_support_module()
# Provider-SDK names come from validate_architecture.py's own LLM_PROVIDER_IMPORTS -- the single
# source of truth ATAI006 already enforces repo-wide -- rather than a second, hand-maintained copy
# that could silently drift from it (code review finding: team lead #1). Model-string prefixes are
# a distinct concern (raw text, not an import name) with no central list to reuse.
FORBIDDEN_TOKENS = _test_support.FORBIDDEN_PROVIDER_TERMS


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
    return _test_support.load_yaml(PRODUCT_DIR, relative_path)


def _action_type_by_config_id() -> dict[str, str]:
    return {
        entry["action_config_id"]: entry["action_type"]
        for entry in _load_yaml("action_configs.yaml")["action_configs"]
    }


def _workflow_by_id() -> dict[str, dict[str, Any]]:
    return {entry["workflow_id"]: entry for entry in _load_yaml("workflows.yaml")["workflows"]}


def _load_prompt_template(prompt_ref: str) -> str:
    (entry,) = (
        item for item in _load_yaml("prompts.yaml")["prompts"] if item["prompt_ref"] == prompt_ref
    )
    return (PRODUCT_DIR / entry["template_path"]).read_text(encoding="utf-8")


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
            ("text.compose_persuasive_text",),
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
                {
                    "client_message": "Hi",
                    "reply_goal": "Answer.",
                    "tone": "neutral",
                    "extra_field": "nope",
                },  # additionalProperties: false -- code review finding: only update_input_v1 had
                # this case before.
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
                {
                    "billing_context": {"notes": "Phase 2", "amount": "$500"},
                    "tone": "firm",
                    "extra_field": "nope",
                },  # additionalProperties: false at the top level -- code review finding.
                {
                    "billing_context": {
                        "notes": "Phase 2",
                        "amount": "$500",
                        "extra_field": "nope",
                    },
                    "tone": "firm",
                },  # additionalProperties: false on the nested billing_context object -- code
                # review finding: this nesting level was entirely untested before.
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


_ACTION_CONFIG_OUTPUT_SCHEMAS = (
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
)


@pytest.mark.parametrize(
    ("action_config_id", "output_schema_ref", "fixture_suffix"),
    [
        (action_config_id, output_schema_ref, suffix)
        for action_config_id, output_schema_ref in _ACTION_CONFIG_OUTPUT_SCHEMAS
        for suffix in ("", ".weak_input")
    ],
)
def test_fixture_matches_its_output_schema(
    action_config_id: str,
    output_schema_ref: str,
    fixture_suffix: str,
) -> None:
    schema = _load_schema(output_schema_ref)

    fixture_path = FIXTURE_ROOT / f"{action_config_id}{fixture_suffix}.json"
    assert fixture_path.is_file(), fixture_path
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    jsonschema.validate(fixture["response_json"], schema)


# ANY-413's own ticket scope requires "Deterministic happy-path and weak-input fake-provider
# fixtures" -- distinct from schema validity (test_fixture_matches_its_output_schema above), this
# proves the weak fixture is actually a different, appropriately hedged draft rather than an
# accidental copy of the happy-path one, and doesn't invent a specific day the weak/vague input
# never supplied (mirrors test_proposal_ai_product.py's weak-fixture content checks, scaled down
# to this product's shorter, deliberately fact-free weak inputs).
_DAY_WORDS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


@pytest.mark.parametrize("action_config_id", [pair[0] for pair in _ACTION_CONFIG_OUTPUT_SCHEMAS])
def test_weak_input_fixture_is_distinct_and_invents_no_specific_day(action_config_id: str) -> None:
    happy_text = json.loads(
        (FIXTURE_ROOT / f"{action_config_id}.json").read_text(encoding="utf-8")
    )["response_json"]["text"]
    weak_text = json.loads(
        (FIXTURE_ROOT / f"{action_config_id}.weak_input.json").read_text(encoding="utf-8")
    )["response_json"]["text"]

    assert weak_text != happy_text
    assert not any(day in weak_text.lower() for day in map(str.lower, _DAY_WORDS)), action_config_id


# Code review finding: the day-word check above only catches invented *dates* -- it cannot catch
# an invented *absence-of-information* claim ("I don't have a firm milestone to share yet") or an
# invented future commitment neither the weak scenario input's progress_notes/reply_goal actually
# states. Denylisted here and checked against every weak fixture -- a well-grounded response to a
# vague-but-non-empty input restates the input plainly, it does not assert what information is or
# isn't available.
_UNGROUNDED_HEDGE_PHRASES = ("don't have", "no update", "nothing to report", "no firm")


@pytest.mark.parametrize("action_config_id", [pair[0] for pair in _ACTION_CONFIG_OUTPUT_SCHEMAS])
def test_weak_input_fixture_invents_no_absence_of_information_claim(action_config_id: str) -> None:
    weak_text = json.loads(
        (FIXTURE_ROOT / f"{action_config_id}.weak_input.json").read_text(encoding="utf-8")
    )["response_json"]["text"].lower()

    for phrase in _UNGROUNDED_HEDGE_PHRASES:
        assert phrase not in weak_text, (action_config_id, phrase)


# Code review finding: content fields only had `minLength: 1`, which accepts a whitespace-only
# value (`" "`), and `constraints.language` used a bare `^...$` pattern, which Python's `re` (what
# jsonschema's `pattern` keyword runs) treats as matching just before a trailing `"\n"` too --
# mirrors test_proposal_ai_product.py's own regression tests for the same two gaps, already fixed
# there.
_TRIMMED_CONTENT_FIELDS = (
    ("client_update_writer.update_input_v1", "progress_notes"),
    ("client_update_writer.reply_draft_input_v1", "client_message"),
    ("client_update_writer.reply_draft_input_v1", "reply_goal"),
    ("client_update_writer.prepaid_request_input_v1", "billing_context.notes"),
    ("client_update_writer.prepaid_request_input_v1", "billing_context.amount"),
    ("client_update_writer.prepaid_request_input_v1", "billing_context.due_date"),
)


def _nested_field_schema(schema: dict[str, Any], dotted_path: str) -> dict[str, Any]:
    node = schema
    for part in dotted_path.split("."):
        node = node["properties"][part]
    return node


@pytest.mark.parametrize(("schema_ref", "field_path"), _TRIMMED_CONTENT_FIELDS)
def test_content_fields_reject_whitespace_only_and_trailing_newline(
    schema_ref: str,
    field_path: str,
) -> None:
    field_schema = _nested_field_schema(_load_schema(schema_ref), field_path)

    jsonschema.validate("Some text", field_schema)
    jsonschema.validate("a", field_schema)
    jsonschema.validate("Some text\nwith an internal newline.", field_schema)
    for untrimmed in (" ", "  Some text", "Some text  ", "  Some text  ", "Some text\n"):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(untrimmed, field_schema)


@pytest.mark.parametrize(
    "schema_ref",
    [
        "client_update_writer.update_input_v1",
        "client_update_writer.reply_draft_input_v1",
        "client_update_writer.prepaid_request_input_v1",
    ],
)
def test_constraints_language_pattern_rejects_a_trailing_newline(schema_ref: str) -> None:
    language_schema = _load_schema(schema_ref)["properties"]["constraints"]["properties"][
        "language"
    ]

    jsonschema.validate("en", language_schema)
    jsonschema.validate("en-US", language_schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate("en\n", language_schema)


# Code review finding: PrepaidRequest's prompts forced a causal/gating claim ("is needed before
# work continues", "keeps ... on schedule") regardless of whether billing_context actually
# supports one -- both weak fixtures proved it invented the claim from vague input. Denylisted
# here across both prepaid_request action configs' fixtures (happy and weak).
_UNGROUNDED_CAUSALITY_PHRASES = ("before work continues", "on schedule", "keeps things moving")


@pytest.mark.parametrize(
    "action_config_id",
    [
        "client_update_writer.prepaid_request_compose_persuasive_text_v1",
    ],
)
@pytest.mark.parametrize("fixture_suffix", ["", ".weak_input"])
def test_prepaid_request_fixtures_invent_no_causal_or_gating_claim(
    action_config_id: str,
    fixture_suffix: str,
) -> None:
    text = json.loads(
        (FIXTURE_ROOT / f"{action_config_id}{fixture_suffix}.json").read_text(encoding="utf-8")
    )["response_json"]["text"].lower()

    for phrase in _UNGROUNDED_CAUSALITY_PHRASES:
        assert phrase not in text, (action_config_id, fixture_suffix, phrase)


# Code review finding: the happy-path fixture wrote "before Friday" for a `due_date: "Friday"`
# input -- "before Friday" is a strictly earlier deadline than "by Friday"/"due Friday", tightening
# a fact the prompt explicitly says must not go beyond what `context`/`situation` provides.
_DUE_DATE_TIGHTENING_PATTERN = re.compile(
    r"\bbefore (Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b", re.IGNORECASE
)


@pytest.mark.parametrize(
    "action_config_id",
    [
        "client_update_writer.prepaid_request_compose_persuasive_text_v1",
    ],
)
def test_prepaid_request_happy_fixture_does_not_tighten_the_due_date(action_config_id: str) -> None:
    text = json.loads((FIXTURE_ROOT / f"{action_config_id}.json").read_text(encoding="utf-8"))[
        "response_json"
    ]["text"]
    assert _DUE_DATE_TIGHTENING_PATTERN.search(text) is None, action_config_id


# Urgency (ANY-603), shared by the objective and fixture tests; the prompt's own list is examples,
# the rule is by meaning. Always-urgent words and invented deadlines count anywhere; time words
# that are neutral on their own ("agreed today", "starts soon") count only in a sentence that
# asks for payment.
_URGENCY_WORDS = re.compile(
    r"\b(now(?! that)|promptly|asap|shortly|quickly|immediately|urgent(ly)?|urgency|at once"
    r"|right away|straight away|without delay)\b|as soon as",
    re.IGNORECASE,
)
_INVENTED_DEADLINE = re.compile(
    r"\bwithin \d+\s+\w+|\b(end of (the )?(day|week|month)|by tomorrow|by tonight)\b",
    re.IGNORECASE,
)
_PAYMENT_VERB = re.compile(r"\b(send|pay|remit|transfer|wire|prepay\w*)\b", re.IGNORECASE)
_TIME_PRESSURE = re.compile(r"\b(today|soon)\b", re.IGNORECASE)


def _adds_urgency(text: str) -> bool:
    return any(
        _URGENCY_WORDS.search(sentence)
        or _INVENTED_DEADLINE.search(sentence)
        or (_PAYMENT_VERB.search(sentence) and _TIME_PRESSURE.search(sentence))
        for sentence in re.split(r"(?<=[.?!])\s+", text)
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Please send USD 500 promptly.", True),
        ("Please send USD 500 as soon as possible.", True),
        ("Please send USD 500 within 24 hours, by Friday.", True),
        ("Please send USD 500 by end of week.", True),
        ("Could you pay today?", True),
        ("Please send the deposit soon.", True),
        ("Could you pay the invoice today?", True),
        ("Now that phase 1 is done, please send USD 500 by Friday.", False),
        ("The deposit was agreed today. Please send USD 500 by Friday.", False),
        ("Phase 2 starts soon. Please send USD 500 by Friday.", False),
        ("Could you send the $500 prepayment by Friday? Let me know once it has been sent.", False),
    ],
)
def test_urgency_detector_separates_payment_urgency_from_neutral_context(
    text: str, expected: bool
) -> None:
    assert _adds_urgency(text) is expected


def _normalized_prepaid_prompt() -> str:
    return " ".join(
        _load_prompt_template(
            "client_update_writer.prepaid_request_compose_persuasive_text.v1"
        ).split()
    )


# The prepaid step's `objective` is neutral (ANY-603/ANY-602): it hardcodes neither urgency, nor
# the closing line, nor the message kind -- all of that lives in the prompt.
def test_prepaid_request_objective_is_neutral() -> None:
    workflow = _workflow_by_id()["client_update_writer.prepaid_request_v1"]
    (step,) = workflow["steps"]
    objective = step["input_mapping"]["objective"].lower()

    assert not _adds_urgency(objective)
    assert "has been sent" not in objective
    # Not an unconditional payment ask; the alternative message kind is chosen by the prompt.
    assert "send the requested prepayment" not in objective
    assert "following the prompt rules" in objective
    assert "confirm" not in objective


# ANY-601: the single A06 step gets the whole billing_context object (notes, amount, optional
# due_date) -- no string joining and no second step that could lose a field.
def test_prepaid_request_single_step_receives_the_whole_billing_context() -> None:
    workflow = _workflow_by_id()["client_update_writer.prepaid_request_v1"]
    (step,) = workflow["steps"]

    assert step["step_id"] == "compose_persuasive_text"
    assert step["input_mapping"]["context"] == "scenario.input.billing_context"
    assert step["output_mapping"] == {
        "context.workflow_output": "steps.compose_persuasive_text.output"
    }


# Code review finding (team lead #2): `?scenario.input...` silently skips an absent source, and the
# fake provider isn't input-sensitive, so a typo'd/deleted source path here could keep E2E green
# while dropping language/length/format for a live provider. Pins the exact source paths.
def test_prepaid_request_persuasive_text_step_maps_constraints_from_expected_sources() -> None:
    workflow = _workflow_by_id()["client_update_writer.prepaid_request_v1"]
    persuasive_step = next(
        step for step in workflow["steps"] if step["step_id"] == "compose_persuasive_text"
    )
    mapping = persuasive_step["input_mapping"]

    assert mapping["constraints.language"] == "?scenario.input.constraints.language"
    assert mapping["constraints.length"] == "?scenario.input.constraints.max_length"
    assert mapping["constraints.format"] == "?scenario.input.constraints.output_format"


# Code review finding (xhigh #5): the per-field constraint mapping above already has a pinning
# test for compose_persuasive_text; the plain `constraints` mapping on each mode's compose_reply
# step had none.
@pytest.mark.parametrize(
    "workflow_id",
    [
        "client_update_writer.update_v1",
        "client_update_writer.reply_draft_v1",
    ],
)
def test_compose_reply_step_maps_constraints_from_scenario_input(workflow_id: str) -> None:
    workflow = _workflow_by_id()[workflow_id]
    reply_step = next(step for step in workflow["steps"] if step["step_id"] == "compose_reply")

    assert reply_step["input_mapping"]["constraints"] == "?scenario.input.constraints"


# The E2E test's amount/due_date assertion doesn't protect the *other* grounded facts the billing
# notes state (week, phase type, sequence) -- this class of regression (dropping/rewording them
# while paraphrasing) had already recurred once. Pins that the happy text keeps all three,
# independent of exact wording.
_HAPPY_NOTES_FACTS = ("this week", "development", "starting next")


def test_prepaid_request_happy_text_preserves_notes_facts() -> None:
    text = _prepaid_fixture_text("")

    for fact in _HAPPY_NOTES_FACTS:
        assert fact in text.lower(), fact


def _prepaid_fixture_text(fixture_suffix: str) -> str:
    fixture = FIXTURE_ROOT / (
        f"client_update_writer.prepaid_request_compose_persuasive_text_v1{fixture_suffix}.json"
    )
    return json.loads(fixture.read_text(encoding="utf-8"))["response_json"]["text"]


# The happy fixture is a payment request; the weak one (no amount value or currency in its input)
# is a terms confirmation per the prompt, so it must not ask for payment or a payment report.
def test_prepaid_request_happy_fixture_asks_to_be_told_once_sent() -> None:
    text = _prepaid_fixture_text("").lower()

    assert "when you get a chance" not in text
    assert "let me know once it has been sent" in text


def test_prepaid_request_weak_fixture_is_a_terms_confirmation() -> None:
    # Exact text on purpose: any rewrite must be a conscious change here, because the text must
    # stay a confirmation request (no payment ask, no "let me know once it has been sent").
    assert _prepaid_fixture_text(".weak_input") == (
        "The project is still in progress. Could you confirm the payment amount and its "
        "currency? Please reply with the confirmation."
    )


# ANY-603: neither fixture's input expresses urgency (the happy one has a plain date and firm
# tone, the weak one no deadline), so both must stay neutral.
@pytest.mark.parametrize("fixture_suffix", ["", ".weak_input"])
def test_prepaid_request_fixtures_have_no_urgency(fixture_suffix: str) -> None:
    assert not _adds_urgency(_prepaid_fixture_text(fixture_suffix))


# ANY-603: urgency only with a basis in the input; neutral request otherwise. Model behavior is
# only provable live (ANY-604); this pins the rule text.
def test_prepaid_request_prompt_gates_urgency_on_the_input() -> None:
    prompt = _normalized_prepaid_prompt()

    assert "Urgency in a payment request comes only from `context.notes`" in prompt
    assert "or the free text of `context.due_date` that themselves express urgency" in prompt
    assert '`due_date: "Friday — ASAP"`' in prompt
    assert "then the notes win and only the date is stated, without its urgency words" in prompt
    assert "urgency words in it follow the urgency rule below" in prompt
    assert "A plain date in `context.due_date`, a placeholder `due_date`" in prompt
    assert "add no urgency words of your own" in prompt
    assert "make a neutral request" in prompt
    assert "do not soften it into an open-ended timeframe" in prompt
    assert "Firmness belongs in the wording, not in a deadline" in prompt


# ANY-601: with no `due_date` in `context`, the model must not invent a date; this pins the rule.
def test_prepaid_request_prompt_forbids_invented_dates_without_a_due_date() -> None:
    prompt = _load_prompt_template(
        "client_update_writer.prepaid_request_compose_persuasive_text.v1"
    )

    assert "If `context` has no `due_date`, do not state or imply any date" in prompt


def test_renderer_contract_pins_the_canonical_copy_ready_composition() -> None:
    """Code review finding: ANY-413 lists "Renderer contract for a copy-ready client message" as
    a Bundle-And-Workflow scope item, distinct from ANY-412/ANY-414's later apps/web-mirror
    renderer *implementation* -- nothing under products/client_update_writer/ pinned it before
    this file. Mirrors ProposalAI's own renderer_contract.yaml + regression test. Cross-checked
    against workflows.yaml/scenarios.yaml for all three modes so it can't silently drift from the
    actual output schema / next action."""
    contract = _load_yaml("renderer_contract.yaml")["renderer_contract"]
    workflows_by_id = _workflow_by_id()
    scenarios_by_id = {
        entry["scenario_id"]: entry for entry in _load_yaml("scenarios.yaml")["scenarios"]
    }

    assert set(contract["scenarios"]) == set(scenarios_by_id)
    for scenario_id in contract["scenarios"]:
        scenario = scenarios_by_id[scenario_id]
        workflow = workflows_by_id[scenario["workflow_id"]]
        assert workflow["output_schema_ref"] == contract["output_schema_ref"]
        assert contract["next_action"] in scenario["allowed_next_actions"]

    assert contract["output_schema_ref"] == "kernel.schemas.compose_reply_output_v1"
    assert contract["canonical_field"] == "text"
    assert contract["call_to_action_field"] == "call_to_action"
    assert contract["call_to_action_composition"] == "append_after_blank_line"
    assert contract["excluded_fields"] == []

    output_schema_properties = _load_schema(contract["output_schema_ref"])["properties"]
    assert contract["canonical_field"] in output_schema_properties
    assert contract["call_to_action_field"] in output_schema_properties


# Code review finding (team lead #1 fix, "me #10"): the deterministic e2e tests run against fixed
# fake-provider fixtures, so they can't prove a real model honors this prompt's constraints.language/
# length/format instructions -- only the prompt text itself can regress here undetected. Pins that
# A06's canonical language/length/format rules (including the html-format case) actually made it
# into the product-owned prompt, not just the workflow mapping that feeds those fields in.
def test_prepaid_request_persuasive_text_prompt_documents_language_length_and_format() -> None:
    prompt = _load_prompt_template(
        "client_update_writer.prepaid_request_compose_persuasive_text.v1"
    )

    assert "constraints.language" in prompt
    assert "constraints.length" in prompt
    assert "constraints.format" in prompt
    assert "html" in prompt.lower()


def test_prepaid_request_max_length_floor_fits_longest_amount_and_due_date() -> None:
    schema = _load_schema("client_update_writer.prepaid_request_input_v1")
    context = schema["properties"]["billing_context"]["properties"]
    floor = schema["properties"]["constraints"]["properties"]["max_length"]["minimum"]
    # "Please send <amount> by <due_date>. Please let me know once it has been sent." plus slack
    overhead = len("Please send  by . Please let me know once it has been sent.") + 20

    assert context["amount"]["maxLength"] + context["due_date"]["maxLength"] + overhead <= floor

    base = {"billing_context": {"notes": "Phase 2 prepayment", "amount": "$500"}, "tone": "firm"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**base, "constraints": {"max_length": floor - 1}}, schema)
    jsonschema.validate({**base, "constraints": {"max_length": floor}}, schema)


# ANY-602: the prompt decides the kind of message with one ordered rule list ("first matching rule
# wins", only the last rule may ask for payment) over one definition of an open condition, so a
# new case maps onto a bullet instead of a new branch that needs its own priority clause. Model
# behavior is only provable live (ANY-604): the fake provider returns one fixed response, so the
# rule text is what is pinned here.
def test_prepaid_request_prompt_has_terms_confirmation_rule() -> None:
    prompt = " ".join(
        _load_prompt_template(
            "client_update_writer.prepaid_request_compose_persuasive_text.v1"
        ).split()
    )

    # Structure: attribution to this payment, one open-condition definition, ordered rules.
    assert "Only facts about *this* payment" in prompt
    assert "never a conflict with `context.amount` / `context.due_date`" in prompt
    assert "the first matching rule wins" in prompt
    assert "Only rule D may ask for payment" in prompt
    rule_positions = [
        prompt.index(marker)
        for marker in (
            "A. Nothing is owed on this payment as things stand now",
            "B. Any condition is open",
            "C. The notes say not to ask for payment yet",
            "D. Otherwise",
        )
    ]
    assert rule_positions == sorted(rule_positions)

    # What opens a condition: every ANY-602 / review case is one bullet of this list.
    for trigger in (
        "not agreed, disputed, awaiting confirmation or contradicted",
        "a different current amount, currency or due date for this payment",
        '`amount: USD 1,200` against "deposit is 50%, USD 1,000"',
        'placeholder such as "TBD"',
        "an absent `due_date` is not a placeholder",
        "names no currency (a bare number, or one with other words",
        "do not tie a currency to this payment",
        "part of this amount was received (and not reversed) and the notes do not state the remaining figure",
        "do not add up",
        "a due date for this payment",
    ):
        assert trigger in prompt, trigger
    assert "Never open by themselves: a missing `due_date`, payment details still to come" in prompt

    # Rules A-C never ask for payment; a confirmation names only open points, no placeholders.
    assert "Rules A–C never ask the client to pay or remit" in prompt
    assert "confirm only the open conditions" in prompt
    # A settled/cancelled payment wins over an obsolete open condition; D states one amount only.
    assert "An obsolete placeholder in `context.amount` or `context.due_date`" in prompt
    # A completed, undisputed refund of a cancelled request is settled (rule A), not open.
    assert "final with nothing owed keeps A" in prompt
    assert "A reversal, refund or chargeback matters only through what it leaves" in prompt
    # "Received in full" must match the amount field; a different settled amount is a conflict.
    assert "A settled amount that differs from a concrete `context.amount`" in prompt
    assert "USD 1,000 settled against `amount: USD 1,200`" in prompt
    # A placeholder amount has nothing to compare: a fully settled payment stays in rule A.
    assert "does not block this: it compares with nothing" in prompt
    # A currency the notes tie to this payment is stated with the number, which is unchanged.
    assert "Always state the currency with the number, never a bare figure" in prompt
    assert '`amount: USD 1,000` with "750 remains" is "USD 750"' in prompt
    assert "The currency is the one `context.amount` names, else the one the notes tie" in prompt
    assert '"300 remains" is "USD 300"' in prompt
    assert "A different currency in the notes is an open point, not a choice" in prompt
    assert '`amount: 500` with "the currency is USD" is "USD 500"' in prompt
    # A currency named in the notes that differs from the amount field is a different amount.
    assert "a different current amount, currency or due date for this payment" in prompt
    assert '`amount: USD 500` against "the agreed currency is EUR"' in prompt
    # A project total matters when this payment is computed from it and the total is not agreed.
    assert "A project total is no exception when this payment is computed from it" in prompt
    assert "is computed from a base (a total, a rate) that the notes say is not agreed" in prompt
    assert "(50% of USD 2,000 or of USD 2,400)" in prompt
    # Two *current* candidates open the base; a superseded base next to an agreed one does not.
    assert "leave as two current candidates" in prompt
    assert "a rejected or superseded base next to one agreed current base opens nothing" in prompt
    # Alternatives or a range are not one amount; a reversal goes to B, the thank-you stays in A.
    assert 'alternatives such as "USD 500 or EUR 460", or a range' in prompt
    assert "a short thank-you for the payment, or a note that the request is withdrawn" in prompt
    assert (
        "pending or contested, a live dispute about the received amount, or an unclear status"
        in prompt
    )
    # An "agreed" value that differs from the field is still open; the claim is not repeated.
    assert "even if the notes call that value agreed" in prompt
    assert (
        "without presenting either value as settled or repeating the notes' agreement claim"
        in prompt
    )
    # The due date is echoed only in a payment request; A and C never present it as upcoming.
    assert "In a payment request, when `context.due_date` is a real, non-placeholder" in prompt
    assert "rules A and C never present an amount or due date as owed or upcoming" in prompt
    # A live dispute beats the settled status; a computed deposit is a "different amount".
    assert "a live dispute about the received amount" in prompt
    assert "an amount that the notes' own terms determine" in prompt
    # Only a currently settled payment is acknowledged; reversals are open; history is no conflict.
    assert (
        "receipts that add up to `context.amount`, or a stated zero balance, count as in full"
        in prompt
    )
    assert "final with an agreed amount still owed is an ordinary unpaid payment" in prompt
    assert "rejected, superseded or replaced is history, not a conflict" in prompt
    assert (
        "the stated remaining figure after a partial receipt, else `context.amount`, never both"
        in prompt
    )
    assert "that conflicts with nothing stays stated as agreed" in prompt
    assert "Never print a placeholder as a value" in prompt
    # D asks for the amount still due, never the full amount after a partial payment.
    assert (
        "payment request for the amount still due: the remaining figure the notes state" in prompt
    )
    # Length fallback never endorses a value; a relative term is a real due date.
    assert "ask the client to confirm only the conditions that are actually open" in prompt
    assert "without stating or endorsing any value" in prompt
    assert '"Net 30 after invoice"' in prompt
    assert "Rules A–C never ask the client to report a payment" in prompt
