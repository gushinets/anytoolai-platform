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
from typing import Any, Literal

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
    # Code review finding (me #1): A05's questions[].category reuses its source issue's
    # category (generate_questions.v1.md) -- it must be closed over the same taxonomy, not left
    # an open string the A05 cross-validator never checks.
    assert set(schema["questions"]["items"]["properties"]["category"]["enum"]) == set(taxonomy)
    assert _literal(steps["extract"]["input_mapping"]["strict"]) is False
    # Code review finding (me #7): the canonical schema's question cap must equal what A05 is
    # actually asked for -- it was 10 while every valid run is capped at 5, so a 6-10 question
    # artifact validated although no run of this workflow can produce one.
    max_questions = _literal(steps["generate_questions"]["input_mapping"]["max_questions"])
    assert schema["questions"]["maxItems"] == max_questions

    for field in fields:
        expected_shape = _A01_TYPE_TO_JSON_SCHEMA_TYPE[field["type"]]
        declared_property = value_properties[field["name"]]
        assert declared_property["type"] == expected_shape["type"], field["name"]
        if expected_shape["type"] == "array":
            assert declared_property["items"]["type"] == expected_shape["items"]["type"], (
                field["name"]
            )


@pytest.mark.parametrize("state", ["present_and_missing", "absent_from_both", "confidence_only"])
def test_a01_field_invariants_hold_for_every_configured_field(state: str) -> None:
    """The canonical schema must reject what A01's cross-validator rejects (a field both present
    and missing, in neither, or carrying confidence without a value), for *every* field in the
    workflow's own A01 field list -- derived from it, so a new field can't silently skip them."""
    fields = [f["name"] for f in _literal(_steps()["extract"]["input_mapping"]["fields"])]
    schema = _load_schema("brief_decoder.decode_output_v1")
    validator = jsonschema.validators.validator_for(schema)(schema)
    complete = json.loads(
        (FIXTURE_ROOT / "brief_decoder.extract_brief_v1.no_issues.json").read_text("utf-8")
    )["response_json"]
    document = _fixture_response("brief_decoder.generate_summary_v1.no_issues")

    def output(brief: dict[str, Any]) -> dict[str, Any]:
        return {
            "brief_text": "x",
            "brief": brief,
            "issues": [],
            "questions": [],
            "document": document,
        }

    assert validator.is_valid(output(complete))  # control: every field present, none missing
    for name in fields:
        brief = json.loads(json.dumps(complete))
        if state == "present_and_missing":
            brief["missing_fields"] = [name]
        elif state == "absent_from_both":
            del brief["values"][name]
            brief["confidence"].pop(name, None)
        else:
            del brief["values"][name]
            brief["missing_fields"] = [name]
        assert not validator.is_valid(output(brief)), (state, name)


# Human-readable stem each A01 field must be reported under in the `gaps` section. Keyed by every
# field so the check below can't silently skip a new one.
_GAPS_KEYWORD = {
    "project_goal": "goal",
    "deliverables": "deliverables",
    "deadline": "deadline",
    "budget": "budget",
    "target_audience": "audience",
    "constraints": "constraint",
}
DocumentLanguage = Literal["en", "ru", "es"]
_GAPS_KEYWORDS_BY_LANGUAGE: dict[DocumentLanguage, dict[str, str]] = {
    "en": _GAPS_KEYWORD,
    "ru": {
        "project_goal": "цель проекта",
        "deliverables": "результат",
        "deadline": "срок",
        "budget": "бюджет",
        "target_audience": "аудитор",
        "constraints": "ограничен",
    },
    "es": {
        "project_goal": "objetivo del proyecto",
        "deliverables": "entregable",
        "deadline": "plazo",
        "budget": "presupuesto",
        "target_audience": "público objetivo",
        "constraints": "restricc",
    },
}
_INTERNAL_FIELD_KEY = re.compile(
    r"\b(?:"
    + "|".join(re.escape(key) for key in (*_GAPS_KEYWORD, "missing_fields"))
    + r")\b",
    re.IGNORECASE,
)
_LITERAL_SPAN = re.compile(
    r"(?<!`)(?P<code>`+)[^\r\n]*?(?<!`)(?P=code)(?!`)"
    r"|(?<!\w)(?P<quote>[\"'])[^\r\n]*?(?P=quote)"
)
_FIELD_LABEL_WORD = r"(?:fields?|поле|поля|полей|campos?)"
# Sentence/line boundaries and masked facts delimit independent assertions.
_ASSERTION = re.compile(r"(?:[^.!?\r\n\0]|[.!?](?!\s|\Z))+")
_FIELD_SEPARATOR = r"[^\w.!?\r\n\0]*"
_TECHNICAL_FIELD_MARKER = re.compile(
    rf"\b(?:{_FIELD_LABEL_WORD}|(?:schema|internal)\b{_FIELD_SEPARATOR}keys?)\b",
    re.IGNORECASE,
)
_KEY_LABELS = re.compile(r"missing fields?\s*:|fields? by name|пропущено поле", re.IGNORECASE)
_FACT_START = re.compile(r"(?:^|\n)[ \t]*(?:(?:[-+*•]|\d+[.)])[ \t]+)?\Z|[.!?][ \t]+\Z")
_FACT_END = re.compile(r"^[ \t]*(?:\Z|[.!?](?:\s|\Z)|\r?\n)")
_TECHNICAL_GAP_SENTENCES = (
    "The {key} field is not present.",
    "Поле {key} не указано.",
    "No se ha indicado el campo {key}.",
)
_CLIENT_FACTS_WITH_COLLIDING_IDENTIFIERS = (
    "Rename target_audience to intended_audience.",
    "Переименовать target_audience в intended_audience.",
    "Renombrar target_audience a intended_audience.",
    "The target_audience database field is missing; restore it.",
    "В базе данных отсутствует поле target_audience; восстановить его.",
    "Falta el campo target_audience en la base de datos; hay que restaurarlo.",
)


def _without_copied_source_facts(text: str, source_facts: tuple[str, ...]) -> str:
    """Exclude complete verbatim source assertions, never identifiers taken out of their context."""
    remaining = list(text)
    for source in source_facts:
        fact = source.strip()
        if not fact:
            continue
        for copied in re.finditer(re.escape(fact), text):
            before, after = text[: copied.start()], text[copied.end() :]
            source_ends_assertion = fact[-1] in ".!?" and (not after or after[0].isspace())
            if _FACT_START.search(before) and (_FACT_END.match(after) or source_ends_assertion):
                # Keep a barrier so adjacent narration cannot inherit words from the copied fact.
                remaining[copied.start() : copied.end()] = ["\0"] * len(fact)
    return "".join(remaining)


def _field_key_leaks(
    text: str, *, source_facts: tuple[str, ...] = (), language: DocumentLanguage = "en"
) -> list[str]:
    """Flag unverified technical assertions; co-occurrence requires review, not semantic proof."""
    # shortcut: only complete verbatim assertions establish provenance; review paraphrases live.
    assert language in _GAPS_KEYWORDS_BY_LANGUAGE, f"unsupported document language: {language}"
    untrusted = _without_copied_source_facts(text, source_facts)
    literal_keys = {
        (literal.start() + key.start(), literal.start() + key.end())
        for literal in _LITERAL_SPAN.finditer(untrusted)
        for key in _INTERNAL_FIELD_KEY.finditer(literal.group())
    }
    # No linker vocabulary: every key in an unverified technical assertion needs review.
    technical_keys = {
        (assertion.start() + key.start(), assertion.start() + key.end())
        for assertion in _ASSERTION.finditer(untrusted)
        if _TECHNICAL_FIELD_MARKER.search(assertion.group())
        for key in _INTERNAL_FIELD_KEY.finditer(assertion.group())
    }
    leaks = _KEY_LABELS.findall(untrusted)
    for match in _INTERNAL_FIELD_KEY.finditer(untrusted):
        if (
            language != "en"
            or "_" in match.group()
            or match.span() in literal_keys
            or match.span() in technical_keys
        ):
            leaks.append(match.group())
    return leaks


@pytest.mark.parametrize(
    "leaky",
    [
        "Missing field: target_audience",
        "Missing fields by name: deliverables",
        "Пропущено поле: target_audience",
        "Missing: project_goal, deliverables, deadline, budget, target_audience, constraints",
        "missing_fields",
        "Missing fields: deliverables",
        "Target_Audience is unspecified",
        "PROJECT_GOAL is missing",
        "MISSING_FIELDS is empty",
    ],
)
def test_field_key_leak_guard_catches_the_qa_strings(leaky: str) -> None:
    assert _field_key_leaks(leaky)


@pytest.mark.parametrize(
    "text",
    [
        "Project goal, deliverables, deadline, budget, target audience "
        "and constraints are missing.",
        "Клиенту нужно уточнить цель проекта, результаты, срок, бюджет, аудиторию и ограничения.",
        "El cliente debe confirmar el objetivo, los entregables, el plazo, el presupuesto, "
        "el público objetivo y las restricciones.",
        "Fix the `reset_password` handler and preserve the `api_v2` route.",
        "The budget's size is unclear.",
    ],
)
def test_field_key_leak_guard_accepts_plain_words(text: str) -> None:
    assert not _field_key_leaks(text)


@pytest.mark.parametrize("identifier", [*_GAPS_KEYWORD, "missing_fields", "PROJECT_GOAL"])
@pytest.mark.parametrize("delimiter", ["", "`", "``", '"', "'"])
def test_field_key_leak_guard_preserves_source_identifiers(
    identifier: str, delimiter: str
) -> None:
    source = f"Preserve the {delimiter}{identifier}{delimiter} database column."
    assert not _field_key_leaks(source, source_facts=(source,))
    assert _field_key_leaks(f"Missing field: {identifier}", source_facts=(source,))
    assert _field_key_leaks(f"The {identifier} field is missing.", source_facts=(source,))


@pytest.mark.parametrize("key", [*_GAPS_KEYWORD, "missing_fields"])
@pytest.mark.parametrize("template", _TECHNICAL_GAP_SENTENCES)
@pytest.mark.parametrize("delimiter", ["", "`", "``", '"', "'"])
def test_all_internal_keys_are_rejected_in_technical_contexts(
    key: str, template: str, delimiter: str
) -> None:
    gap = template.format(key=f"{delimiter}{key}{delimiter}")
    source = f"Rename the {delimiter}{key}{delimiter} database field."
    assert _field_key_leaks(gap)
    assert _field_key_leaks(gap, source_facts=(source,))
    assert len(_field_key_leaks(f"{source} {gap}", source_facts=(source,))) == 1


@pytest.mark.parametrize("source", _CLIENT_FACTS_WITH_COLLIDING_IDENTIFIERS)
def test_complete_client_facts_are_allowed_even_when_they_describe_a_missing_field(
    source: str,
) -> None:
    assert _field_key_leaks(source)
    assert not _field_key_leaks(source, source_facts=(source,))
    assert _field_key_leaks("The target_audience field is missing.", source_facts=(source,))


@pytest.mark.parametrize("key", [key for key in _GAPS_KEYWORD if "_" not in key])
def test_single_word_keys_remain_valid_unformatted_prose(key: str) -> None:
    assert not _field_key_leaks(f"Confirm the {key} with the client.")


@pytest.mark.parametrize("key", [*_GAPS_KEYWORD, "missing_fields"])
def test_source_values_cannot_authorize_new_missing_field_claims(key: str) -> None:
    assert _field_key_leaks(f'The "{key}" field is missing.', source_facts=(key,))


@pytest.mark.parametrize("delimiter", ["`", '"'])
def test_copied_fact_cannot_span_separate_source_values(delimiter: str) -> None:
    assert _field_key_leaks(
        f"{delimiter}budget{delimiter}", source_facts=(f"{delimiter}budget", delimiter)
    )


def test_source_values_cannot_combine_into_a_new_client_fact() -> None:
    assert _field_key_leaks(
        "Rename target_audience to intended_audience.",
        source_facts=("Rename target_audience", "to intended_audience."),
    )


@pytest.mark.parametrize(
    "text",
    [
        "Rename target_audience",
        "  Rename target_audience  ",
        "Rename target_audience.",
        "Project facts. Rename target_audience. Confirm the budget.",
        "The limit is 100. Rename target_audience.",
        "Project facts\nRename target_audience\nConfirm the budget.",
    ],
)
def test_complete_source_facts_use_standalone_statement_boundaries(text: str) -> None:
    assert not _field_key_leaks(text, source_facts=("Rename target_audience",))


@pytest.mark.parametrize(
    "text",
    [
        "Do not Rename target_audience.",
        "Missing: Rename target_audience.",
        "Not requested; Rename target_audience.",
        "Rename target_audience is not requested.",
        "Rename target_audience.id",
        "RENAME target_audience.",
    ],
)
def test_changed_context_is_not_a_copied_source_fact(text: str) -> None:
    assert _field_key_leaks(text, source_facts=("Rename target_audience",))


def test_multiple_facts_and_repeated_copies_do_not_authorize_gap_narration() -> None:
    first = "Rename target_audience."
    second = "Restore the `budget` database column."
    text = f"{first} {second}\n{first} The `budget` field is missing."
    assert _field_key_leaks(text, source_facts=(first, second)) == ["budget"]


@pytest.mark.parametrize(
    "leak",
    ["target_audience", '"target_audience"', "`TARGET_AUDIENCE`", "``target_audience``"],
)
def test_copied_fact_does_not_authorize_another_assertion(leak: str) -> None:
    source = "Preserve the `target_audience` database column."
    assert len(_field_key_leaks(f"{source} {leak} is missing.", source_facts=(source,))) == 1


@pytest.mark.parametrize("literal", ["` budget `", "``\tbudget\t``", '"budget"', "'budget'"])
def test_copied_source_fact_preserves_its_internal_whitespace(literal: str) -> None:
    source = f"Preserve {literal}."
    assert not _field_key_leaks(source, source_facts=(source,))
    assert _field_key_leaks(source, source_facts=("Preserve budget.",))


@pytest.mark.parametrize(
    "literal",
    [
        "`target_audience.id`",
        "`data['budget']`",
        "`data.budget`",
        '"Missing field: budget"',
        "``target_audience = `legacy` ``",
    ],
)
def test_complete_source_facts_preserve_expressions_and_quoted_messages(literal: str) -> None:
    source = f"Preserve {literal}."
    assert _field_key_leaks(source)
    assert not _field_key_leaks(source, source_facts=(source,))
    assert _field_key_leaks(f"{source} target_audience is missing.", source_facts=(source,))


def test_uncopied_source_fact_cannot_change_field_context() -> None:
    text = "field `source_id` budget"
    assert _field_key_leaks(text) == ["budget"]
    assert _field_key_leaks(text, source_facts=("Keep `source_id`.",)) == ["budget"]
    assert not _field_key_leaks(text, source_facts=(text,))


@pytest.mark.parametrize(
    ("source_identifier", "leaked_key"),
    [("target_audience_cache", "target_audience"), ("target_audience", "project_goal")],
)
def test_source_identifier_exemption_only_covers_the_same_whole_key(
    source_identifier: str, leaked_key: str
) -> None:
    assert _field_key_leaks(leaked_key, source_facts=(f"Preserve `{source_identifier}`.",))


def test_summary_prompt_names_gaps_in_words_not_field_keys() -> None:
    """ANY-615: requesting missing fields by name made the model copy raw keys to the reader."""
    prompt = (PRODUCT_DIR / "prompts" / "generate_summary.v1.md").read_text(encoding="utf-8")
    assert "by name" not in prompt
    for key in _GAPS_KEYWORD:
        readable = key.replace("_", " ")
        assert f'`{key}` as "{readable}"' in prompt, key
    assert "internal field keys" in prompt
    assert "language the document is written in" in prompt
    assert "section titles, section content and `summary`" in prompt
    assert "Preserve literal identifiers and code formatting" in prompt
    assert "even when an identifier matches an internal field key" in prompt
    assert "no snake_case identifiers" not in prompt
    assert "no code formatting" not in prompt


def test_summary_prompt_copies_lists_verbatim() -> None:
    """ANY-617: paraphrased lists changed who acts, what rights cover and times. Only `summary`
    is free text; lists, issues and questions are copied verbatim, one per line."""
    prompt = " ".join(
        (PRODUCT_DIR / "prompts" / "generate_summary.v1.md").read_text(encoding="utf-8").split()
    )
    for phrase in (
        'one item per line, each line starting with "- "',
        "Do not merge, split, shorten, reword, reorder, summarize or drop items.",
        "keeps who performs each action",
        "what a right or license covers",
        "a time stays a time and never becomes a date range",
        "Only `summary` is written freely.",
        "every `constraints` item verbatim. List all of them, including exclusions",
        "every `data.issues` `description` verbatim",
        "every `data.questions` `question` verbatim",
        "`summary` is the only free text",
    ):
        assert phrase in prompt, phrase
    assert "in plain sentences" not in prompt
    assert "The questions and their rationales must also use that language" not in prompt


# Words a section may use that carry no project fact. Deliberately per-section: `overview` is
# only allowed to state present facts (generate_summary.v1.md: "do not mention absent ones
# here"), so it gets no words for talking about the brief or missing details -- allowing them
# there once masked an "the brief gives no further detail" violation. `key-details` may label
# fields and say that none were found.
_NON_FACT_WORDS = {
    # ANY-617: overview may label the verbatim target audience in the document language.
    "overview": {
        "lets",
        "that",
        "wants",
        "clien",
        "targe",
        "audie",
        "целев",
        "аудит",
        "públi",
        "objet",
    },
    "key-details": {
        "deliv",
        "deadl",
        "budge",
        "const",
        "rathe",
        "than",
        "brief",
        "found",
        "were",
        # ANY-617: localized group labels (ru, es).
        "резул",
        "срок",
        "бюдже",
        "огран",
        "entre",
        "plazo",
        "presu",
        "restr",
    },
}
# A10 suffix -> (A01 suffix, expected document language).
_SUMMARY_FIXTURES: dict[str, tuple[str, DocumentLanguage]] = {
    "": ("", "en"),
    ".weak_input": (".weak_input", "en"),
    ".no_issues": (".no_issues", "en"),
    ".ru": (".ru", "ru"),
    ".es": (".es", "es"),
}


_MIN_WORD_LEN = 4  # shorter words are articles/prepositions, not facts


def _stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[^\W_]+", text.casefold()) if len(w) >= _MIN_WORD_LEN}


@pytest.mark.parametrize(
    ("summary_suffix", "extract_suffix", "language"),
    [(suffix, *case) for suffix, case in _SUMMARY_FIXTURES.items()],
)
def test_summary_fixtures_obey_the_a10_prompt(
    summary_suffix: str, extract_suffix: str, language: DocumentLanguage
) -> None:
    """generate_summary.v1.md: built from `data` only (never invent facts) and `gaps` names every
    `data.brief.missing_fields` entry. The fixtures are the deterministic evidence for those
    rules, so they are checked against the A01 fixture that feeds the same run (code review:
    the overview named a "bakery" and "new website" that no A01 value carried, and the weak
    fixture never reported `constraints` missing). ANY-615 forbids internal missing-field
    notation in titles, content and summary while preserving identifiers from client facts."""
    gap_keywords = _GAPS_KEYWORDS_BY_LANGUAGE[language]
    assert set(gap_keywords) == {
        f["name"] for f in _literal(_steps()["extract"]["input_mapping"]["fields"])
    }
    brief = _fixture_response("brief_decoder.extract_brief_v1" + extract_suffix)
    document = _fixture_response("brief_decoder.generate_summary_v1" + summary_suffix)
    sections = {s["id"]: s["content"] for s in document["sections"]}

    # Keep complete values separate: joining them could invent a statement the client never made.
    source_facts = tuple(
        item
        for value in brief["values"].values()
        for item in ([value] if isinstance(value, str) else value)
    )
    texts = [
        (f"{section['id']}.{field}", section[field])
        for section in document["sections"]
        for field in ("title", "content")
    ]
    for where, text in [*texts, ("summary", document["summary"])]:
        leaks = _field_key_leaks(text, source_facts=source_facts, language=language)
        assert not leaks, f"{where}: field key leaks {leaks}"

    for section_id, allowed in _NON_FACT_WORDS.items():
        ungrounded = (
            _stems(sections[section_id])
            - _stems(json.dumps(brief["values"], ensure_ascii=False))
            - allowed
        )
        assert not ungrounded, (section_id, sorted(ungrounded))
    for name in brief["missing_fields"]:
        assert gap_keywords[name] in sections["gaps"].casefold(), name

    schema = _load_schema("brief_decoder.decode_output_v1")
    document_schema = {"$defs": schema["$defs"], **schema["properties"]["document"]}
    jsonschema.validators.validator_for(schema)(document_schema).validate(document)


@pytest.mark.parametrize("suffix", _SUMMARY_FIXTURES)
@pytest.mark.parametrize("section_index", range(4))
@pytest.mark.parametrize("title", ["Переведённый заголовок", "Título traducido"])
def test_summary_fixture_rejects_changed_fixed_titles(
    monkeypatch: pytest.MonkeyPatch, suffix: str, section_index: int, title: str
) -> None:
    original = _fixture_response
    stem = "brief_decoder.generate_summary_v1" + suffix
    document = original(stem)
    document["sections"][section_index]["title"] = title
    monkeypatch.setitem(
        globals(), "_fixture_response", lambda name: document if name == stem else original(name)
    )
    with pytest.raises(jsonschema.ValidationError, match="was expected"):
        test_summary_fixtures_obey_the_a10_prompt(suffix, *_SUMMARY_FIXTURES[suffix])


def _list_lines(content: str) -> list[str]:
    return [line[2:] for line in content.splitlines() if line.startswith("- ")]


@pytest.mark.parametrize("summary_suffix", _SUMMARY_FIXTURES)
def test_summary_fixtures_copy_lists_verbatim(summary_suffix: str) -> None:
    """ANY-617: deliverables, every constraint, issue descriptions and questions appear
    verbatim, one per line, in source order; only `summary` is free text."""
    extract_suffix, language = _SUMMARY_FIXTURES[summary_suffix]
    values = _fixture_response("brief_decoder.extract_brief_v1" + extract_suffix)["values"]
    issues = _fixture_response("brief_decoder.detect_issues_v1" + summary_suffix)["issues"]
    questions = (
        []
        if summary_suffix == ".no_issues"
        else _fixture_response("brief_decoder.generate_questions_v1" + summary_suffix)["questions"]
    )
    sections = {
        s["id"]: s["content"]
        for s in _fixture_response("brief_decoder.generate_summary_v1" + summary_suffix)["sections"]
    }

    fields = ("deliverables", "deadline", "budget", "constraints")
    labels = {
        "en": ("Deliverables", "Deadline", "Budget", "Constraints"),
        "ru": ("Результаты", "Срок", "Бюджет", "Ограничения"),
        "es": ("Entregables", "Plazo", "Presupuesto", "Restricciones"),
    }
    expected_lines = []
    for field, label in zip(fields, labels[language], strict=True):
        if field not in values:
            continue
        if field in ("deliverables", "constraints"):
            expected_lines.append(f"{label}:")
            expected_lines.extend(f"- {item}" for item in values[field])
        else:
            expected_lines.append(f"{label}: {values[field]}")
    if not expected_lines:
        assert language == "en"  # The empty-details fixture uses the English fallback.
        expected_lines.append(
            "No deliverables, deadline, budget or constraints were found in the brief."
        )
    assert sections["key-details"] == "\n".join(expected_lines)

    if "project_goal" in values:
        assert sections["overview"].splitlines()[0] == values["project_goal"]
    if "target_audience" in values:
        assert any(
            line.endswith(": " + values["target_audience"])
            for line in sections["overview"].splitlines()
        )
    assert _list_lines(sections["gaps"]) == [issue["description"] for issue in issues]
    assert _list_lines(sections["next-steps"]) == [q["question"] for q in questions]


@pytest.mark.parametrize(
    ("suffix", "section_id", "replacements"),
    [
        ("", "key-details", {"should look modern": "the look should be modern"}),
        (
            ".no_issues",
            "key-details",
            {
                "- checkout goes through a third-party payment processor, "
                "not a custom payment system\n": ""
            },
        ),
        (
            "",
            "next-steps",
            {"the exact date the website needs to be live": "the exact launch date"},
        ),
        ("", "next-steps", {"live?\n- Could": "live? Could"}),
        ("", "key-details", {"- menu page\n- order form": "- order form\n- menu page"}),
        (".no_issues", "key-details", {"2026-11-02": "2026-11-01 – 2026-11-02"}),
        pytest.param(
            ".no_issues",
            "key-details",
            {"Deliverables:": "Constraints:", "Constraints:": "Deliverables:"},
            id="swapped-list-headings",
        ),
        pytest.param(
            ".no_issues",
            "key-details",
            {"Deadline:": "Budget:", "Budget:": "Deadline:"},
            id="swapped-scalar-labels",
        ),
        pytest.param(
            ".no_issues",
            "key-details",
            {"- menu page": "menu page\n- menu page"},
            id="unexpected-non-bullet-line",
        ),
    ],
)
def test_summary_fixture_rejects_changed_source_items(
    monkeypatch: pytest.MonkeyPatch,
    suffix: str,
    section_id: str,
    replacements: dict[str, str],
) -> None:
    original = _fixture_response
    stem = "brief_decoder.generate_summary_v1" + suffix
    document = original(stem)
    section = next(s for s in document["sections"] if s["id"] == section_id)
    assert all(section["content"].count(text) == 1 for text in replacements)
    # Replace simultaneously so swapping labels cannot undo the first substitution.
    section["content"] = re.sub(
        "|".join(map(re.escape, replacements)),
        lambda match: replacements[match[0]],
        section["content"],
    )
    monkeypatch.setitem(
        globals(), "_fixture_response", lambda name: document if name == stem else original(name)
    )
    with pytest.raises(AssertionError):
        test_summary_fixtures_copy_lists_verbatim(suffix)


@pytest.mark.parametrize("suffix", _SUMMARY_FIXTURES)
@pytest.mark.parametrize(
    ("section_index", "field"),
    [(None, "summary"), *[(i, field) for i in range(4) for field in ("title", "content")]],
)
def test_summary_fixture_guard_rejects_leaks_in_every_copied_field(
    monkeypatch: pytest.MonkeyPatch, suffix: str, section_index: int | None, field: str
) -> None:
    original = _fixture_response
    stem = "brief_decoder.generate_summary_v1" + suffix
    document = original(stem)
    target = document if section_index is None else document["sections"][section_index]
    target[field] = "Missing field: target_audience"
    monkeypatch.setitem(
        globals(), "_fixture_response", lambda name: document if name == stem else original(name)
    )
    with pytest.raises(AssertionError, match="field key leaks"):
        test_summary_fixtures_obey_the_a10_prompt(suffix, *_SUMMARY_FIXTURES[suffix])


@pytest.mark.parametrize("delimiter", ["", "`", "``", '"', "'"])
def test_summary_fixture_guard_preserves_identifiers_from_extracted_values(
    monkeypatch: pytest.MonkeyPatch, delimiter: str
) -> None:
    original = _fixture_response
    source = (
        f"Fix the {delimiter}reset_password{delimiter} handler and preserve the "
        f"{delimiter}api_v2{delimiter} and {delimiter}target_audience{delimiter} routes."
    )

    def fixture_response(name: str) -> dict[str, Any]:
        response = original(name)
        if name == "brief_decoder.extract_brief_v1":
            response["values"]["project_goal"] = source
        elif name == "brief_decoder.generate_summary_v1":
            response["sections"][0]["content"] = source
        return response

    monkeypatch.setitem(globals(), "_fixture_response", fixture_response)
    test_summary_fixtures_obey_the_a10_prompt("", "", "en")


@pytest.mark.parametrize("source", _CLIENT_FACTS_WITH_COLLIDING_IDENTIFIERS)
@pytest.mark.parametrize("source_field", ["project_goal", "deliverables"])
def test_summary_fixture_guard_preserves_complete_client_facts(
    monkeypatch: pytest.MonkeyPatch, source: str, source_field: str
) -> None:
    original = _fixture_response

    def fixture_response(name: str) -> dict[str, Any]:
        response = original(name)
        if name == "brief_decoder.extract_brief_v1":
            assert "target_audience" in response["missing_fields"]
            if source_field == "deliverables":
                response["values"][source_field].append(source)
            else:
                response["values"][source_field] = source
        elif name == "brief_decoder.generate_summary_v1":
            response["sections"][0]["content"] = source
        return response

    monkeypatch.setitem(globals(), "_fixture_response", fixture_response)
    test_summary_fixtures_obey_the_a10_prompt("", "", "en")


@pytest.mark.parametrize("key", [key for key in _GAPS_KEYWORD if "_" not in key])
@pytest.mark.parametrize("template", _TECHNICAL_GAP_SENTENCES)
def test_summary_fixture_guard_rejects_code_formatted_single_word_fields(
    monkeypatch: pytest.MonkeyPatch, key: str, template: str
) -> None:
    original = _fixture_response
    stem = "brief_decoder.generate_summary_v1.weak_input"
    document = original(stem)
    document["sections"][2]["content"] += " " + template.format(key=f"`{key}`")
    monkeypatch.setitem(
        globals(), "_fixture_response", lambda name: document if name == stem else original(name)
    )
    with pytest.raises(AssertionError, match="field key leaks"):
        test_summary_fixtures_obey_the_a10_prompt(".weak_input", ".weak_input", "en")


@pytest.mark.parametrize(
    "leak",
    [
        "target_audience is missing.",
        "target_audience не указан.",
        "Falta target_audience.",
        "The `target_audience` field is missing.",
        "Поле `target_audience` не указано.",
        "No se ha indicado el campo `target_audience`.",
    ],
)
def test_source_identifier_does_not_hide_a_still_missing_brief_field(
    monkeypatch: pytest.MonkeyPatch, leak: str
) -> None:
    original = _fixture_response

    def fixture_response(name: str) -> dict[str, Any]:
        response = original(name)
        if name == "brief_decoder.extract_brief_v1":
            assert "target_audience" in response["missing_fields"]
            response["values"]["project_goal"] += " Preserve the `target_audience` database column."
        elif name == "brief_decoder.generate_summary_v1":
            response["sections"][2]["content"] += " " + leak
        return response

    monkeypatch.setitem(globals(), "_fixture_response", fixture_response)
    with pytest.raises(AssertionError, match="field key leaks"):
        test_summary_fixtures_obey_the_a10_prompt("", "", "en")


@pytest.mark.parametrize("key", [key for key in _GAPS_KEYWORD if "_" not in key])
def test_json_quoting_of_extracted_values_cannot_authorize_a_literal(
    monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    original = _fixture_response

    def fixture_response(name: str) -> dict[str, Any]:
        response = original(name)
        if name == "brief_decoder.extract_brief_v1":
            response["values"]["deliverables"].append(key)
        elif name == "brief_decoder.generate_summary_v1":
            response["sections"][2]["content"] += f' The "{key}" field is not present.'
        return response

    monkeypatch.setitem(globals(), "_fixture_response", fixture_response)
    with pytest.raises(AssertionError, match="field key leaks"):
        test_summary_fixtures_obey_the_a10_prompt("", "", "en")


@pytest.mark.parametrize("key", [key for key in _GAPS_KEYWORD if "_" not in key])
@pytest.mark.parametrize("label", ["Missing field", "Не заполнено поле", "Falta el campo"])
@pytest.mark.parametrize("notation", ["({key})", "[{key}]", "= {key}", "- {key}", "«{key}»"])
def test_summary_fixture_rejects_field_labels_across_punctuation(
    monkeypatch: pytest.MonkeyPatch, key: str, label: str, notation: str
) -> None:
    original = _fixture_response
    stem = "brief_decoder.generate_summary_v1.weak_input"
    document = original(stem)
    document["sections"][2]["content"] += " " + label + " " + notation.format(key=key)
    monkeypatch.setitem(
        globals(), "_fixture_response", lambda name: document if name == stem else original(name)
    )
    with pytest.raises(AssertionError, match="field key leaks"):
        test_summary_fixtures_obey_the_a10_prompt(".weak_input", ".weak_input", "en")


@pytest.mark.parametrize("prefix", ["- ", "• ", "* ", "+ ", "1. ", "2) ", "  - ", "\t• "])
@pytest.mark.parametrize("suffix", ["", ".ru", ".es"])
def test_summary_fixture_preserves_deliverables_in_list_items(
    monkeypatch: pytest.MonkeyPatch, prefix: str, suffix: str
) -> None:
    original = _fixture_response
    source = "Rename target_audience to intended_audience."
    extract_suffix, language = _SUMMARY_FIXTURES[suffix]
    extra_gap = ""

    def fixture_response(name: str) -> dict[str, Any]:
        response = original(name)
        if name == "brief_decoder.extract_brief_v1" + extract_suffix:
            response["values"]["deliverables"].append(source)
        elif name == "brief_decoder.generate_summary_v1" + suffix:
            response["sections"][1]["content"] = (
                prefix + source + "\n" + prefix + source + extra_gap
            )
        return response

    monkeypatch.setitem(globals(), "_fixture_response", fixture_response)
    test_summary_fixtures_obey_the_a10_prompt(suffix, extract_suffix, language)
    for separator in (" ", "\n" + prefix):
        extra_gap = separator + "The target_audience field is missing."
        with pytest.raises(AssertionError, match="field key leaks"):
            test_summary_fixtures_obey_the_a10_prompt(suffix, extract_suffix, language)


@pytest.mark.parametrize("prefix", ["Do not - ", "Missing: • ", "Ignore + ", "Exclude 2) "])
def test_inline_list_markers_do_not_authorize_changed_client_facts(prefix: str) -> None:
    source = "Rename target_audience to intended_audience."
    assert _field_key_leaks(prefix + source, source_facts=(source,))


@pytest.mark.parametrize("line_ending", ["\n", "\r\n"])
def test_list_items_without_terminal_punctuation_keep_source_provenance(line_ending: str) -> None:
    source = "Rename target_audience to intended_audience"
    text = "- " + source + line_ending + "1) " + source
    assert not _field_key_leaks(text, source_facts=(source,))
    assert _field_key_leaks(
        text + line_ending + "- target_audience is missing.", source_facts=(source,)
    )


@pytest.mark.parametrize(
    "marker", ["field", "поле", "campo", "field name", "field identifier", "schema key"]
)
@pytest.mark.parametrize("separator", [" (", " [", " = ", " - ", " — ", " «", " / ", " ~ "])
def test_field_marker_punctuation_is_checked_in_both_directions(
    marker: str, separator: str
) -> None:
    assert _field_key_leaks(marker + separator + "budget") == ["budget"]
    assert _field_key_leaks("budget" + separator + marker) == ["budget"]
    source = marker + separator + "budget"
    assert not _field_key_leaks(source, source_facts=(source,))


@pytest.mark.parametrize("separator", [". ", "! ", "? ", "\n", "\r\n"])
@pytest.mark.parametrize("marker", ["field", "field name", "field identifier", "schema key"])
def test_field_labels_cannot_cross_independent_assertions(
    separator: str, marker: str
) -> None:
    assert not _field_key_leaks(marker + separator + "budget")
    assert not _field_key_leaks("budget" + separator + marker)


@pytest.mark.parametrize("suffix", [".weak_input", ".ru", ".es"])
@pytest.mark.parametrize("key", [key for key in _GAPS_KEYWORD if "_" not in key])
@pytest.mark.parametrize(
    "label",
    [
        "field name",
        "field identifier",
        "field label",
        "field key",
        "fields' names",
        "FIELD IDENTIFIERS",
        "schema key",
        "internal keys",
    ],
)
def test_summary_fixture_distinguishes_technical_label_phrases_from_client_facts(
    monkeypatch: pytest.MonkeyPatch, suffix: str, key: str, label: str
) -> None:
    extract_suffix, language = _SUMMARY_FIXTURES[suffix]
    extract_stem = "brief_decoder.extract_brief_v1" + extract_suffix
    summary_stem = "brief_decoder.generate_summary_v1" + suffix
    brief, document = _fixture_response(extract_stem), _fixture_response(summary_stem)
    source = f"The {label} {key} is missing from the database; restore it."
    brief["values"]["project_goal"] = source
    document["sections"][0]["content"] = source
    responses = {extract_stem: brief, summary_stem: document}
    monkeypatch.setitem(globals(), "_fixture_response", responses.__getitem__)
    test_summary_fixtures_obey_the_a10_prompt(suffix, extract_suffix, language)

    document["sections"][2]["content"] += f" Missing {label}: {key}."
    with pytest.raises(AssertionError, match="field key leaks"):
        test_summary_fixtures_obey_the_a10_prompt(suffix, extract_suffix, language)


@pytest.mark.parametrize(
    "text",
    [
        "Confirm the budget with the client.",
        "The name of the project is missing; confirm the budget.",
        "The field name is unknown. Budget needs confirmation.",
        "fieldname budget",
        "schema keyboard budget",
    ],
)
def test_technical_label_phrases_do_not_reject_ordinary_english(text: str) -> None:
    assert not _field_key_leaks(text)


@pytest.mark.parametrize(
    "text",
    [
        "Choose a field name after confirming the budget.",
        "field unrelated budget",
        "budget unrelated field",
        "field namesake budget",
    ],
)
def test_unverified_technical_assertions_require_source_evidence(text: str) -> None:
    # These can be valid prose; the fixture guard cannot establish their meaning without a source.
    assert _field_key_leaks(text) == ["budget"]
    assert not _field_key_leaks(text, source_facts=(text,))


@pytest.mark.parametrize("key", [key for key in _GAPS_KEYWORD if "_" not in key])
@pytest.mark.parametrize(
    "template",
    [
        "Missing field name is {key}.",
        "The missing field would be {key}.",
        "The field was identified as {key}.",
        "The field is commonly referred to as {key}.",
        "The schema key that remains unfilled is {key}.",
        "{key} is the name of the missing field.",
        "{key} has been described as an internal key.",
        "The field which needs clarification, according to the analysis, is {key}.",
        "The missing field in API v1.0 is {key}.",
    ],
)
@pytest.mark.parametrize("suffix", [".weak_input", ".ru", ".es"])
def test_summary_fixture_reviews_technical_assertions_independently_of_linking_words(
    monkeypatch: pytest.MonkeyPatch, key: str, template: str, suffix: str
) -> None:
    extract_suffix, language = _SUMMARY_FIXTURES[suffix]
    extract_stem = "brief_decoder.extract_brief_v1" + extract_suffix
    summary_stem = "brief_decoder.generate_summary_v1" + suffix
    brief, document = _fixture_response(extract_stem), _fixture_response(summary_stem)
    source = template.format(key=key)
    brief["values"]["project_goal"] = source
    document["sections"][0]["content"] = source
    responses = {extract_stem: brief, summary_stem: document}
    monkeypatch.setitem(globals(), "_fixture_response", responses.__getitem__)
    test_summary_fixtures_obey_the_a10_prompt(suffix, extract_suffix, language)

    # A different assertion about the same key cannot inherit the source fact's exemption.
    document["sections"][2]["content"] += " " + source.removesuffix(".") + " in this brief."
    with pytest.raises(AssertionError, match="field key leaks"):
        test_summary_fixtures_obey_the_a10_prompt(suffix, extract_suffix, language)


@pytest.mark.parametrize(
    "text",
    [
        "Missing fields are budget, deadline, deliverables and constraints.",
        "The schema keys would be budget / deadline / deliverables / constraints.",
        "budget, deadline, deliverables and constraints are the missing fields.",
        "The field names are: (budget), [deadline], deliverables & constraints.",
        "Missing fields in API v1.0 are budget, deadline, deliverables and constraints.",
    ],
)
def test_technical_context_covers_every_key_in_an_assertion(text: str) -> None:
    assert _field_key_leaks(text) == ["budget", "deadline", "deliverables", "constraints"]
    assert not _field_key_leaks(text, source_facts=(text,))


@pytest.mark.parametrize(
    ("section_index", "field"),
    [(None, "summary"), *[(i, field) for i in range(4) for field in ("title", "content")]],
)
def test_linked_field_name_is_rejected_in_every_copied_location(
    monkeypatch: pytest.MonkeyPatch, section_index: int | None, field: str
) -> None:
    original = _fixture_response
    stem = "brief_decoder.generate_summary_v1.weak_input"
    document = original(stem)
    target = document if section_index is None else document["sections"][section_index]
    target[field] += " Missing field name is budget."
    monkeypatch.setitem(
        globals(), "_fixture_response", lambda name: document if name == stem else original(name)
    )
    with pytest.raises(AssertionError, match="field key leaks"):
        test_summary_fixtures_obey_the_a10_prompt(".weak_input", ".weak_input", "en")


@pytest.mark.parametrize("key", [key for key in _GAPS_KEYWORD if "_" not in key])
@pytest.mark.parametrize(("suffix", "prefix"), [(".ru", "Не указан "), (".es", "Falta ")])
@pytest.mark.parametrize(
    ("section_index", "field"),
    [(None, "summary"), *[(i, field) for i in range(4) for field in ("title", "content")]],
)
def test_localized_fixtures_reject_untranslated_keys_but_preserve_client_facts(
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    suffix: str,
    prefix: str,
    section_index: int | None,
    field: str,
) -> None:
    original = _fixture_response
    extract_suffix, language = _SUMMARY_FIXTURES[suffix]
    extract_stem = "brief_decoder.extract_brief_v1" + extract_suffix
    summary_stem = "brief_decoder.generate_summary_v1" + suffix
    brief, document = original(extract_stem), original(summary_stem)
    source = f"The {key} database field is missing; restore it."
    brief["values"]["deliverables"].append(source)
    document["sections"][1]["content"] += "\n- " + source
    responses = {extract_stem: brief, summary_stem: document}
    monkeypatch.setitem(globals(), "_fixture_response", responses.__getitem__)
    test_summary_fixtures_obey_the_a10_prompt(suffix, extract_suffix, language)

    target = document if section_index is None else document["sections"][section_index]
    target[field] += " " + prefix + key + "."
    with pytest.raises(AssertionError, match="field key leaks"):
        test_summary_fixtures_obey_the_a10_prompt(suffix, extract_suffix, language)


@pytest.mark.parametrize("suffix", [".weak_input", ".ru", ".es"])
def test_fixture_completeness_requires_gap_words_in_the_declared_language(
    monkeypatch: pytest.MonkeyPatch, suffix: str
) -> None:
    original = _fixture_response
    extract_suffix, language = _SUMMARY_FIXTURES[suffix]
    brief = original("brief_decoder.extract_brief_v1" + extract_suffix)
    stem = "brief_decoder.generate_summary_v1" + suffix
    for key in brief["missing_fields"]:
        document = original(stem)
        gap = document["sections"][2]
        keyword = _GAPS_KEYWORDS_BY_LANGUAGE[language][key]
        gap["content"] = re.sub(re.escape(keyword), "…", gap["content"], flags=re.IGNORECASE)
        monkeypatch.setitem(
            globals(),
            "_fixture_response",
            lambda name, document=document: document if name == stem else original(name),
        )
        with pytest.raises(AssertionError, match=key):
            test_summary_fixtures_obey_the_a10_prompt(suffix, extract_suffix, language)


@pytest.mark.parametrize(
    ("suffix", "goal_gap"),
    [
        (".ru", "Цель проекта не определена."),
        (".es", "El objetivo del proyecto no está definido."),
    ],
)
def test_localized_audience_gap_cannot_cover_a_missing_project_goal(
    monkeypatch: pytest.MonkeyPatch, suffix: str, goal_gap: str
) -> None:
    extract_suffix, language = _SUMMARY_FIXTURES[suffix]
    extract_stem = "brief_decoder.extract_brief_v1" + extract_suffix
    summary_stem = "brief_decoder.generate_summary_v1" + suffix
    brief, document = _fixture_response(extract_stem), _fixture_response(summary_stem)
    del brief["values"]["project_goal"]
    del brief["confidence"]["project_goal"]
    brief["missing_fields"].append("project_goal")
    document["sections"][0]["content"] = brief["values"]["deliverables"][0]
    responses = {extract_stem: brief, summary_stem: document}
    monkeypatch.setitem(globals(), "_fixture_response", responses.__getitem__)
    with pytest.raises(AssertionError, match="project_goal"):
        test_summary_fixtures_obey_the_a10_prompt(suffix, extract_suffix, language)
    document["sections"][2]["content"] += " " + goal_gap
    test_summary_fixtures_obey_the_a10_prompt(suffix, extract_suffix, language)


@pytest.mark.parametrize(
    ("suffix", "invented"), [(".ru", "Неподтверждённый факт."), (".es", "Afirmación inventada.")]
)
def test_localized_fixture_grounding_checks_unicode_words(
    monkeypatch: pytest.MonkeyPatch, suffix: str, invented: str
) -> None:
    original = _fixture_response
    stem = "brief_decoder.generate_summary_v1" + suffix
    document = original(stem)
    document["sections"][0]["content"] += " " + invented
    monkeypatch.setitem(
        globals(), "_fixture_response", lambda name: document if name == stem else original(name)
    )
    with pytest.raises(AssertionError, match="overview"):
        test_summary_fixtures_obey_the_a10_prompt(suffix, *_SUMMARY_FIXTURES[suffix])


def test_field_key_guard_rejects_unknown_document_languages() -> None:
    with pytest.raises(AssertionError, match="unsupported document language"):
        _field_key_leaks("Confirm the budget.", language="de")  # type: ignore[arg-type]


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
    # every output field is either a rendered part or explicitly excluded (brief_text is the
    # verbatim input echoed for the handoff, never rendered)
    assert contract["excluded_fields"] == ["brief_text"]
    assert {part["field"] for part in contract["parts"]} | set(contract["excluded_fields"]) == set(
        output_schema["properties"]
    )
    # The model-written document must never be the copy authority (ANY-616).
    assert "canonical_field" not in contract
    copy_text = contract["copy_text"]
    assert copy_text["authority"] == "structured_fields_only"
    assert copy_text["sources"] == ["brief.values", "brief.missing_fields", "issues", "questions"]
    assert copy_text["not_copyable_fields"] == ["document", "brief.confidence"]
    for source in copy_text["sources"]:
        head, *rest = source.split(".")
        node = output_schema["properties"][head]
        for key in rest:
            node = node["properties"][key]
    assert contract["canonical_field_composition"].strip()
    assert "never from `document`" in contract["canonical_field_composition"]

    # Code review finding (me #2): the `clarifying_questions` part used to describe an empty
    # `questions` list as "no clarification needed" -- a readiness claim that contradicts
    # generate_summary.v1.md's own rule (empty `questions` alone never implies the brief is
    # ready) and the deterministic `.no_issues` fixture, which pairs empty `questions` with a
    # not-ready summary.
    (questions_part,) = (
        part for part in contract["parts"] if part["part_id"] == "clarifying_questions"
    )
    assert "no clarification needed" not in questions_part["description"].lower()


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


def test_handoff_route_is_allowlisted_declarative_and_leak_free() -> None:
    """ANY-26: the Brief Decoder -> Acceptance Builder route maps only always-present paths."""
    (route,) = _test_support.load_yaml(PRODUCT_DIR, "handoffs.yaml")["handoffs"]
    acceptance_dir = PRODUCT_DIR.parent / "acceptance_builder"
    target = _test_support.load_yaml(acceptance_dir, "scenarios.yaml")["scenarios"]
    frontends = _test_support.load_yaml(acceptance_dir, "frontends.yaml")["frontends"]

    assert route["source_scenario_id"] == WORKFLOW_ID
    assert route["target_scenario_id"] in {s["scenario_id"] for s in target}
    assert route["target_frontend_id"] in {f["frontend_id"] for f in frontends if f["enabled"]}
    assert (route["target_start_policy"], route["consent_required"]) == ("immediate", True)
    assert route["context_mapping"] == {"brief_text": "artifact.content_json.brief_text"}
    # preview_mapping: direct artifact paths only -- no literals, no optional brief.values.*
    assert set(route["preview_mapping"].values()) == {
        "artifact.content_json.document.summary",
        "artifact.content_json.brief.missing_fields",
    }
    # `continue_to_target` is deliberately not advertised: the target may be disabled in a
    # supported deployment, and the web handoff journey belongs to ANY-244.
    scenarios = _test_support.load_yaml(PRODUCT_DIR, "scenarios.yaml")["scenarios"]
    assert scenarios[0]["allowed_next_actions"] == ["copy_result"]


def test_changed_output_contract_carries_a_bumped_version() -> None:
    """ANY-26: `brief_text` became a required workflow-output field, so the workflow and the
    output schema are no longer the v1 definitions already persisted by earlier jobs/artifacts
    (job.workflow_version / artifact schema_version drift guards). The input schema and the
    scenario (whose advertised next actions are unchanged) stay at v1."""
    versions = {s["schema_ref"]: s["version"] for s in _test_support.load_yaml(PRODUCT_DIR, "schemas.yaml")["schemas"]}
    assert versions == {"brief_decoder.decode_input_v1": 1, "brief_decoder.decode_output_v1": 2}
    assert _workflow()["version"] == 2
    (scenario,) = _test_support.load_yaml(PRODUCT_DIR, "scenarios.yaml")["scenarios"]
    assert scenario["version"] == 1


def test_handoff_brief_text_is_the_verbatim_input_and_never_looser_than_the_target() -> None:
    """ANY-26 review: the handoff source is the caller's brief passed through untouched, so its
    output schema must equal the decode input's and the target's `brief_text` (a valid decode can
    never fail handoff creation), and the workflow must copy `scenario.input.brief_text`."""
    schemas = PRODUCT_DIR / "schemas"
    source = json.loads((schemas / "decode_output.schema.json").read_text())
    decode_input = json.loads((schemas / "decode_input.schema.json").read_text())
    target_dir = PRODUCT_DIR.parent / "acceptance_builder" / "schemas"
    target = json.loads((target_dir / "draft_input.schema.json").read_text())
    brief_text = source["properties"]["brief_text"]
    assert "brief_text" in source["required"]
    assert brief_text == decode_input["properties"]["brief_text"]
    assert brief_text == target["properties"]["brief_text"]
    steps = _workflow()["steps"]
    passthrough = [s["output_mapping"].get("context.workflow_output.brief_text") for s in steps]
    assert passthrough.count("scenario.input.brief_text") == 1

    validator = jsonschema.validators.validator_for(brief_text)(brief_text)
    assert validator.is_valid("x" * 8000)
    assert validator.is_valid("a\n\nb")
    for bad in ("x" * 8001, " a", "a ", "\na", "a\n", ""):
        assert not validator.is_valid(bad), repr(bad)
