# Action Model

Action = product-neutral typed logical operation.

Action Configuration = product/scenario-specific behavior for an action type.

MVP-A implements all 11 Wave 1 action types using one generic `StructuredLlmActionExecutor` where possible.

## Required action definition fields

- `action_type`
- `version`
- `input_schema_ref`
- `output_schema_ref`
- `executor`
- `emits_events`

## Wave 1 action types

| Old atom | Platform action type |
|---|---|
| A01 `extract_structured` | `text.extract_structured_fields` |
| A04 `detect_issues` | `text.detect_issues_by_taxonomy` |
| A07 `generate_reply` | `text.compose_reply` |
| A09 `generate_angle` | `text.synthesize_angle` |
| A10 `generate_document` | `document.generate_from_template` |
| A11 `compare_classify` | `text.compare_and_classify` |
| A02 `score_match` | `text.score_match_by_rubric` |
| A06 `generate_proposal` | `text.compose_persuasive_text` |
| A08 `generate_rewrites` | `text.generate_gap_rewrites` |
| A03 `score_multidim` | `text.score_multidimensional_axes` |
| A05 `generate_questions` | `text.generate_clarifying_questions` |

`generate_proposal` must never become a platform action type. ProposalAI uses `text.compose_persuasive_text` through product-specific MVP-B action config.
