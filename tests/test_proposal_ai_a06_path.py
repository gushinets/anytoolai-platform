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


@pytest.mark.parametrize(("fee", "fraction"), [("3 200,50", "50"), ("12 500.75", "75")])
def test_the_fraction_of_a_space_grouped_fee_is_not_an_allowed_price(fee: str, fraction: str) -> None:
    with pytest.raises(StructuredOutputValidationError):
        PersuasiveTextCrossValidator().validate(
            input_payload={
                "constraints": _proposal_constraints(),
                "context": {"freelancer_positioning": f"My fixed fee is {fee} EUR"},
            },
            output={"text": f"My fixed fee is {fraction} EUR."},
        )
