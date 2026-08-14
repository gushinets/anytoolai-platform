from __future__ import annotations

from action_runner.always_fail_fake_adapter import AlwaysFailFakeAdapter
from action_runner.cancelled_fake_adapter import CancelledFakeAdapter
from action_runner.compare_and_classify_out_of_categories_then_valid_adapter import (
    CompareAndClassifyOutOfCategoriesThenValidAdapter,
)
from action_runner.compose_reply_over_limit_then_valid_adapter import (
    ComposeReplyOverLimitThenValidAdapter,
)
from action_runner.counting_fake_adapter import CountingFakeAdapter
from action_runner.empty_questions_fake_adapter import EmptyQuestionsFakeAdapter
from action_runner.gap_rewrites_count_mismatch_then_valid_adapter import (
    GapRewritesCountMismatchThenValidAdapter,
)
from action_runner.generic_executor import GenericExecutor
from action_runner.invalid_structured_output_adapter import InvalidStructuredOutputAdapter
from action_runner.synthesize_angle_out_of_options_then_valid_adapter import (
    SynthesizeAngleOutOfOptionsThenValidAdapter,
)
from action_runner.synthesize_angle_secondary_out_of_options_then_valid_adapter import (
    SynthesizeAngleSecondaryOutOfOptionsThenValidAdapter,
)

__all__ = [
    "AlwaysFailFakeAdapter",
    "CancelledFakeAdapter",
    "CompareAndClassifyOutOfCategoriesThenValidAdapter",
    "ComposeReplyOverLimitThenValidAdapter",
    "CountingFakeAdapter",
    "EmptyQuestionsFakeAdapter",
    "GapRewritesCountMismatchThenValidAdapter",
    "GenericExecutor",
    "InvalidStructuredOutputAdapter",
    "SynthesizeAngleOutOfOptionsThenValidAdapter",
    "SynthesizeAngleSecondaryOutOfOptionsThenValidAdapter",
]
