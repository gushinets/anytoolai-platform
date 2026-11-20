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
# Continuative aspect modifies the predicate; the negative group determines polarity.
_EN_STILL = r"(?:still )?"
_EN_COPULA = rf"(?: {_EN_STILL}is |['’]s )"
_RU_ASPECT = r"(?:(?:пока|(?:вс[её] )?ещ[её]|по[-‑]прежнему|до сих пор) )?"
_ES_ASPECT = r"(?:(?:aún|todavía) )?"
_READINESS_CLAUSES = {
    "en": (
        (
            r"the (?:brief|request)" + _EN_COPULA,
            rf"{_EN_STILL}(?P<negative>not {_EN_STILL}(?:yet |fully )?)?ready to start(?: work)?",
        ),
    ),
    "ru": (
        (r"(?:бриф|запрос) ", _RU_ASPECT + r"(?P<negative>не )?готов к (?:работе|началу работы)"),
    ),
    "es": tuple(
        (subject + " ", rf"{_ES_ASPECT}{verb}{_ES_ASPECT}{adjective} para empezar")
        for subject, adjective in (("el encargo", "listo"), ("la solicitud", "lista"))
        for verb in (
            r"(?P<negative>no )?está ",
            r"sigue (?:(?P<negative>sin estar )|(?:estando )?)",
        )
    ),
}

# A prerequisite can be a clause ("once the client signs") or a time phrase
# ("after sign-off"). The focus particle is optional in either construction.
_CONDITION = {
    "en": r"(?:only )?(?:if|when|once|after|subject to)",
    "ru": r"(?:(?:только|лишь) )?(?:если|когда|после|при условии)",
    "es": r"(?:(?:s[oó]lo|solamente|únicamente) )?(?:si|cuando|después de|tras|a condición de)",
}
_COORDINATORS = {"en": {"and", "or"}, "ru": {"и", "или", "либо", "а"}, "es": {"y", "o"}}
_CONTRAST = r"\b(?:but|pero|но)\b"
_STATEMENT_END = re.compile(r"[.!?;]|" + _CONTRAST)
# These separators can connect a predicate to a qualification on either side.
_CLAUSE_END = re.compile(r"[,:—–]")
_INDEPENDENT_PREFIX = {
    "en": r"(?:however|in any case)\b",
    "ru": r"(?:однако|в любом случае)\b",
    "es": r"(?:sin embargo|en cualquier caso)\b",
}


def _starts_condition(condition: str, language: DocumentLanguage) -> bool:
    if condition in {"once again", "once more", "if anything", "after all", "después de todo"}:
        return False
    return bool(re.match(rf"(?:{_CONDITION[language]})\s+\S", condition))


def _joins_condition(clause: str, language: DocumentLanguage) -> bool:
    conjunction, _, condition = clause.partition(" ")
    return conjunction in _COORDINATORS[language] and _starts_condition(condition, language)


def _verdict_matches(
    clause: str, language: DocumentLanguage, *, opening: bool
) -> Iterator[re.Match[str]]:
    introducer = _CONDITION[language] + (r"|whether" if language == "en" else "")
    for subject, predicate in _READINESS_CLAUSES[language]:
        if opening:
            match = re.fullmatch(subject + predicate, clause)
            if match:
                yield match
        else:
            named = rf"(?:{subject}|it{_EN_COPULA})" if language == "en" else subject
            for match in re.finditer(rf"(?:\b{named}|^){predicate}(?=\s|$)", clause):
                if not re.search(rf"\b(?:{introducer})\s+$", clause[: match.start()]):
                    yield match


def _consequence_index(clauses: list[str], start: int, language: DocumentLanguage) -> int | None:
    """Find the consequence shared by the condition at start and its alternatives."""
    for index in range(start + 1, len(clauses)):
        clause = clauses[index]
        first, _, rest = clause.partition(" ")
        joined = first in _COORDINATORS[language]
        if re.match(_INDEPENDENT_PREFIX[language], rest if joined else clause):
            break
        if joined:
            # A coordinated prerequisite may omit the repeated "if".
            continue
        if not _starts_condition(clause, language) or any(
            _verdict_matches(clause, language, opening=False)
        ):
            return index
    return None


def _statement_verdicts(statement: str, language: DocumentLanguage) -> Iterator[bool]:
    if language == "ru":
        # The internal comma in a compound conjunction does not start a consequence.
        statement = re.sub(
            r"(?<=\bпри условии),\s*(?=что\b)|(?<=\bпосле того),\s*(?=как\b)", " ", statement
        )
    parts = [part.strip() for part in _CLAUSE_END.split(statement) if part.strip()]
    index = 0
    while index < len(parts):
        clause = parts[index]
        index += 1
        conditional = _starts_condition(clause, language) or _joins_condition(clause, language)
        if conditional:
            consequence = _consequence_index(parts, index - 1, language)
            if consequence is not None:
                index = consequence + 1
            continue
        for match in _verdict_matches(clause, language, opening=False):
            suffix = clause[match.end() :].strip()
            if (
                not suffix
                and index < len(parts)
                and _starts_condition(parts[index], language)
                and _consequence_index(parts, index, language) is None
            ):
                # A detached qualifier belongs to this verdict only if it does
                # not introduce its own consequence to the right.
                suffix = parts[index]
                index += 1
            if _starts_condition(suffix, language):
                while index < len(parts) and _joins_condition(parts[index], language):
                    index += 1
            else:
                yield match["negative"] is None


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
    if language == "en":
        normalized = re.sub(r"\bisn['’]t\b", "is not", normalized)
    # A fixture must establish current readiness before its free-form explanation.
    boundary = re.search(r"[.!](?=\s|$)", normalized)
    assert boundary, f"Expected a separate opening readiness sentence: {summary!r}"
    opening = next(_verdict_matches(normalized[:boundary.start()], language, opening=True), None)
    assert opening and (opening["negative"] is None) == expected_ready, (
        f"Expected opening readiness={expected_ready}: {summary!r}"
    )
    # A contrast can introduce a trailing condition on a later assertion.
    explanation = normalized[boundary.end():]
    explanation = re.sub(rf"{_CONTRAST}(?= (?:{_CONDITION[language]})\s+\S)", ":", explanation)
    for statement in _STATEMENT_END.split(explanation):
        verdicts = _statement_verdicts(statement, language)
        assert (not expected_ready) not in verdicts, f"Conflicting readiness verdicts: {summary!r}"


_EMPTY_OVERVIEW = {
    "en": "The brief does not state what the client wants.",
    "ru": "В брифе не указано, что хочет получить клиент.",
    "es": "La solicitud no indica qué quiere obtener el cliente.",
}

BRIEF_DETAIL_FIELDS = ("deliverables", "deadline", "budget", "constraints")
EMPTY_BRIEF_DETAILS = {
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
    for field in BRIEF_DETAIL_FIELDS:
        if field not in values:
            continue
        if field in group_labels:
            detail_lines.append(f"{group_labels[field][language]}:")
            detail_lines.extend(f"- {item}" for item in values[field])
        else:
            detail_lines.append(labeled_brief_value(field, values[field], language))
    if not detail_lines:
        detail_lines.append(EMPTY_BRIEF_DETAILS[language])
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
