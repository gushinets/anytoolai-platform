"""Evidence for the combined-feasibility decision in the Draft risk evaluation suite."""

import re


def scope_questions(output: dict, language: str) -> list[dict]:
    """Only a question linked to the joint scope, time and budget finding qualifies."""
    deadline = {"ru": "завтра", "en": "tomorrow", "es": "mañana"}[language]
    indexes = set()
    for index, issue in enumerate(output["issues"]):
        text = (issue["description"] + " " + issue.get("evidence", "")).casefold()
        if (
            issue["severity"] == "high"
            and issue["category"] in {"scope_risk", "timeline_risk", "budget_risk"}
            and all(
                re.search(pattern, text)
                for pattern in (
                    r"500",
                    r"15[ .,\u202f\xa0]?000",
                    deadline,
                    r"кабинет|account|cuenta",
                    r"оплат|payment|pago",
                    r"1[cс]",
                )
            )
        ):
            indexes.add(index)
    return [q for q in output["questions"] if q["source_issue_index"] in indexes]
