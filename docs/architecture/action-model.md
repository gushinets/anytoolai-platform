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

## A03 `text.score_multidimensional_axes` contract

Strict, closed (`additionalProperties: false`) schemas — `kernel.schemas.score_multidim_input_v1` / `kernel.schemas.score_multidim_output_v1`:

- Input: `text` (required, non-empty string); `axes` (required, non-empty array of `{id, description, weight?}`; `id`/`description` non-empty strings, `weight` an optional positive number the platform never reads — v1 uses one fixed documented 1–10 numeric scale).
- Output: `scores` (required, non-empty array of `{axis_id, score, commentary}`; `score` 1–10, `commentary` non-empty with `maxLength: 500`); `dominant_axes` and `weakest_axes` (required, non-empty arrays of axis ids).
- `ScoreMultidimensionalAxesInputValidator` rejects duplicate `axes[*].id` before any provider call — JSON Schema cannot express partial-key uniqueness — sharing the `_reject_duplicate_ids` helper with `ExtractStructuredFieldsInputValidator`.
- `ScoreMultidimensionalAxesCrossValidator` enforces that `scores` maps exactly once onto `axes` (exists, unique, exhaustive — every `axis_id` must be an axis id, no id repeats, and every axis id must appear), then recomputes `dominant_axes`/`weakest_axes` outside the model response as the tie-preserving, input-order set of axis ids at the max/min reported score and rejects a mismatch (missing tied entry, extra entry, or wrong order) exactly, with no numeric tolerance — unlike A02's weighted-aggregate recompute, these are direct equality checks against the model's own reported per-axis scores, not an independently-computed float. Rejected/oversized values are truncated (`_truncated_repr`) before flowing into the retry prompt and persisted debug-artifact metadata.
- The chain-of-thought prohibition on `commentary` is a prompt instruction (`score_multidimensional_axes.v1.md`), not a runtime heuristic, matching the sibling A09 contract.
- No product axis meaning (Ethos/Pathos/Logos, AI-cliché detection, or similar) is hardcoded in the platform contract — axes are entirely caller-supplied, per the parent ANY-49 issue.

## A09 `text.synthesize_angle` contract

Strict, closed (`additionalProperties: false`) schemas — `kernel.schemas.synthesize_angle_input_v1` / `kernel.schemas.synthesize_angle_output_v1`:

- Input: `signals` (required, non-empty array of `{id, label, value, evidence?}`; `id`/`label` non-empty strings, `value` accepts any JSON type, `evidence` an optional non-empty string); `objective` (required, non-empty string); optional `options` (array of unique non-empty strings).
- Output: `angle` (required, non-empty primary recommendation) and `rationale` (required, non-empty, `maxLength: 500` concise explanation); optional `secondary_angle` (non-empty string when present).
- `SynthesizeAngleCrossValidator` enforces options-membership: when `options` is non-empty, `angle`/`secondary_angle` must each be one of them; when `options` is absent/empty, synthesis is open with no membership check. Rejected values are truncated (`_truncated_repr`) before flowing into the retry prompt and persisted debug-artifact metadata.
- The chain-of-thought prohibition on `rationale` is a prompt instruction (`synthesize_angle.v1.md`), not a runtime heuristic — the ticket frames it as a validation/prompt requirement, not a strict contract.

## A10 `document.generate_from_template` contract

Strict, closed (`additionalProperties: false`) schemas — `kernel.schemas.generate_document_input_v1` / `kernel.schemas.generate_document_output_v1`:

- Input: `template_ref` (required, non-empty and non-whitespace string) identifying the product-registered template; `data` (required object) holding the template's input fields; optional `style` enum (`professional | concise | detailed`, defaults to `professional`).
- Output: `sections` (required, non-empty array of ordered document sections) and `summary` (required, non-empty and non-whitespace string). Each section is `{id, title, content}` (all required, non-empty and non-whitespace strings) plus an optional `metadata.kind` enum (`heading | paragraph | list | table | note`), required whenever `metadata` is present so an empty `metadata: {}` is rejected.

## A11 `text.compare_and_classify` contract

Strict, closed (`additionalProperties: false`) schemas — `kernel.schemas.compare_classify_input_v1` / `kernel.schemas.compare_classify_output_v1`:

- Input: `subject_text` and `reference_text` (required, non-empty strings); `categories` (required, array of unique non-empty strings, `minItems: 2`); `criteria` (required, non-empty array of `{id, description, weight?}`; `id`/`description` non-empty strings, optional `weight` a positive number).
- Output: `verdict` (required, non-empty category value), `confidence` (required number, `0`–`1`), `deltas` (required, non-empty array of `{criterion_id, status, evidence}` — `status` is the closed enum `match | partial | mismatch`, `evidence` a non-empty string), `rationale` (required, non-empty, `maxLength: 500` concise summary).
- `CompareAndClassifyInputValidator` rejects duplicate `criteria[*].id` before any provider call, mirroring `ExtractStructuredFieldsInputValidator` (A01) — a duplicate id would make the output's per-criterion coverage check ambiguous.
- `CompareAndClassifyCrossValidator` enforces: `verdict` must be one of `categories`; every `deltas[*].criterion_id` must exist in `criteria`, must not repeat, and `deltas` must cover every `criteria[*].id` exactly once (full coverage, not a partial subset — this was an explicit open contract question resolved as mandatory coverage so `verdict` always rests on a complete evidence set). Rejected values are truncated (`_truncated_repr`) before flowing into the retry prompt and persisted debug-artifact metadata.
- `confidence` is a relative signal, not a calibrated probability — that constraint is a prompt instruction (`compare_and_classify.v1.md`), not a runtime heuristic, matching the `rationale` chain-of-thought prohibition pattern used elsewhere in this doc.
