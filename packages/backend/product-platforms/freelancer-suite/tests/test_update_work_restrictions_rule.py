"""Pin the original V02 and its role-boundary controls; behavior needs live evaluation."""

import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[5]
FIXTURES = ROOT / "tests/fixtures/client_update_writer_eval"
SUITE = json.loads((FIXTURES / "work_restrictions.json").read_text(encoding="utf-8"))
EXPECTED_REPEATS = 5


def test_original_v02_is_unchanged_and_controls_cover_each_language() -> None:
    original = json.loads((FIXTURES / "final_variants.json").read_text(encoding="utf-8"))
    case = next(c for c in SUITE["cases"] if c["id"] == "V02-en")
    assert case == next(c for c in original["cases"] if c["id"] == "V02-en")
    assert {case["id"] for case in SUITE["cases"]} == {
        f"V02-{prefix}{language}"
        for prefix in ("", "DECL-", "EDITORIAL-", "WITHHELD-", "PUBLICATION-")
        for language in ("ru", "en", "es")
    }
    assert SUITE["repeats"] == SUITE["minimum_usable"] == EXPECTED_REPEATS
    assert SUITE["max_critical_errors"] == 0


@pytest.mark.parametrize("case", SUITE["cases"], ids=lambda case: case["id"])
def test_work_restriction_case_fits_update_input_schema(case: dict) -> None:
    schema_path = (
        ROOT / "packages/backend/product-platforms/freelancer-suite/src"
        / "anytoolai_freelancer_suite/products/client_update_writer"
        / "schemas/update_input.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate({"progress_notes": case["progress_notes"], "tone": case["tone"]}, schema)
