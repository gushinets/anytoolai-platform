"""Protect the prompt contract and V06 inputs; model behavior needs live evaluation."""

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[5]
PRODUCT = (
    ROOT
    / "packages/backend/product-platforms/freelancer-suite/src"
    / "anytoolai_freelancer_suite/products/client_update_writer"
)
FIXTURES = ROOT / "tests/fixtures/client_update_writer_eval"
SUITE = json.loads((FIXTURES / "commercial_terms.json").read_text(encoding="utf-8"))


def prompt_text() -> str:
    return " ".join(
        (PRODUCT / "prompts/update_compose_reply.v1.md").read_text(encoding="utf-8").split()
    )


def test_update_requires_commercial_terms_even_without_payment_request() -> None:
    text = prompt_text()
    assert "The completeness rule also covers client-facing commercial terms" in text
    assert "contract or quoted amounts with their currencies" in text
    assert "stated agreement/payment status and conditions" in text
    assert (
        "even when the update is not a payment request; this does not mean omitting the amount."
    ) in text
    assert "Do not invent an invoice, balance due, payment demand or payment deadline." in text


def test_commercial_context_does_not_override_privacy_or_author_withholding() -> None:
    text = prompt_text()
    assert (
        "These client-facing terms are distinct from the freelancer's own private costs "
        "and margins."
    ) in text
    assert "Explicit author directions to withhold a term still take precedence." in text
    assert (
        "The freelancer's own costs, margins, subcontractors and private figures remain private "
        "unless `situation` explicitly authorizes sharing those details."
    ) in text


def test_v06_regression_preserves_the_original_failing_spanish_input() -> None:
    original = json.loads((FIXTURES / "final_variants.json").read_text(encoding="utf-8"))
    case = next(c for c in SUITE["cases"] if c["id"] == "V06-es")
    assert case == next(c for c in original["cases"] if c["id"] == "V06-es")
    assert hashlib.sha256(case["progress_notes"].encode()).hexdigest() == (
        "984f883cccbaefc00a53ff7e41cc0efa1adb2da2696476928b973f40deb735c1"
    )
    expected_ids = {
        f"V06-{prefix}{language}"
        for prefix in ("", "MIXED-", "WITHHELD-")
        for language in ("ru", "en", "es")
    }
    assert {case["id"] for case in SUITE["cases"]} == expected_ids
    assert SUITE["repeats"] == SUITE["minimum_usable"]
    assert SUITE["max_critical_errors"] == 0


@pytest.mark.parametrize("case", SUITE["cases"], ids=lambda case: case["id"])
def test_v06_live_case_fits_the_real_update_input_schema(case: dict) -> None:
    schema = json.loads((PRODUCT / "schemas/update_input.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate({"progress_notes": case["progress_notes"], "tone": case["tone"]}, schema)
