# Execution Plan: ANY-256 A20b2. A02 text.score_match_by_rubric Contract And Runtime

## Status

- State: active
- Owner: agent
- Created: 2026-08-14
- Last updated: 2026-08-14
- Review date: 2026-08-14
- Next action: none outstanding from the round-2 `/code-review` pass; keep in sync with any
  further review rounds.
- Blocker: none

## Goal

Implement the product-neutral `text.score_match_by_rubric` atom (legacy A02 `score_match`) as a
strict, independently runnable JSON-schema contract — `text_a`/`text_b`/`rubric[]` in,
`criterion_scores[]`/`score`/`strengths[]`/`gaps[]` out — executed through the existing
`StructuredLlmActionExecutor`/`ProviderGateway`/`ActionRunner`, so ANY-218 can count this atom
toward 11/11 without a placeholder/smoke qualification.

## Scope

### In scope

- Strict, closed (`additionalProperties: false`) input/output JSON schemas replacing the previous
  fully-permissive placeholders (`score_match_{input,output}.schema.json`).
- `ScoreMatchByRubricInputValidator`: rejects duplicate `rubric[*].id` before any provider call
  (JSON Schema can't express partial-key uniqueness); shares a `_reject_duplicate_ids` helper with
  `ExtractStructuredFieldsInputValidator` (review round 1).
- `ScoreMatchByRubricCrossValidator`: enforces `criterion_scores` maps exactly once onto `rubric`
  (exists + unique + exhaustive), then recomputes the rubric-weighted average of `criterion_scores`
  outside the model response and rejects a `score` that disagrees by more than a fixed `0.5`-point
  tolerance — with an explicit `math.isfinite` guard on the recomputed aggregate so an
  overflow-to-`NaN` weight combination can't silently bypass the check (review round 1, critical).
- Product-neutral prompt (`score_match_by_rubric.v1.md`) instructing the model to compute the
  aggregate as the rubric-weighted average rounded to the nearest whole number.
- Registration: action definition, `schemas.yaml` (pre-existing), `kernel_demo`
  `action_configs.yaml`/`prompts.yaml`, deterministic fake-provider fixture, and production
  `output_cross_validators`/`input_validators` wiring in `apps/platform-worker/.../composition.py`.
- Schema/cross-validation/ActionRunner test coverage plus config/architecture/docs/quick-check
  gates.

### Out of scope

- The sibling A20b atoms (`text.compare_and_classify` / ANY-255, `text.score_multidimensional_axes`
  / ANY-257).
- Any product-specific rubric content, weighting scheme, or taxonomy — explicitly MVP-B scope per
  the parent ANY-49 issue.

## Relevant docs

- `docs/architecture/action-model.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/exec-plans/active/any-259-a20c2-a09-text-synthesize-angle-contract-and-runtime.md`
  (sibling Wave-1 atom; same review-driven exec-plan gap raised and fixed there first)

## Contracts touched

- API: none directly (action-runner atom, not an HTTP endpoint).
- DB: none (uses existing `action_runs`/`provider_calls`/`artifacts`/event tables; no migration).
- Config:
  - `configs/kernel/schemas/score_match_{input,output}.schema.json` (now strict).
  - `configs/kernel/products/kernel_demo/action_configs.yaml`
    (`kernel_demo.score_match_by_rubric_v1` added).
  - `configs/kernel/products/kernel_demo/prompts.yaml` (`kernel_demo.score_match_by_rubric.v1`
    added).
  - `configs/kernel/products/kernel_demo/prompts/score_match_by_rubric.v1.md` (new).
  - `tests/fixtures/provider/fake_provider_outputs/kernel_demo.score_match_by_rubric_v1.json` (new).
- Events: none new (existing `action.*`/`provider.*`/`artifact.*` event types).
- Frontend: none (no OpenAPI/type-shape change).

## Implementation steps

- [x] Design the strict input/output JSON schemas (`text_a`/`text_b`/`rubric[]` ->
      `criterion_scores[]`/`score`/`strengths[]`/`gaps[]`); close outer/nested objects with
      `additionalProperties: false`; `weight` constrained to `exclusiveMinimum: 0` (no upper bound
      — see decision log).
- [x] Write `ScoreMatchByRubricInputValidator` (duplicate `rubric[*].id` rejection) and
      `ScoreMatchByRubricCrossValidator` (exists+unique+exhaustive criterion mapping + weighted-
      aggregate recompute/tolerance).
- [x] Write the prompt `score_match_by_rubric.v1.md`, incl. the weighted-average rounding
      instruction and an explicit chain-of-thought prohibition on `rationale`.
- [x] Register action definition/action_configs.yaml/prompts.yaml/fake-provider fixture; wire both
      validators into production `output_cross_validators`/`input_validators` in
      `apps/platform-worker/.../composition.py`.
- [x] Add schema fixture tests (`test_score_match_by_rubric_schema.py`): minimal/full valid,
      missing required, unexpected property (top-level and nested rubric/criterion_scores items),
      empty `rubric`/`criterion_scores`, non-positive `weight`, out-of-range scores.
- [x] Add `TestScoreMatchByRubricInputValidator`/`TestScoreMatchByRubricCrossValidator` unit tests
      and ActionRunner deterministic fake-provider execution + validation-retry
      (provider-call-accounting) tests.
- [x] Update `docs/architecture/action-model.md` with the finalized A02 contract shape and
      `generate-docs` regen.
- [x] `/code-review --high` round 1: fix the `NaN`-overflow aggregate bypass (critical), extract
      the shared `_reject_duplicate_ids` helper, cross-reference the tolerance constant with the
      prompt's rounding instruction (plus a pinning test), and accumulate `total_weight` in the
      existing rubric loop instead of re-summing `rubric_weights.values()`.
- [x] Add this execution plan (round 1 review also flagged its absence, matching the same
      per-ticket gap ANY-259 hit first).
- [x] `/code-review --high` round 2 (findings unverified, orchestrator stopped before Phase 2):
      fix the `total_weight`/`rubric_weights` desync the round-1 in-loop-accumulate change
      introduced — a duplicate rubric `id` inflated `total_weight` past what the deduplicated
      `rubric_weights` numerator actually used. Reverted to summing `rubric_weights.values()` after
      the loop and added a regression test exercising the cross-validator directly (bypassing
      `ScoreMatchByRubricInputValidator`, which masks this in production wiring). Deleted
      `TestRejectDuplicateIdsSharedHelper`, confirmed fully redundant with existing
      `TestExtractStructuredFieldsInputValidator`/`TestScoreMatchByRubricInputValidator` coverage.
      Declined the round-2 "reuse `_reject_duplicate_ids` in the cross-validator" suggestion: that
      helper raises `ActionInputValidationError`, but the cross-validator must raise
      `StructuredOutputValidationError` to trigger PydanticAI retries — reusing it as proposed would
      swap exception types and break retry-on-duplicate-criterion-id.
- [x] Final `python scripts/agent/runner.py generate-docs --check` / `quick-check` /
      `postgresql-check` pass.

## Validation

- [x] `uv run pytest packages/backend/platform-actions/tests -q` (full package: schema +
      cross-validation + registration tests)
- [x] `uv run pytest packages/backend/platform-core/tests/unit/test_action_runner.py -k
      "score_match or duplicate_rubric" -q` (postgres-marked; run against a throwaway Docker
      Postgres container in this sandbox, expected to run against CI's managed instance too)
- [x] `python scripts/agent/runner.py validate-configs`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py validate-docs`
- [x] `python scripts/agent/runner.py generate-docs --check`
- [x] `python scripts/agent/runner.py quick-check`
- [x] `python scripts/agent/runner.py postgresql-check` — run against a throwaway Docker Postgres
      container in this sandbox (no local Postgres by default); not run against CI's managed
      instance

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-14 | Aggregate rounding tolerance fixed at `0.5` points on the 0–100 scale | The ticket leaves the exact tolerance undefined; no prior numeric recompute/tolerance precedent exists in `cross_validation.py` (every earlier cross validator does membership/bounds/regex checks). `0.5` covers the model rounding a weighted average to the nearest whole point, matching the prompt's explicit rounding instruction — pinned by a dedicated test reading the prompt file so the two can't drift apart silently. |
| 2026-08-14 | `rubric[*].weight` left with only `exclusiveMinimum: 0`, no upper bound in the schema | Round 1 review's critical finding (extreme weights overflowing float64 to `inf`/`NaN` and silently bypassing the aggregate check) was fixed at the arithmetic level instead — an explicit `math.isfinite(expected_score)` guard rejects any non-finite recomputed aggregate regardless of how it got there, which closes the hole without picking an arbitrary weight ceiling the ticket doesn't specify. |
| 2026-08-14 | Extracted `_reject_duplicate_ids(items, id_field=..., error_label=...)` and had both `ExtractStructuredFieldsInputValidator` (A01) and `ScoreMatchByRubricInputValidator` (A02) call it | Round 1 review found the new A02 validator was a near line-for-line copy of the existing A01 one (same isinstance guards, seen-set, error-message shape, differing only in field names). Two call sites is the point this repo's own "three similar lines is better than a premature abstraction" guidance stops applying, since the duplicated surface is a multi-line control-flow rule, not a few standalone lines, and a third atom (A03 `score_multidimensional_axes`, ANY-257) is likely to want the same rule next. |
| 2026-08-14 | Reverted `total_weight` to `sum(rubric_weights.values())` after the loop, undoing round 1's in-loop accumulation | Round 2 review (finder-only, unverified) caught that accumulating `total_weight` alongside `rubric_weights` inside the same loop double-counts a duplicate rubric `id` in the denominator while the dict numerator silently deduplicates it (last write wins) — a real desync, currently unreachable in prod only because `ScoreMatchByRubricInputValidator` always runs first and rejects duplicate ids, but not something the cross-validator class should rely on an external caller to prevent. |
| 2026-08-14 | Did not reuse `_reject_duplicate_ids` inside `ScoreMatchByRubricCrossValidator`'s `criterion_scores` duplicate check, despite round 2 review suggesting it | The helper raises `ActionInputValidationError` (correct for a pre-provider-call input validator); this is a post-provider-call cross-validator, which must raise `StructuredOutputValidationError` so PydanticAI treats a duplicate `criterion_id` as retryable. Swapping in the shared helper as proposed would change the exception type and silently break that retry path. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-14 | Implemented strict input/output schemas, both validators, prompt, config wiring, fake-provider fixture, and full test coverage; `quick-check`/`validate-configs`/`validate-architecture`/`validate-docs`/`generate-docs --check`/`postgresql-check` (Docker Postgres) all clean | Address round 1 `/code-review --high` findings |
| 2026-08-14 | Fixed the critical `NaN`-overflow aggregate bypass, accumulated `total_weight` inline instead of re-summing, extracted the shared `_reject_duplicate_ids` helper, cross-referenced the tolerance constant with the prompt's rounding instruction plus a pinning test, added this execution plan | Re-run full validation suite and push |
| 2026-08-14 | Round 2 `/code-review --high` (finder-only, orchestrator stopped before verify): fixed the `total_weight`/`rubric_weights` duplicate-id desync round 1's accumulate-in-loop change introduced (Angle A, confirmed real by independent read), deleted the fully redundant `TestRejectDuplicateIdsSharedHelper`, declined the unsafe "reuse `_reject_duplicate_ids`" suggestion (wrong exception type for a cross-validator), left the remaining cosmetic/debatable findings (schema weight ceiling, prompt-substring pinning-test brittleness, comment length, per-scenario test-class granularity, per-retry recompute cost) unaddressed by explicit user choice | None outstanding |
| 2026-08-14 | Direct-call hardening pass (code-review-style inline comment): guarded `ScoreMatchByRubricCrossValidator` against a non-string/unhashable `criterion_id` and a zero `total_weight` reaching the division, both only reachable via a direct unit-test call bypassing schema validation (see decision log); added 5 regression tests for previously-uncovered error branches; declined a `ClassVar` nitpick in `test_score_match_by_rubric_schema.py` as inapplicable — this repo's ruff `select` list omits `RUF` and no CI/`runner.py` step invokes ruff | None outstanding |
| 2026-08-14 | Merged `main` (ANY-260), which split the monolithic `cross_validation.py` into a `cross_validation/` package (one module per atom) and, in the same refactor, inlined each validator's duplicate-id check instead of sharing `_reject_duplicate_ids` (that helper no longer exists anywhere in the new layout). The conflict resolution on `cross_validation.py`/`test_cross_validation.py` dropped `ScoreMatchByRubricInputValidator`/`ScoreMatchByRubricCrossValidator` entirely, leaving `composition.py` and `test_cross_validation.py` importing names the package no longer exported (would fail at import time). Restored both classes as `cross_validation/score_match_by_rubric.py`, following the new package's established inline-duplicate-check style (matching `extract_structured_fields.py`) rather than reintroducing the now-removed shared helper; re-exported both names from `cross_validation/__init__.py`. `quick-check` (602 passed), `validate-configs`, `validate-architecture`, `validate-docs`, and `generate-docs --check` all clean post-restore | None outstanding |

## Open questions

- None.

## Follow-up debt

- `docs/architecture/action-model.md`'s A02 section and this plan both hardcode the `0.5`-point
  tolerance value; if a later ticket changes the prompt's rounding granularity, both need a manual
  update alongside the `_SCORE_MATCH_AGGREGATE_TOLERANCE` constant (the pinning test only catches a
  wording change in the prompt itself, not a matching doc/plan edit).
- Same pre-existing pattern as ANY-259: most of `text_score_match_by_rubric.py`'s module-level
  constants (`INPUT_SCHEMA_REF`, `OUTPUT_SCHEMA_REF`, `KERNEL_DEMO_PROMPT_REF`,
  `FAKE_PROVIDER_FIXTURE_ID`) are never imported elsewhere — shared by every sibling
  `definitions/*.py` file, not specific to this atom; not fixed here to avoid an unrelated
  repo-wide diff.
- Round 2 review raised several unverified, debatable findings left unaddressed by explicit user
  choice: no upper bound on `rubric[*].weight` in the schema (would let a schema `maximum` replace
  the `math.isfinite` overflow guard, its comment, and its dedicated test, at the cost of an
  equally arbitrary weight ceiling the ticket doesn't specify); `TestScoreMatchByRubricAggregateToleranceMatchesPrompt`
  pins tolerance-to-prompt sync via a literal prose substring match, which is brittle to harmless
  prompt copyedits and blind to a rounding-granularity change that keeps the same phrase; the
  11-line derivation comment above `_SCORE_MATCH_AGGREGATE_TOLERANCE`; `rubric_weights`/`total_weight`
  recomputed from scratch on every PydanticAI retry attempt against the same unchanged
  `input_payload['rubric']`; and `TestScoreMatchByRubricCrossValidatorOverflow` living in its own
  one-test class instead of a method on `TestScoreMatchByRubricCrossValidator`.
