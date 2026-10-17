"""ProposalAI copy-ready guards through the whole A06 output validation (code review round 18).

Uses the real constraints the ProposalAI workflow passes to A06, so the kernel's plain-text markup
check and the product's forbidden_patterns are exercised together, in their real order.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from anytoolai_platform_actions.structured_llm.cross_validation import PersuasiveTextCrossValidator
from anytoolai_platform_core.structured_output.errors import StructuredOutputValidationError

WORKFLOWS = (
    Path(__file__).resolve().parents[1]
    / "packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite"
    / "products/proposal_ai/workflows.yaml"
)


def _proposal_constraints() -> dict:
    steps = yaml.safe_load(WORKFLOWS.read_text(encoding="utf-8"))["workflows"][0]["steps"]
    mapping = next(step for step in steps if step["step_id"] == "compose_persuasive_text")[
        "input_mapping"
    ]
    constraints = {}
    for key, source in mapping.items():
        if key.startswith("constraints.") and source.startswith("literal:"):
            literal = source.removeprefix("literal:")
            constraints[key.removeprefix("constraints.")] = json.loads(literal)
    return constraints


# The brief states every number the texts below use, as a real run's context would.
BRIEF = {"task_text": "Latency under 50ms, uptime 99%, budget 500, timeline 2 weeks, x 10"}


def _validate(text: str) -> None:
    PersuasiveTextCrossValidator().validate(
        input_payload={"constraints": _proposal_constraints(), "context": BRIEF},
        output={"text": text},
    )


@pytest.mark.parametrize(
    "text",
    [
        "Hello <client_name>, I can help.",
        "Hello<client_name>world, I can help.",
        "Hello <Имя или фамилия>, I can help.",
        "Hello <client and/or company>, I can help.",
        # any template syntax, not only a bracketed name (code review round 19)
        "Hello <%=client_name%>, I can help.",
        "Hello <%first_name%>, I can help.",
        "Hello <@client_name>, I can help.",
        "Hello <$name>, I can help.",
        "Hello <#name>, I can help.",
        "Hello %FIRST_NAME%, I can help.",
        "Hello %client.name%, I can help.",
        "Hello %\u0418\u041c\u042f%, I can help.",
        # fail closed: brackets around words are rejected even in a comparison
        "I can implement the condition x<y && a>b.",
        "I can implement x<y and a> 10.",
    ],
)
def test_a_bracketed_word_never_reaches_a_copy_ready_proposal(text: str) -> None:
    with pytest.raises(StructuredOutputValidationError):
        _validate(text)


@pytest.mark.parametrize(
    "text",
    [
        "I keep latency <50ms and uptime >99% on every integration.",
        "Budget < 500 and timeline > 2 weeks works for me.",
        "I keep latency <=50ms and uptime >99%.",
        "Uptime stays at 99% while latency drops by 50%.",
        "I can start this week and deliver the integration with tests.",
    ],
)
def test_numeric_comparisons_and_plain_prose_pass(text: str) -> None:
    _validate(text)


def _validate_fee(profile: str, text: str) -> None:
    PersuasiveTextCrossValidator().validate(
        input_payload={"constraints": _proposal_constraints(), "context": {"freelancer_positioning": profile}},
        output={"text": text},
    )


@pytest.mark.parametrize(
    ("profile", "fee"),
    [
        ("My fixed fee is 3 200,50 EUR", "50"),
        ("My fixed fee is 3 200,50 EUR", "200,50"),
        ("My fixed fee is 3 200,50 EUR", "3"),
        ("My fixed fee is 12 500.75 EUR", "75"),
        ("My fixed fee is 12 500.75 EUR", "500.75"),
        ("3 projects, 200 clients", "3 200"),
    ],
)
def test_a_space_grouped_fee_is_one_amount_never_its_parts(profile: str, fee: str) -> None:
    with pytest.raises(StructuredOutputValidationError):
        _validate_fee(profile, f"My fixed fee is {fee} EUR.")


def test_a_space_grouped_fee_may_be_restated() -> None:
    _validate_fee("My fixed fee is 3 200,50 EUR", "My fixed fee is 3200.50 EUR.")


@pytest.mark.parametrize(
    ("profile", "faithful", "invented"),
    [
        ("My fixed fee is CHF 1'500.", "My fixed fee is CHF 1500.", "My fixed fee is CHF 500."),
        ("My fixed fee is CHF 1'500.", "My fixed fee is CHF 1,500.", "My fixed fee is CHF 1."),
        ("My fixed fee is CHF 1’500.", "My fixed fee is CHF 1500.", "My fixed fee is CHF 500."),
        ("My fixed fee is CHF 1'500.50.", "My fixed fee is CHF 1500.50.", "My fixed fee is CHF 500.50."),
        ("I delivered +20% revenue growth.", "I delivered 20% revenue growth.", "I delivered -20% revenue growth."),
        ("My fixed fee is +200 EUR.", "My fixed fee is 200 EUR.", "My fixed fee is -200 EUR."),
        ("My rate is $1.234k.", "My rate is $1,234.", "My rate is $1,234,000."),
        ("I processed .5M rows.", "I processed 500,000 rows.", "I processed 5,000,000 rows."),
    ],
)
def test_a_number_is_read_by_its_shape(profile: str, faithful: str, invented: str) -> None:
    _validate_fee(profile, faithful)
    with pytest.raises(StructuredOutputValidationError):
        _validate_fee(profile, invented)


def test_a_scaled_fee_keeps_its_exact_fraction() -> None:
    _validate_fee("My fixed fee is $1.2345k", "My fixed fee is $1,234.50.")
    with pytest.raises(StructuredOutputValidationError):
        _validate_fee("My fixed fee is $1.2345k", "My fixed fee is $1,234.")


@pytest.mark.parametrize(
    ("profile", "faithful", "altered"),
    [
        ("I can complete a 2-to-3-week project", "in 2 to 3 weeks", "in 2 to 4 weeks"),
        ("We build 3-to-5-page websites", "websites of 3 to 5 pages", "websites of 3 to 6 pages"),
    ],
)
def test_a_digit_leading_hyphenated_range_keeps_its_upper_bound(
    profile: str, faithful: str, altered: str
) -> None:
    _validate_fee(profile, f"I can deliver {faithful}.")
    with pytest.raises(StructuredOutputValidationError):
        _validate_fee(profile, f"I can deliver {altered}.")


@pytest.mark.parametrize("hyphen", ["-", "‐", "‑"])
def test_a_typographic_hyphen_separates_a_count_from_a_hyphenated_unit(hyphen: str) -> None:
    profile = f"Wrote 3 500{hyphen}word posts last week"
    _validate_fee(profile, "I wrote 3 posts of 500 words each last week.")
    with pytest.raises(StructuredOutputValidationError):
        _validate_fee(profile, "I wrote 3,500 posts last week.")
