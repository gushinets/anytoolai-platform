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
    for pattern in _READINESS_CLAUSES[language]:
        match = re.fullmatch(pattern, clause.strip())
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
