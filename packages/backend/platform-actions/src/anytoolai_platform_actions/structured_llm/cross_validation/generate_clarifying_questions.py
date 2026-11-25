from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ._shared import _coerce_integer_valued, _cross_validation_error, _truncated_repr

_QUESTION_PRIORITY_RANK: Mapping[str, int] = {"high": 0, "medium": 1, "low": 2}
_DEFAULT_MAX_QUESTIONS = 5


class GenerateClarifyingQuestionsCrossValidator:
    """Validates A05 output.questions against dynamic constraints from A05 input that the
    static output schema cannot express: each source_issue_index must be in bounds of
    input.issues, the list must not exceed input.max_questions (default 5), and questions must
    use allowed categories when a taxonomy is supplied. Order is by priority then issue index.
    """

    def validate(
        self,
        *,
        input_payload: Mapping[str, Any],
        output: Mapping[str, Any] | None,
    ) -> None:
        if output is None:
            raise _cross_validation_error("missing_output")
        questions = output.get("questions")
        if not isinstance(questions, list):
            raise _cross_validation_error("malformed_generate_clarifying_questions_output")

        issues = input_payload.get("issues")
        issue_count = len(issues) if isinstance(issues, list) else 0

        max_questions = _coerce_integer_valued(input_payload.get("max_questions"))
        if max_questions is None:
            max_questions = _DEFAULT_MAX_QUESTIONS
        if len(questions) > max_questions:
            raise _cross_validation_error(
                f"questions_exceed_max_questions:{len(questions)}>{max_questions}"
            )

        taxonomy = input_payload.get("taxonomy")
        previous_rank: tuple[int, int] | None = None
        for question in questions:
            if not isinstance(question, Mapping):
                raise _cross_validation_error("malformed_question_entry")
            source_issue_index = _coerce_integer_valued(question.get("source_issue_index"))
            if source_issue_index is None or not (0 <= source_issue_index < issue_count):
                raise _cross_validation_error(
                    f"source_issue_index_out_of_bounds:{question.get('source_issue_index')}"
                )
            category = question.get("category")
            if taxonomy is not None and category not in taxonomy:
                raise _cross_validation_error(
                    f"category_not_in_taxonomy:{_truncated_repr(category)}"
                )
            priority_rank = _QUESTION_PRIORITY_RANK.get(question.get("priority"))
            if priority_rank is None:
                raise _cross_validation_error(
                    f"unknown_priority:{_truncated_repr(question.get('priority'))}"
                )
            rank = (priority_rank, source_issue_index)
            if previous_rank is not None and rank < previous_rank:
                raise _cross_validation_error("questions_not_deterministically_ordered")
            previous_rank = rank
