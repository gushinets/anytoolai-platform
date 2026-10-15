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
- `cross_validator_ref`
- `input_validator_ref`

`emits_events` is optional and defaults to `[]` when omitted.

`cross_validator_ref` and `input_validator_ref` are opaque strings in `platform-core` —
the loader requires them but does not resolve them. Use `"none"` as the explicit
sentinel for an atom with no validator. `platform-actions` resolves non-`"none"` refs
against its concrete validator classes at worker composition-root startup, failing
closed if a declared ref has no matching class, since `platform-core` must not import
`platform-actions` (see `docs/architecture/package-layering.md`).

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

## A06 `text.compose_persuasive_text` caller constraints

`input.constraints` (closed object) carries `tone`, `length`, `language`, `format` and four optional rules that stay product-neutral so any A06 caller can opt in:

- `forbidden_patterns` (array of regular expressions): `PersuasiveTextCrossValidator` rejects `text` when any pattern matches, case-insensitively (placeholders, boilerplate signatures, a banned dash). `PersuasiveTextInputValidator` rejects an invalid expression before any provider call; the input schema allows at most 32 patterns of at most 200 characters each; the whole list gets one second on the output, and a list that does not finish within it fails the action without a model retry (a caller bug, not a model mistake).
  ProposalAI treats any unfilled template marker as a placeholder, failing closed: a `<...>` span whose first character is not a space, a digit or `=` (`<client_name>`, `<%= name %>`, `<@name>`), and a `%NAME%` merge tag. A comparison with brackets around words is rejected too (the kernel's plain-text check already reads most of them as HTML), costing one retry, while a missed placeholder would ship an unsendable proposal. Numeric comparisons (`<50ms`, `<=50ms`, `< 500`) and percentages (`99%`) pass; `$NAME` and `__NAME__` are left to the prompt because technical prose uses them (`$PATH`, `__init__`).
- `plain_text_lists` (`allowed` | `forbidden`): `forbidden` rejects a CommonMark list, a line that starts with a bullet character, or two or more lines that start with a dash or a lettered marker (`a)`), on top of the kernel-wide plain_text policy that allows lists (ANY-502).
- `numbers_must_appear_in_context` (boolean): every number in `text` must occur in `input.context`, compared by value: grouped amounts (`1,500`, `1.234,50`, `3 200`) are one number, a dotted date is three, a word that starts with a letter is a name and offers no number (`GPT-4o`, `n8n`), a word that starts with a digit is a quantity whose unit is ignored (`16GB`, `12V`) and whose `k`/`M` suffix scales it (`$20k`). It catches invented amounts, dates and durations without domain knowledge. Fixed contract: it does not classify a digit inside a word (`4K`, `2FA` are quantities 4000 and 2 to it, not resolutions or acronyms) and it does not decide who asserted a number (a client budget in `context` is evidence for the same amount in `text`); both are semantic questions and belong to a separate check, not to this one. A finding of either kind is by design; a false rejection of a realistic input is a bug.
- `claims_to_avoid` (array of objects with a required `description`): prompt-level only. The caller lists statements the text must not assert, for example gaps found by A04. It is a constraint and not a `context` field because the mapping DSL rejects dotted `context.*` input targets.

A failed cross-validation is a PydanticAI validation retry, so the model gets another attempt before the user sees an error.

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

## A02 `text.score_match_by_rubric` contract

Strict, closed (`additionalProperties: false`) schemas — `kernel.schemas.score_match_input_v1` / `kernel.schemas.score_match_output_v1`:

- Input: `text_a` and `text_b` (required, non-empty strings); `rubric` (required, non-empty array of `{id, description, weight}`; `id`/`description` non-empty strings, `weight` a positive number).
- Output: `criterion_scores` (required, non-empty array of `{criterion_id, score, rationale}`; `score` 0–100, `rationale` non-empty with `maxLength: 500`); `score` (required aggregate, 0–100); `strengths` and `gaps` (required arrays of non-empty strings, may be empty); `overall_rationale` (required, non-empty, `maxLength: 500` synthesis across all criteria).
- `ScoreMatchByRubricInputValidator` rejects duplicate `rubric[*].id` before any provider call — JSON Schema cannot express partial-key uniqueness, so this runs the same way as `ExtractStructuredFieldsInputValidator`. Non-positive `weight` and an empty `rubric` are rejected by the input schema itself (`exclusiveMinimum`/`minItems`), not by this validator.
- `ScoreMatchByRubricCrossValidator` enforces that `criterion_scores` maps exactly once onto `rubric` (exists, unique, exhaustive — every `criterion_id` must be a rubric id, no id repeats, and every rubric id must appear), then recomputes the rubric-weighted average of `criterion_scores` outside the model response and rejects a `score` that disagrees by more than `0.5` points. That tolerance has no prior codebase precedent (every earlier cross validator does membership/bounds/regex checks, not arithmetic); `0.5` covers the model rounding the weighted average to the nearest whole point on the 0–100 scale. Rejected/oversized values are truncated (`_truncated_repr`) before flowing into the retry prompt and persisted debug-artifact metadata.
- The chain-of-thought prohibition on `rationale` is a prompt instruction (`score_match_by_rubric.v1.md`), not a runtime heuristic, matching the sibling A09 contract.

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

## kernel_demo composite workflow mapping notes

The workflow mapping DSL (`packages/backend/platform-core/.../workflows/mappings.py`) only
supports plain dotted paths — no array indexing, no string formatting/concatenation. Two places
in `kernel_demo`'s composite workflows hit this limitation directly:

- `composite_evaluate_match_v1`'s `score_multidimensional_axes` step needs a plain-string `text`
  input. `score_match_by_rubric`'s output had no top-level string — the only per-item rationale
  lives inside `criterion_scores[*].rationale`, which the DSL cannot reach. Fixed by adding a new
  top-level `overall_rationale` string to `score_match_output.schema.json` (a synthesis across all
  criteria, not a duplicate of any single `criterion_scores[*].rationale`) purely so this chain has
  a mapping-DSL-reachable field to consume.
- `composite_analyze_and_clarify_v1`'s `detect_issues` step stays order-only after `extract`, by
  contrast — `extract`'s output has no usable field either (`values` is an untyped,
  caller-controlled bag with no guaranteed field names; `missing_fields` is field names, not
  issue-taxonomy categories). A schema-extension fix was tried and reverted: it silently dropped
  `scenario.input.context` for this one workflow, forced every other caller of
  `extract_structured_fields_v1` to generate an unused field, and gave `retry_extract_v1` an extra
  way to burn its single retry slot on that field. Order-only here is the deliberate outcome, not
  an oversight — see `plans/ANY-219.md`'s team-lead-3/seventeenth/eighteenth review passes for the
  full history of what was tried.
