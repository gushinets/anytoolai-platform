"""Protect the ANY-762 prompt contract and cases; model behavior needs live evaluation."""

import hashlib
import json
import re
from pathlib import Path

import jsonschema
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[5]
PRODUCT = (
    ROOT
    / "packages/backend/product-platforms/freelancer-suite/src"
    / "anytoolai_freelancer_suite/products/brief_decoder"
)
SUITE = json.loads(
    (ROOT / "tests/fixtures/brief_decoder_eval/deadline_status.json").read_text(encoding="utf-8")
)
EXPECTED_BD_RU_05 = (
    "Нужно связать форму заявки сайта онлайн-курсов с amoCRM. При новой заявке создаётся "
    "контакт и сделка с названием курса; повторная заявка на тот же email не должна дублировать "
    "контакт. Источник — одна форма на https://courses.example/apply. Нужен журнал ошибок и "
    "инструкция запуска. Перенос старых заявок, рассылки и телефония исключены. Тестовый аккаунт "
    "CRM предоставляет заказчик. Нужно проверить успешную заявку, повторный email и "
    "недоступность CRM. Желаемый срок клиента — 10 дней; окончательную оценку исполнитель ещё не давал."
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
        "BD-RU-05", "BD-EN-PREFERRED", "BD-RU-CONDITIONAL", "BD-ES-TENTATIVE",
        "BD-RU-AGREED", "BD-EN-AGREED", "BD-EN-PLAIN",
    }
    assert {case["status"] for case in SUITE["cases"]} == {"unconfirmed", "agreed", "plain"}
    assert {
        case["language"] for case in SUITE["cases"] if case["status"] == "unconfirmed"
    } == {"ru", "en", "es"}


@pytest.mark.parametrize("case", SUITE["cases"], ids=lambda case: case["id"])
def test_case_input_fits_decode_input_schema(case: dict) -> None:
    schema = json.loads((PRODUCT / "schemas/decode_input.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(case["input"], schema)


@pytest.mark.parametrize("case", SUITE["cases"], ids=lambda case: case["id"])
def test_canonical_deadline_and_key_details_keep_status(case: dict) -> None:
    for field in ("deadline", "key_details_line"):
        text = case["canonical"][field].lower()
        if case["status"] == "unconfirmed":
            assert any(marker in text for marker in case["unconfirmed_markers"]), field
        else:
            assert not any(marker in text for marker in case["unconfirmed_markers"]), field
            if case["status"] == "agreed":
                assert any(marker in text for marker in case["agreed_markers"]), field
        assert set(re.findall(r"\d+", text)) <= set(re.findall(r"\d+", case["input"]["brief_text"]))
