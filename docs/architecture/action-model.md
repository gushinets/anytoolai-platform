# Action Model

Action = product-neutral typed logical operation.

Action Configuration = product/scenario-specific behavior for an action type.

MVP-A implements all 11 Wave 1 action types using one generic `StructuredLlmActionExecutor` where possible.

## Structured LLM executor decision

`StructuredLlmActionExecutor` is the only MVP-A place where PydanticAI may be used.

It owns:

- resolving prompt and schema references for an action config;
- invoking PydanticAI for typed structured-output execution;
- letting PydanticAI perform validation retries;
- calling Provider Gateway for every physical model attempt;
- returning an AnytoolAI `ActionResult` for downstream workflow mapping.

It does not own:

- provider/model selection outside `provider_policy_ref`;
- direct LiteLLM SDK calls;
- direct provider SDK calls;
- workflow orchestration;
- scenario/session/job persistence;
- artifact persistence as a hidden side effect;
- product-specific Freelancer semantics.

All physical provider attempts go through Provider Gateway so retry accounting and `platform.provider_calls` remain deterministic.

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

## A09 `text.synthesize_angle` contract

Strict, closed (`additionalProperties: false`) schemas — `kernel.schemas.synthesize_angle_input_v1` / `kernel.schemas.synthesize_angle_output_v1`:

- Input: `signals` (required, non-empty array of `{id, label, value, evidence?}`; `id`/`label` non-empty strings, `value` accepts any JSON type, `evidence` an optional non-empty string); `objective` (required, non-empty string); optional `options` (array of unique non-empty strings).
- Output: `angle` (required, non-empty primary recommendation) and `rationale` (required, non-empty, `maxLength: 500` concise explanation); optional `secondary_angle` (non-empty string when present).
- `SynthesizeAngleCrossValidator` enforces options-membership: when `options` is non-empty, `angle`/`secondary_angle` must each be one of them; when `options` is absent/empty, synthesis is open with no membership check. Rejected values are truncated (`_truncated_repr`) before flowing into the retry prompt and persisted debug-artifact metadata.
- The chain-of-thought prohibition on `rationale` is a prompt instruction (`synthesize_angle.v1.md`), not a runtime heuristic — the ticket frames it as a validation/prompt requirement, not a strict contract.

## A02 `text.score_match_by_rubric` contract

Strict, closed (`additionalProperties: false`) schemas — `kernel.schemas.score_match_input_v1` / `kernel.schemas.score_match_output_v1`:

- Input: `text_a` and `text_b` (required, non-empty strings); `rubric` (required, non-empty array of `{id, description, weight}`; `id`/`description` non-empty strings, `weight` a positive number).
- Output: `criterion_scores` (required, non-empty array of `{criterion_id, score, rationale}`; `score` 0–100, `rationale` non-empty with `maxLength: 500`); `score` (required aggregate, 0–100); `strengths` and `gaps` (required arrays of non-empty strings, may be empty).
- `ScoreMatchByRubricInputValidator` rejects duplicate `rubric[*].id` before any provider call — JSON Schema cannot express partial-key uniqueness, so this runs the same way as `ExtractStructuredFieldsInputValidator`. Non-positive `weight` and an empty `rubric` are rejected by the input schema itself (`exclusiveMinimum`/`minItems`), not by this validator.
- `ScoreMatchByRubricCrossValidator` enforces that `criterion_scores` maps exactly once onto `rubric` (exists, unique, exhaustive — every `criterion_id` must be a rubric id, no id repeats, and every rubric id must appear), then recomputes the rubric-weighted average of `criterion_scores` outside the model response and rejects a `score` that disagrees by more than `0.5` points. That tolerance has no prior codebase precedent (every earlier cross validator does membership/bounds/regex checks, not arithmetic); `0.5` covers the model rounding the weighted average to the nearest whole point on the 0–100 scale. Rejected/oversized values are truncated (`_truncated_repr`) before flowing into the retry prompt and persisted debug-artifact metadata.
- The chain-of-thought prohibition on `rationale` is a prompt instruction (`score_match_by_rubric.v1.md`), not a runtime heuristic, matching the sibling A09 contract.

## A10 `document.generate_from_template` contract

Strict, closed (`additionalProperties: false`) schemas — `kernel.schemas.generate_document_input_v1` / `kernel.schemas.generate_document_output_v1`:

- Input: `template_ref` (required, non-empty and non-whitespace string) identifying the product-registered template; `data` (required object) holding the template's input fields; optional `style` enum (`professional | concise | detailed`, defaults to `professional`).
- Output: `sections` (required, non-empty array of ordered document sections) and `summary` (required, non-empty and non-whitespace string). Each section is `{id, title, content}` (all required, non-empty and non-whitespace strings) plus an optional `metadata.kind` enum (`heading | paragraph | list | table | note`), required whenever `metadata` is present so an empty `metadata: {}` is rejected.
