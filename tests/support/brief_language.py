"""Authored language fixtures: pipeline evidence, never a claim about live model behavior."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/brief_language_eval"
CASES = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))["cases"]
CANONICAL = json.loads((FIXTURES / "canonical.json").read_text(encoding="utf-8"))

DocumentLanguage = Literal["en", "ru", "es"]

# Authored fixtures open with a verdict about the brief. Keep each subject paired with
# its grammatical predicate; the following explanation is independently worded.
_READINESS_CLAUSES = {
    "en": (
        r"(?:(?P<subject>the (?:brief|request) is )|it is )?"
        r"(?P<negative>not (?:yet |fully )?)?ready to start(?: work)?",
    ),
    "ru": (
        r"(?:(?P<subject>бриф|запрос) )?(?:пока )?"
        r"(?P<negative>не )?готов к (?:работе|началу работы)",
    ),
    "es": tuple(
        rf"(?:(?P<subject>{subject}) )?(?:(?:aún|todavía) )?"
        rf"(?P<negative>no )?está {adjective} para empezar"
        for subject, adjective in (("el encargo", "listo"), ("la solicitud", "lista"))
    ),
}


def _fixture_verdict(clause: str, language: DocumentLanguage, *, opening: bool) -> bool | None:
    # The opening is a complete verdict; later assertions may carry a trailing qualifier.
    end = r"\Z" if opening else r"(?=\s|\Z)"
    for pattern in _READINESS_CLAUSES[language]:
        match = re.match(pattern + end, clause.strip())
        if match and (not opening or match["subject"]):
            return match["negative"] is None
    return None


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
    first, *explanation = re.split(r"[.,;:—–]|\b(?:but|pero|но)\b", normalized)
    opening = _fixture_verdict(first, language, opening=True)
    assert opening is expected_ready, f"Expected opening readiness={expected_ready}: {summary!r}"
    rest = {_fixture_verdict(clause, language, opening=False) for clause in explanation}
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


def assert_brief_overview(content: str, values: dict[str, Any], language: DocumentLanguage) -> None:
    labels = {"en": "Target audience", "ru": "Целевая аудитория", "es": "Público objetivo"}
    lines = [values["project_goal"]] if "project_goal" in values else []
    if "target_audience" in values:
        lines.append(f"{labels[language]}: {values['target_audience']}")
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
    sections = document["sections"]
    assert [s["id"] for s in sections] == ["overview", "key-details", "gaps", "next-steps"]
    overview, details, gaps, next_steps = (s["content"] for s in sections)
    assert_brief_overview(overview, values, language)

    fields = ("deliverables", "deadline", "budget", "constraints")
    labels = {
        "en": ("Deliverables", "Deadline", "Budget", "Constraints"),
        "ru": ("Результаты", "Срок", "Бюджет", "Ограничения"),
        "es": ("Entregables", "Plazo", "Presupuesto", "Restricciones"),
    }
    detail_lines = []
    for field, label in zip(fields, labels[language], strict=True):
        if field not in values:
            continue
        if field in ("deliverables", "constraints"):
            detail_lines.append(f"{label}:")
            detail_lines.extend(f"- {item}" for item in values[field])
        else:
            detail_lines.append(f"{label}: {values[field]}")
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
