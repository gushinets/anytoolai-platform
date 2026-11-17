"""Replay ANY-762 captured outputs; future model behavior still needs fresh live evaluation."""

import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest
import yaml

from tests.support.brief_decoder_deadline_status import assert_deadline_status

ROOT = Path(__file__).resolve().parents[5]
PRODUCT = (
    ROOT
    / "packages/backend/product-platforms/freelancer-suite/src"
    / "anytoolai_freelancer_suite/products/brief_decoder"
)
SUITE = json.loads(
    (ROOT / "tests/fixtures/brief_decoder_eval/deadline_status.json").read_text(encoding="utf-8")
)
EVIDENCE = json.loads(
    (
        ROOT
        / "docs/exec-plans/active"
        / "any-762-brief-decoder-deadline-status.evidence-20261117.json"
    ).read_text(encoding="utf-8")
)
EXPECTED_BD_RU_05 = (
    "Нужно связать форму заявки сайта онлайн-курсов с amoCRM. При новой заявке создаётся "
    "контакт и сделка с названием курса; повторная заявка на тот же email не должна дублировать "
    "контакт. Источник — одна форма на https://courses.example/apply. Нужен журнал ошибок и "
    "инструкция запуска. Перенос старых заявок, рассылки и телефония исключены. Тестовый аккаунт "
    "CRM предоставляет заказчик. Нужно проверить успешную заявку, повторный email и "
    "недоступность CRM. Желаемый срок клиента — 10 дней; окончательную оценку исполнитель "
    "ещё не давал."
)


def _prompt(name: str) -> str:
    return " ".join((PRODUCT / "prompts" / name).read_text(encoding="utf-8").split())


def test_extract_prompt_keeps_term_status_with_its_value() -> None:
    text = _prompt("extract_brief.v1.md")
    assert "Keep the status the brief gives a deadline or budget together with its value." in text
    assert "even when the brief writes it as a label before the value" in text
    assert "and so is a stated lack of confirmation" in text
    assert "Never reduce such a term to the bare date, duration or amount." in text
    assert (
        "a term the brief states as agreed or fixed stays agreed or fixed, and a plain term "
        "without a qualifier is not marked as unconfirmed."
    ) in text
    assert "Never invent a final estimate, a new date or a confirmation." in text


def test_summary_prompt_keeps_term_status_in_key_details() -> None:
    text = _prompt("generate_summary.v1.md")
    assert "or budget with the status its `data.brief.values` entry states" in text
    assert (
        "Never present such a term as a fixed deadline or an agreed budget, "
        "and never add a status the value does not carry."
    ) in text
    assert "Do not drop or upgrade a stated status of a term" in text
    assert (
        "deadline or budget stays one in every section and in `summary`, "
        "and an agreed one stays agreed."
    ) in text


@pytest.mark.parametrize("field_name", ["deadline", "budget"])
def test_deadline_field_description_asks_for_status(field_name: str) -> None:
    workflow = yaml.safe_load((PRODUCT / "workflows.yaml").read_text(encoding="utf-8"))
    extract = next(
        step for step in workflow["workflows"][0]["steps"] if step["step_id"] == "extract"
    )
    fields = json.loads(extract["input_mapping"]["fields"].removeprefix("literal:"))
    field = next(field for field in fields if field["name"] == field_name)
    assert "including its stated status" in field["description"]


def test_bd_ru_05_is_the_original_ticket_input() -> None:
    case = next(case for case in SUITE["cases"] if case["id"] == "BD-RU-05")
    text = case["input"]["brief_text"]
    assert text == EXPECTED_BD_RU_05
    assert hashlib.sha256(text.encode()).hexdigest() == (
        "28de603ce1d141a6b19e550dcf07f6a072bbe05debd3b233e0b38b96b2f2bcac"
    )
    assert {case["id"] for case in SUITE["cases"]} == {
        "BD-RU-05",
        "BD-EN-PREFERRED",
        "BD-RU-CONDITIONAL",
        "BD-ES-TENTATIVE",
        "BD-RU-AGREED",
        "BD-EN-AGREED",
        "BD-EN-PLAIN",
    }
    assert {case["status"] for case in SUITE["cases"]} == {"unconfirmed", "agreed", "plain"}
    assert {case["language"] for case in SUITE["cases"] if case["status"] == "unconfirmed"} == {
        "ru",
        "en",
        "es",
    }


@pytest.mark.parametrize("case", SUITE["cases"], ids=lambda case: case["id"])
def test_case_input_fits_decode_input_schema(case: dict) -> None:
    schema = json.loads((PRODUCT / "schemas/decode_input.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(case["input"], schema)


@pytest.mark.parametrize("case", SUITE["cases"], ids=lambda case: case["id"])
def test_canonical_deadline_and_key_details_keep_status(case: dict) -> None:
    assert_deadline_status(
        case["id"],
        {
            "brief": {"values": {"deadline": case["canonical"]["deadline"]}},
            "document": {
                "sections": [
                    {
                        "id": "key-details",
                        "content": case["canonical"]["key_details_line"],
                    }
                ]
            },
        },
    )


def _captured_output(run: dict) -> dict:
    # The capture projects brief.values.deadline; document is the persisted A10 output.
    return {
        "brief": {"values": {"deadline": run["deadline"]}},
        "document": deepcopy(run["document"]),
    }


def test_captured_runs_cover_every_case_and_match_the_reviewed_sources() -> None:
    assert Counter((run["case_id"], run["attempt"]) for run in EVIDENCE["runs"]) == Counter(
        (case["id"], attempt) for case in SUITE["cases"] for attempt in (1, 2, 3)
    )
    assert len({run["session_id"] for run in EVIDENCE["runs"]}) == len(EVIDENCE["runs"])
    assert (
        EVIDENCE["fixture_sha256"]
        == hashlib.sha256(
            (ROOT / "tests/fixtures/brief_decoder_eval/deadline_status.json").read_bytes()
        ).hexdigest()
    )
    for relative in (
        "prompts/extract_brief.v1.md",
        "prompts/generate_summary.v1.md",
        "workflows.yaml",
    ):
        path = PRODUCT / relative
        assert EVIDENCE["worker_source_sha256"][path.relative_to(ROOT).as_posix()] == (
            hashlib.sha256(path.read_bytes()).hexdigest()
        )
    inputs = {
        case["id"]: hashlib.sha256(case["input"]["brief_text"].encode()).hexdigest()
        for case in SUITE["cases"]
    }
    for run in EVIDENCE["runs"]:
        assert run["input_sha256"] == inputs[run["case_id"]]


@pytest.mark.parametrize(
    "run",
    EVIDENCE["runs"],
    ids=lambda run: f"{run['case_id']}--{run['attempt']}",
)
def test_captured_output_keeps_deadline_status(run: dict) -> None:
    assert_deadline_status(run["case_id"], _captured_output(run))


# Each replacement is tested in just one output at a time: the other must not mask its failure.
BAD_DEADLINES = [
    ("BD-RU-05", "bare-duration", "Срок: 10 дней"),
    ("BD-RU-05", "missing-confirmation", "Желаемый срок клиента — 10 дней"),
    (
        "BD-RU-05",
        "missing-preference",
        "Срок: 10 дней; окончательную оценку исполнитель ещё не давал",
    ),
    ("BD-RU-05", "invented-confirmation", "Желаемый срок клиента — 10 дней; оценка подтверждена"),
    (
        "BD-EN-PREFERRED",
        "bare-schedule",
        "Deadline: three weeks from kickoff, with launch by December 10",
    ),
    ("BD-EN-PREFERRED", "missing-launch", "Preferred schedule: three weeks from kickoff"),
    (
        "BD-EN-PREFERRED",
        "missing-kickoff",
        "Preferred schedule: three weeks, with launch by December 10",
    ),
    (
        "BD-EN-PREFERRED",
        "changed-month",
        "Preferred schedule: three weeks from kickoff, with launch by November 10",
    ),
    ("BD-RU-CONDITIONAL", "missing-prerequisite", "Предварительный запуск — 15 декабря"),
    ("BD-RU-CONDITIONAL", "missing-dates", "Предварительный срок"),
    (
        "BD-RU-CONDITIONAL",
        "reversed-events",
        "Срок указан условно: если запуск будет 1 декабря, макеты будут готовы к 15 декабря",
    ),
    (
        "BD-RU-CONDITIONAL",
        "reversed-dates",
        "Срок указан условно: если макеты будут готовы к 15 декабря, запуск — 1 декабря",
    ),
    (
        "BD-RU-CONDITIONAL",
        "unconditional",
        "Срок указан условно: макеты будут готовы к 1 декабря, запуск — 15 декабря",
    ),
    (
        "BD-RU-CONDITIONAL",
        "negated-prerequisite",
        "Срок указан условно: если макеты не будут готовы к 1 декабря, запуск — 15 декабря",
    ),
    ("BD-ES-TENTATIVE", "missing-confirmation", "Plazo tentativo: unas cuatro semanas"),
    (
        "BD-ES-TENTATIVE",
        "missing-tentative",
        "Plazo: unas cuatro semanas, aún por confirmar con el diseñador",
    ),
    (
        "BD-ES-TENTATIVE",
        "changed-duration",
        "Plazo tentativo: unas cinco semanas, aún por confirmar con el diseñador",
    ),
    ("BD-RU-AGREED", "missing-agreement", "Срок: сдача 20 декабря"),
    ("BD-RU-AGREED", "negated-agreement", "Срок не согласован с исполнителем: сдача 20 декабря"),
    ("BD-EN-AGREED", "missing-agreement", "Deadline: December 20"),
    ("BD-EN-AGREED", "negated-agreement", "Deadline not agreed with the developer: December 20"),
    (
        "BD-EN-AGREED",
        "contradictory-tail",
        "Deadline: agreed with the developer on our call: December 20; not agreed",
    ),
    ("BD-EN-PLAIN", "invented-agreement", "Deadline agreed: March 3"),
    ("BD-EN-PLAIN", "invented-uncertainty", "Deadline unconfirmed: March 3"),
    ("BD-EN-PLAIN", "invented-year", "Deadline: March 3, 2027"),
    ("BD-EN-PLAIN", "changed-day", "Deadline: March 4"),
]


@pytest.mark.parametrize("field", ["deadline", "key-details"])
@pytest.mark.parametrize(
    ("case_id", "defect", "replacement"),
    BAD_DEADLINES,
    ids=[f"{case_id}-{defect}" for case_id, defect, _ in BAD_DEADLINES],
)
def test_corrupted_outputs_are_rejected_independently(
    case_id: str,
    defect: str,
    replacement: str,
    field: str,
) -> None:
    run = next(run for run in EVIDENCE["runs"] if run["case_id"] == case_id)
    output = _captured_output(run)
    if field == "deadline":
        output["brief"]["values"]["deadline"] = replacement
    else:
        section = next(s for s in output["document"]["sections"] if s["id"] == "key-details")
        section["content"] = replacement
    message = "extracted deadline" if field == "deadline" else "key-details deadline"
    with pytest.raises(AssertionError, match=message):
        assert_deadline_status(case_id, output)


@pytest.mark.parametrize("section_id", ["gaps", "overview", "key-details"])
def test_qualifiers_in_other_facts_cannot_rescue_a_bare_deadline(section_id: str) -> None:
    run = next(run for run in EVIDENCE["runs"] if run["case_id"] == "BD-RU-05")
    output = _captured_output(run)
    for section in output["document"]["sections"]:
        section["content"] = "Срок: 10 дней" if section["id"] == "key-details" else ""
        if section["id"] == section_id:
            section["content"] += (
                "\n- Бюджет: желаемый, окончательную оценку исполнитель ещё не давал."
            )
    with pytest.raises(AssertionError, match="key-details deadline"):
        assert_deadline_status("BD-RU-05", output)


@pytest.mark.parametrize("defect", ["missing-section", "duplicate-section", "missing-deadline"])
def test_incomplete_or_ambiguous_outputs_are_rejected(defect: str) -> None:
    output = _captured_output(EVIDENCE["runs"][0])
    sections = output["document"]["sections"]
    section = next(s for s in sections if s["id"] == "key-details")
    if defect == "missing-section":
        sections.remove(section)
    elif defect == "duplicate-section":
        sections.append(deepcopy(section))
    else:
        del output["brief"]["values"]["deadline"]
    with pytest.raises(AssertionError):
        assert_deadline_status("BD-RU-05", output)


def test_cached_review_and_deadline_line_do_not_override_document_content() -> None:
    run = deepcopy(EVIDENCE["runs"][0])
    section = next(s for s in run["document"]["sections"] if s["id"] == "key-details")
    section["content"] = "Срок: 10 дней"
    assert run["semantic_review"]["verdict"] == "PASS"
    assert "Желаемый срок" in run["deadline_line"]
    with pytest.raises(AssertionError, match="key-details deadline"):
        assert_deadline_status(run["case_id"], _captured_output(run))


@pytest.mark.parametrize("extra_line", ["Deadline: March 4", "Deadline: March 3"])
def test_multiple_deadline_items_are_not_silently_selected(extra_line: str) -> None:
    run = next(run for run in EVIDENCE["runs"] if run["case_id"] == "BD-EN-PLAIN")
    output = _captured_output(run)
    section = next(s for s in output["document"]["sections"] if s["id"] == "key-details")
    section["content"] += "\n- " + extra_line
    with pytest.raises(AssertionError, match="exactly one labeled deadline"):
        assert_deadline_status(run["case_id"], output)


def test_prerequisite_in_another_bullet_does_not_make_launch_conditional() -> None:
    run = next(run for run in EVIDENCE["runs"] if run["case_id"] == "BD-RU-CONDITIONAL")
    output = _captured_output(run)
    section = next(s for s in output["document"]["sections"] if s["id"] == "key-details")
    section["content"] = (
        "- Срок: запуск — 15 декабря.\n- Допущение: если макеты будут готовы к 1 декабря."
    )
    with pytest.raises(AssertionError, match="key-details deadline"):
        assert_deadline_status(run["case_id"], output)


@pytest.mark.parametrize("bullet", ["- ", "• ", "* ", "2) "])
def test_presentation_changes_preserve_the_reviewed_clause(bullet: str) -> None:
    output = {
        "brief": {"values": {"deadline": "  MARCH  3. "}},
        "document": {
            "sections": [
                {
                    "id": "key-details",
                    "content": bullet + "DEADLINE:\tMarch 3.",
                }
            ]
        },
    }
    assert_deadline_status("BD-EN-PLAIN", output)
