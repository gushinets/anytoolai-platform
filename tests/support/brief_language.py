"""Authored language fixtures: pipeline evidence, never a claim about live model behavior."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/brief_language_eval"
CASES = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))["cases"]
CANONICAL = json.loads((FIXTURES / "canonical.json").read_text(encoding="utf-8"))

DocumentLanguage = Literal["en", "ru", "es"]

# Fixture verdicts use a closed set of subjects and predicates. Only a named subject
# can establish a verdict inside a clause; an omitted subject must start the clause.
_READINESS_CLAUSES = {
    "en": (
        (
            r"the (?:brief|request) is ",
            r"(?P<negative>not (?:yet |fully )?)?ready to start(?: work)?",
        ),
    ),
    "ru": ((r"(?:бриф|запрос) ", r"(?:пока )?(?P<negative>не )?готов к (?:работе|началу работы)"),),
    "es": tuple(
        (subject + " ", rf"(?:(?:aún|todavía) )?(?P<negative>no )?está {adjective} para empezar")
        for subject, adjective in (("el encargo", "listo"), ("la solicitud", "lista"))
    ),
}

# An explicitly conditional or interrogative complement does not assert its contents.
_CONDITION = {"en": r"if|when|once", "ru": r"если|когда", "es": r"si|cuando"}
_COORDINATORS = {"en": {"and", "or"}, "ru": {"и", "или", "либо", "а"}, "es": {"y", "o"}}
_STATEMENT_END = re.compile(r"[.!?;:—–]|\b(?:but|pero|но)\b")


def _fixture_verdicts(clause: str, language: DocumentLanguage, *, opening: bool) -> Iterator[bool]:
    clause = clause.strip()
    introducer = _CONDITION[language] + (r"|whether" if language == "en" else "")
    for subject, predicate in _READINESS_CLAUSES[language]:
        if opening:
            match = re.fullmatch(subject + predicate, clause)
            if match:
                yield match["negative"] is None
        else:
            named = rf"(?:{subject}|it is )" if language == "en" else subject
            for match in re.finditer(rf"(?:\b{named}|^){predicate}(?=\s|$)", clause):
                if not re.search(rf"\b(?:{introducer})\s+$", clause[: match.start()]):
                    yield match["negative"] is None


def _asserted_clauses(statement: str, language: DocumentLanguage) -> Iterator[str]:
    # A chain of prerequisites governs one consequence in the authored fixtures.
    awaiting_consequence = False
    *prefixes, last = statement.split(",")
    for part in prefixes:
        clause = part.strip()
        if not clause:
            continue
        first, _, rest = clause.partition(" ")
        condition_text = rest if first in _COORDINATORS[language] else clause
        discourse_marker = condition_text in {"once again", "once more", "if anything"}
        if not discourse_marker and re.match(rf"(?:{_CONDITION[language]})\b", condition_text):
            awaiting_consequence = True
        elif awaiting_consequence:
            awaiting_consequence = False
        else:
            yield clause
    if not awaiting_consequence:
        yield last


def assert_summary_readiness(
    summary: str,
    language: DocumentLanguage,
    *,
    issues: list[dict[str, Any]],
    missing_fields: list[str],
    questions: list[dict[str, Any]],
) -> None:
    expected_ready = not (issues or missing_fields or questions)
    normalized = " ".join(summary.casefold().split())
    first_statement, *explanation = _STATEMENT_END.split(normalized)
    first, _, continuation = first_statement.partition(",")
    opening = next(_fixture_verdicts(first, language, opening=True), None)
    assert opening is expected_ready, f"Expected opening readiness={expected_ready}: {summary!r}"
    rest = {
        verdict
        for statement in (continuation, *explanation)
        for clause in _asserted_clauses(statement, language)
        for verdict in _fixture_verdicts(clause, language, opening=False)
    }
    assert (not expected_ready) not in rest, f"Conflicting readiness verdicts: {summary!r}"


_EMPTY_OVERVIEW = {
    "en": "The brief does not state what the client wants.",
    "ru": "В брифе не указано, что хочет получить клиент.",
    "es": "La solicitud no indica qué quiere obtener el cliente.",
}

_EMPTY_DETAILS = {
    "en": "No deliverables, deadline, budget or constraints were found in the brief.",
    "ru": "Конкретные результаты работы, сроки, бюджет и ограничения не указаны.",
    "es": "No se indican entregables concretos, plazo, presupuesto ni restricciones.",
}

_EMPTY_GAPS = {
    "en": "No issues were found in the brief, and nothing requested is missing.",
    "ru": "Бриф полон, все необходимые сведения указаны.",
    "es": "La solicitud está completa y contiene toda la información necesaria.",
}

_EMPTY_QUESTIONS = {
    "en": "No clarifying questions were generated for this brief.",
    "ru": "Уточняющих вопросов по брифу нет.",
    "es": "No se generaron preguntas aclaratorias para esta solicitud.",
}

# Inflected field names for the confirmation sentence in the authored fixtures.
_MISSING_NAMES = {
    "en": {
        "project_goal": "project goal",
        "target_audience": "target audience",
        "deliverables": "deliverables",
        "deadline": "deadline",
        "budget": "budget",
        "constraints": "constraints",
    },
    "ru": {
        "project_goal": "цель проекта",
        "target_audience": "целевую аудиторию",
        "deliverables": "результаты работы",
        "deadline": "срок",
        "budget": "бюджет",
        "constraints": "ограничения",
    },
    "es": {
        "project_goal": "el objetivo del proyecto",
        "target_audience": "el público objetivo",
        "deliverables": "los entregables",
        "deadline": "el plazo",
        "budget": "el presupuesto",
        "constraints": "las restricciones",
    },
}


def _missing_confirmation(missing_fields: list[str], language: DocumentLanguage) -> str:
    # Only the set of missing facts matters. The authored sentence uses template field order.
    order = ("project_goal", "deliverables", "deadline", "budget", "target_audience", "constraints")
    names = [_MISSING_NAMES[language][field] for field in sorted(missing_fields, key=order.index)]
    phrase = names[-1]
    if len(names) > 1:
        conjunction = {"en": " and ", "ru": " и ", "es": " y "}[language]
        phrase = ", ".join(names[:-1]) + conjunction + phrase
    if language == "ru":
        return f"Клиенту нужно уточнить {phrase}."
    if language == "es":
        return f"El cliente debe confirmar {phrase}."
    if len(names) == 1:
        plural = missing_fields[0] in {"deliverables", "constraints"}
        verb, pronoun = ("are", "them") if plural else ("is", "it")
        return f"The {phrase} {verb} not stated; the client should confirm {pronoun}."
    return f"{phrase.capitalize()} are missing; the client should confirm them."


def labeled_brief_value(field: str, value: str, language: DocumentLanguage) -> str:
    labels = {
        "target_audience": {
            "en": "Target audience",
            "ru": "Целевая аудитория",
            "es": "Público objetivo",
        },
        "deadline": {"en": "Deadline", "ru": "Срок", "es": "Plazo"},
        "budget": {"en": "Budget", "ru": "Бюджет", "es": "Presupuesto"},
    }
    return f"{labels[field][language]}: {value}"


def assert_brief_overview(content: str, values: dict[str, Any], language: DocumentLanguage) -> None:
    lines = [values["project_goal"]] if "project_goal" in values else []
    if "target_audience" in values:
        lines.append(labeled_brief_value("target_audience", values["target_audience"], language))
    if not lines:
        lines.append(_EMPTY_OVERVIEW[language])
    assert content == "\n".join(lines), "overview"


def assert_summary_matches_sources(
    document: dict[str, Any],
    brief: dict[str, Any],
    issues: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    language: DocumentLanguage,
) -> None:
    """Check authored A10 fixtures against the structured inputs of the same run."""
    values = brief["values"]
    missing = brief["missing_fields"]
    assert_summary_readiness(
        document["summary"], language, issues=issues, missing_fields=missing, questions=questions
    )
    for records, key in ((issues, "description"), (questions, "question")):
        if records:
            assert not all(record[key] in document["summary"] for record in records), (
                f"summary repeats the full {key} list"
            )
    sections = document["sections"]
    assert [s["id"] for s in sections] == ["overview", "key-details", "gaps", "next-steps"]
    overview, details, gaps, next_steps = (s["content"] for s in sections)
    assert_brief_overview(overview, values, language)

    group_labels = {
        "deliverables": {"en": "Deliverables", "ru": "Результаты", "es": "Entregables"},
        "constraints": {"en": "Constraints", "ru": "Ограничения", "es": "Restricciones"},
    }
    detail_lines = []
    for field in ("deliverables", "deadline", "budget", "constraints"):
        if field not in values:
            continue
        if field in group_labels:
            detail_lines.append(f"{group_labels[field][language]}:")
            detail_lines.extend(f"- {item}" for item in values[field])
        else:
            detail_lines.append(labeled_brief_value(field, values[field], language))
    if not detail_lines:
        detail_lines.append(_EMPTY_DETAILS[language])
    assert details == "\n".join(detail_lines), "key-details"

    gap_lines = [f"- {issue['description']}" for issue in issues]
    if missing:
        gap_lines.append(_missing_confirmation(missing, language))
    elif not issues:
        gap_lines.append(_EMPTY_GAPS[language])
    assert gaps == "\n".join(gap_lines), "gaps"

    question_lines = [f"- {question['question']}" for question in questions]
    if not questions:
        question_lines.append(_EMPTY_QUESTIONS[language])
    assert next_steps == "\n".join(question_lines), "next-steps"


def golden_cases(product: str) -> list[dict[str, Any]]:
    return [
        case
        for case in CASES
        if case["id"] in CANONICAL and case["scenario_id"].startswith(product + ".")
    ]


def write_provider_fixtures(directory: Path, case: dict[str, Any]) -> dict[str, Any]:
    output = CANONICAL[case["id"]]
    scenario = case["scenario_id"]
    if scenario == "brief_decoder.decode_v1":
        actions = {
            "brief_decoder.extract_brief_v1": output["brief"],
            "brief_decoder.detect_issues_v1": {"issues": output["issues"]},
            "brief_decoder.generate_questions_v1": {"questions": output["questions"]},
            "brief_decoder.generate_summary_v1": output["document"],
        }
    else:
        actions = {
            "acceptance_builder.extract_v1": output["extracted"],
        }
        if scenario == "acceptance_builder.check_v1":
            actions["acceptance_builder.compare_v1"] = output["comparison"]
    for action, response in actions.items():
        (directory / f"{action}.json").write_text(
            json.dumps({"response_json": response}, ensure_ascii=False), encoding="utf-8"
        )
    return output
