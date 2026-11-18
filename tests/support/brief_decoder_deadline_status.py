"""Bounded output oracle for the seven ANY-762 cases, not a natural-language classifier.

Clause checks preserve required facts; independent fingerprints cover every copied text field.
New document wording or layout requires review, even when it is semantically correct.
"""

import hashlib
import json
import re
from pathlib import Path

_REVIEWED_DOCUMENTS = json.loads(
    (
        Path(__file__).resolve().parents[1] / "fixtures/brief_decoder_eval/reviewed_documents.json"
    ).read_text(encoding="utf-8")
)["document_sha256"]

_NO_FINAL_ESTIMATE = (
    r"(?:окончательную оценку исполнитель еще не давал|"
    r"исполнитель еще не подтвердил окончательную оценку|"
    r"окончательная оценка исполнителем еще не дана)"
)
_DESIGNS_READY = r"макеты будут готовы к 1 декабря"
_RU_YEAR = r"(?: год не указан)?"
_EN_YEAR = r"(?: the year is (?:not specified|unspecified))?"

# Full clauses bind each status to its value and each conditional date to its event.
_CLAUSES = {
    "BD-RU-05": (
        r"(?:срок )?желаемый срок клиента 10 дней "
        + _NO_FINAL_ESTIMATE
        + r"(?: поэтому срок не согласован)?"
    ),
    "BD-EN-PREFERRED": (
        r"(?:deadline )?(?:the )?preferred schedule (?:is |of )?"
        r"three weeks from kickoff with launch by december 10"
        r"(?: the kickoff date and (?:launch )?year are (?:not specified|unspecified))?"
    ),
    "BD-RU-CONDITIONAL": (
        r"(?:(?:срок (?:запуска )?указан условно )?если "
        + _DESIGNS_READY
        + r" запуск (?:планируется на )?15 декабря|"
        r"(?:срок )?запуск (?:запланирован на )?15 декабря (?:если |при условии что )"
        + _DESIGNS_READY
        + r")"
        + _RU_YEAR
    ),
    "BD-ES-TENTATIVE": (
        r"plazo (?:tentativo (?:de )?unas cuatro semanas|unas cuatro semanas tentativo) "
        r"(?:y )?aún por confirmar con el diseñador"
    ),
    "BD-RU-AGREED": r"(?:срок )?согласован с исполнителем сдача 20 декабря" + _RU_YEAR,
    "BD-EN-AGREED": (
        r"(?:deadline )?(?:agreed with the developer on (?:our|a) call (?:as )?december 20|"
        r"december 20 agreed with the developer on (?:our|a) call)" + _EN_YEAR
    ),
    "BD-EN-PLAIN": r"(?:deadline )?march 3" + _EN_YEAR,
}
_DEADLINE_LABEL = re.compile(
    r"(?:(?:желаемый |предварительный )?срок|(?:предварительный )?запуск|"
    r"deadline|(?:the )?preferred schedule|plazo)\b"
)


def _normalize(text: str) -> str:
    # Ignore presentation punctuation, but keep negation, question marks, words, and dates.
    return " ".join(re.sub(r"[.,:;—–]", " ", text.casefold().replace("ё", "е")).split())


def assert_deadline_clauses(case_id: str, output: dict) -> None:
    """Check only the two deadline clauses, including partial authored canonical examples."""
    assert case_id in _CLAUSES, f"unsupported deadline case: {case_id}"
    clause = _CLAUSES[case_id]
    values = output["brief"]["values"]
    assert "deadline" in values, "missing extracted deadline"
    deadline = values["deadline"]
    assert isinstance(deadline, str), "extracted deadline must be text"
    assert re.fullmatch(clause, _normalize(deadline)), (
        f"{case_id}: extracted deadline lost a required fact or uses unreviewed wording: {deadline}"
    )

    sections = [s for s in output["document"]["sections"] if s["id"] == "key-details"]
    assert len(sections) == 1, "expected exactly one key-details section"
    content = sections[0]["content"]
    assert isinstance(content, str), "key-details content must be text"
    lines = [
        _normalize(re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", line)) for line in content.splitlines()
    ]
    deadlines = [line for line in lines if _DEADLINE_LABEL.match(line)]
    assert len(deadlines) == 1, "expected exactly one labeled deadline item in key-details"
    assert re.fullmatch(clause, deadlines[0]), (
        f"{case_id}: key-details deadline lost a required fact or uses unreviewed wording: "
        f"{deadlines[0]}"
    )


def assert_deadline_status(case_id: str, output: dict) -> None:
    """Check a complete output; callers must separately verify capture provenance/schema."""
    assert_deadline_clauses(case_id, output)
    document = output["document"]
    # composeCopyText copies summary and every title/content in order; metadata is not copied.
    copied_fields = {
        "summary": document.get("summary"),
        "sections": [
            {field: section.get(field) for field in ("id", "title", "content")}
            for section in document["sections"]
        ],
    }
    fingerprint = hashlib.sha256(
        json.dumps(copied_fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    # shortcut: exact reviewed prose only; review new variants before extending the references.
    assert fingerprint in _REVIEWED_DOCUMENTS[case_id], (
        f"{case_id}: unreviewed copied document ({fingerprint}); review the entire document "
        "for contradictions before approving a new reference"
    )
