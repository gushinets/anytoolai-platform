# Execution Plan: ANY-259 A20c2. A09 text.synthesize_angle Contract And Runtime

## Status

- State: active
- Owner: agent
- Created: 2026-08-12
- Last updated: 2026-08-12
- Review date: 2026-08-12
- Next action: none outstanding from review; keep in sync with any further review rounds.
- Blocker: none

## Goal

Implement the product-neutral `text.synthesize_angle` atom (legacy A09 `generate_angle`) as a strict,
independently runnable JSON-schema contract — `signals[]`/`objective`/optional `options[]` in,
`angle`/`rationale`/optional `secondary_angle` out — executed through the existing
`StructuredLlmActionExecutor`/`ProviderGateway`/`ActionRunner`, so ANY-218 can count this atom toward
11/11 without a placeholder/smoke qualification.

## Scope

### In scope

- Strict, closed (`additionalProperties: false`) input/output JSON schemas replacing the previous
  fully-permissive placeholders (`synthesize_angle_{input,output}.schema.json`).
- `signals[].value` accepts any JSON type (precedent: `extract_output.schema.json`), with test
  coverage across string/number/bool/null/array/object.
- Options-membership cross-validator (`SynthesizeAngleCrossValidator`): when `options` is non-empty,
  `angle`/`secondary_angle` must be one of them; when `options` is absent/empty, open synthesis is
  allowed with no membership check.
- Product-neutral prompt (`synthesize_angle.v1.md`) with an explicit chain-of-thought prohibition on
  `rationale`.
- Registration: action definition, `schemas.yaml`, `kernel_demo` `action_configs.yaml`/`prompts.yaml`,
  deterministic fake-provider fixture, and production `output_cross_validators` wiring in
  `apps/platform-worker/.../composition.py`.
- Schema/cross-validation/ActionRunner test coverage plus config/architecture/docs/quick-check gates.

### Out of scope

- The sibling A20c atoms (`text.compose_persuasive_text` / ANY-258, `text.generate_gap_rewrites` /
  ANY-260).
- Any product-level persuasion semantics, anti-AI/non-native behavior, or `generate_proposal` —
  explicitly MVP-B scope per the parent ANY-45 issue.

## Relevant docs

- `docs/architecture/action-model.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/exec-plans/active/any-253-a10-document-generate-from-template-contract-and-runtime.md`
  (sibling Wave-1 atom; same review-driven exec-plan gap raised and fixed there first)

## Contracts touched

- API: none directly (action-runner atom, not an HTTP endpoint).
- DB: none (uses existing `action_runs`/`provider_calls`/`artifacts`/event tables; no migration).
- Config:
  - `configs/kernel/schemas/synthesize_angle_{input,output}.schema.json` (now strict).
  - `configs/kernel/products/kernel_demo/action_configs.yaml` (`kernel_demo.synthesize_angle_v1`
    added).
  - `configs/kernel/products/kernel_demo/prompts.yaml` (`kernel_demo.synthesize_angle.v1` added).
  - `configs/kernel/products/kernel_demo/prompts/synthesize_angle.v1.md` (new).
  - `tests/fixtures/provider/fake_provider_outputs/kernel_demo.synthesize_angle_v1.json` (new).
- Events: none new (existing `action.*`/`provider.*`/`artifact.*` event types).
- Frontend: none (no OpenAPI/type-shape change).

## Implementation steps

- [x] Design the strict input/output JSON schemas (`signals[]`/`objective`/optional `options[]` ->
      `angle`/`rationale`/optional `secondary_angle`); close outer/nested objects with
      `additionalProperties: false`.
- [x] Write `SynthesizeAngleCrossValidator` (options-membership) following the
      `DetectIssuesByTaxonomyCrossValidator` pattern.
- [x] Write the prompt `synthesize_angle.v1.md`, incl. explicit chain-of-thought prohibition on
      `rationale`.
- [x] Register action definition/schemas.yaml/action_configs.yaml/prompts.yaml/fake-provider fixture.
- [x] Add schema fixture tests (`test_synthesize_angle_schema.py`): minimal/full valid, all
      `signals[].value` JSON types, missing required, unexpected property (top-level and nested),
      empty `signals`/`objective`/`angle`/`secondary_angle`, duplicate `options`, empty `options` as
      open synthesis.
- [x] Add `TestSynthesizeAngleCrossValidator` cross-validation tests and an ActionRunner
      deterministic fake-provider execution test.
- [x] Remove a duplicate `SynthesizeAngleCrossValidator` class definition left by an interrupted edit
      (review round 1, `ruff --select F811`).
- [x] Register `SynthesizeAngleCrossValidator` in the production `output_cross_validators` in
      `apps/platform-worker/.../composition.py` — it was only wired in the test harness, so the
      cross-validator was a no-op in production (review round 2, critical).
- [x] Extract `_require_output`/`_optional_membership_set` helpers to de-duplicate the
      missing-output guard and membership-set coercion across all three cross-validators (review
      round 2).
- [x] Add the missing trailing newline to `synthesize_angle_input.schema.json` (review round 2).
- [x] Bound rejected-value text embedded in `exc.reason` via `_truncated_repr()` — first applied to
      `SynthesizeAngleCrossValidator`'s `angle`/`secondary_angle` (review round 4), then its unused
      `limit` parameter dropped in favor of a module constant (review round 5), then extended to
      every other model-controlled (output-sourced) interpolation in the file:
      `DetectIssuesByTaxonomyCrossValidator`'s `category_not_in_taxonomy` and
      `ExtractStructuredFieldsCrossValidator`'s `unrequested_field`/`unrequested_missing_field`/
      `field_marked_missing_but_present`/`duplicate_missing_field`/`confidence_for_unpopulated_field`
      (review round 6) — all sourced from `output`, none had a schema `maxLength`, all fed into
      `ModelRetry(exc.reason)` and the persisted debug-artifact metadata unbounded.
- [x] Add this execution plan (raised as a non-blocking observation during the 2026-08-12 AC check,
      then confirmed as an actual per-ticket gap — not a repo-wide pattern — once the sibling
      ANY-253 branch, which added its own exec plan, merged into this one).
- [x] Update `docs/architecture/action-model.md` with the finalized A09 contract shape (team lead #2
      review, P3).
- [x] Final `python scripts/agent/runner.py generate-docs --check` / `full-check` pass and PR.

## Validation

- [x] `uv run pytest packages/backend/platform-actions/tests -k "synthesize_angle or cross_validation" -q`
- [x] `uv run pytest packages/backend/platform-core/tests/unit/test_action_runner.py -k synthesize_angle -q`
      (postgres-marked; skips locally without `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL`, expected to run
      in CI)
- [x] `uv run python scripts/agent/runner.py generate-docs --check`
- [x] `uv run python scripts/agent/runner.py full-check` (after every review round, and again after
      merging `main`/ANY-253)
- [x] `python scripts/agent/runner.py postgresql-check` — run against a throwaway Docker Postgres
      container in this sandbox (no local Postgres by default); not run against CI's managed instance

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-11 | Options-membership enforced via a dedicated cross-validator, not just prompt guidance | The ticket's "define+test behavior when options supplied vs open synthesis" reads as an enforcement requirement, matching the existing `DetectIssuesByTaxonomyCrossValidator` precedent for the same shape of constraint |
| 2026-08-11 | Chain-of-thought prohibition on `rationale` implemented as a prompt instruction only, no runtime heuristic | The ticket frames it as a validation/prompt requirement, not a strict contract; a heuristic detector would be guessing at natural-language structure with no reliable signal |
| 2026-08-11 | Registered `SynthesizeAngleCrossValidator` in the production `composition.py`, not just the test harness | Round 2 review found the validator was only wired in `test_action_runner.py`'s `_build_runner()`; `StructuredLlmActionExecutor` resolves validators via `.get(action_type)` (returns `None` if absent), so the entire cross-validator was a silent no-op in production |
| 2026-08-11 | Extracted `_truncated_repr()` and applied it to every output-sourced (model-controlled) value interpolated into `exc.reason` across all three cross-validators, not just the new one | `angle`/`category`/`values` keys have no schema `maxLength`; the raw rejected value flows unbounded into both the next `ModelRetry` prompt and the persisted debug-artifact metadata. Round 4 found it for `angle`; round 6 found the same class of gap in the two sibling validators this diff already touches |
| 2026-08-12 | Added this execution plan | `AGENTS.md`'s "Before coding" section requires one under `docs/exec-plans/active/`; an earlier AC check treated the gap as a repo-wide pattern affecting the whole A20c/A21 series (no sibling had one at the time), but the ANY-253 merge landed that ticket's own exec plan (added after its own team-lead review flagged the identical gap), making ANY-259 the actual remaining outlier rather than part of an unaddressed pattern |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-11 | Implemented strict input/output schemas, cross-validator, prompt, config wiring, fake-provider fixture, and test coverage (`a6c9dfa`) | Address first code-review pass |
| 2026-08-11 | Fixed duplicate `SynthesizeAngleCrossValidator` class definition (review round 1) | Address round 2 (production wiring gap, DRY duplication, missing newline) |
| 2026-08-11 | Registered the cross-validator in production `composition.py`, extracted `_require_output`/`_optional_membership_set` helpers, added the missing trailing newline (review round 2) | Address round 4 (unbounded `exc.reason` text) |
| 2026-08-11 | Added `_truncated_repr()` and applied it to `angle`/`secondary_angle` (`59deef3`); dropped its unused `limit` parameter (`3dea555`); extended it to `DetectIssuesByTaxonomyCrossValidator`/`ExtractStructuredFieldsCrossValidator` (`8091901`) | Merge `main` and re-verify |
| 2026-08-12 | Merged `main` (pulls in ANY-253); resolved a `test_action_runner.py` conflict preserving both atoms' tests and the full cross-validator registry (`552123f`); re-ran `full-check` clean (358 backend + 216 frontend tests) | Add this execution plan; finish `docs/architecture/action-model.md` and push |
| 2026-08-13 | Addressed team-lead #2 review (P3): documented the finalized A09 contract in `docs/architecture/action-model.md`; re-verified `generate-docs --check`, `full-check`, and `postgresql-check` (Docker Postgres) all clean | Push and open the PR |

## Open questions

- None.

## Follow-up debt

- Unused module constants in `text_synthesize_angle.py` (5 of 6 module-level constants are never
  imported elsewhere) — pre-existing pattern shared by every sibling `definitions/*.py` file, not
  specific to this atom; not fixed here to avoid an unrelated repo-wide diff.