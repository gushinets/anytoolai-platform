# Execution Plan: ANY-255 A20b1. A11 text.compare_and_classify Contract And Runtime

## Status

- State: active
- Owner: agent
- Created: 2026-08-13
- Last updated: 2026-08-13
- Review date: 2026-08-13
- Next action: commit and open PR; run `postgresql-check` against a real PostgreSQL instance
  before merge (not run in this sandbox — see Follow-up debt).
- Blocker: none

## Goal

Implement the product-neutral `text.compare_and_classify` atom (legacy A11 `compare_classify`) as
a strict, independently runnable JSON-schema contract — `subject_text`/`reference_text`/
`categories[]`/`criteria[]` in, `verdict`/`confidence`/`deltas[]`/`rationale` out — executed
through the existing `StructuredLlmActionExecutor`/`ProviderGateway`/`ActionRunner`, so ANY-218 can
count this atom toward 11/11 without a placeholder/smoke qualification. First child ticket of the
A20b Scoring And Classification pack (parent ANY-49; siblings ANY-256/ANY-257).

## Scope

### In scope

- Strict, closed (`additionalProperties: false`) input/output JSON schemas replacing the
  previous fully-permissive placeholders (`compare_classify_{input,output}.schema.json`).
- `CompareAndClassifyInputValidator`: rejects duplicate `criteria[*].id` before any provider
  call (a duplicate id would make output full-coverage matching ambiguous).
- `CompareAndClassifyCrossValidator`: `verdict` must be one of `categories`; every
  `deltas[*].criterion_id` must exist in `criteria`, must not repeat, and `deltas` must cover
  every `criteria[*].id` exactly once (full coverage — resolved open contract question, see
  Decision log).
- Product-neutral prompt (`compare_and_classify.v1.md`) with an explicit chain-of-thought
  prohibition on `rationale` and a note that `confidence` is a relative signal, not a calibrated
  probability.
- Registration: action definition, `schemas.yaml` (pre-existing), `kernel_demo`
  `action_configs.yaml`/`prompts.yaml`, deterministic fake-provider fixture, and production
  `input_validators`/`output_cross_validators` wiring in `apps/platform-worker/.../composition.py`.
- Schema/cross-validation/executor-retry/ActionRunner test coverage plus
  config/architecture/docs/quick-check gates.

### Out of scope

- The sibling A20b atoms (`text.score_match_by_rubric` / ANY-256,
  `text.score_multidimensional_axes` / ANY-257).
- Any product rubric, taxonomy, axis, or provider/runtime implementation detail — stays in MVP-B
  per the parent ANY-49 Definition of Done.

## Relevant docs

- `docs/architecture/action-model.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/exec-plans/active/any-259-a20c2-a09-text-synthesize-angle-contract-and-runtime.md`
  (closest sibling precedent: options/categories-membership cross-validator shape, and the same
  review-driven exec-plan gap raised and fixed there first)
- `plans/ANY-255.md` (Linear issue import + code-review log for this ticket)

## Contracts touched

- API: none directly (action-runner atom, not an HTTP endpoint).
- DB: none (uses existing `action_runs`/`provider_calls`/`artifacts`/event tables; no migration).
- Config:
  - `configs/kernel/schemas/compare_classify_{input,output}.schema.json` (now strict).
  - `configs/kernel/products/kernel_demo/action_configs.yaml`
    (`kernel_demo.compare_and_classify_v1` added).
  - `configs/kernel/products/kernel_demo/prompts.yaml`
    (`kernel_demo.compare_and_classify.v1` added).
  - `configs/kernel/products/kernel_demo/prompts/compare_and_classify.v1.md` (new).
  - `tests/fixtures/provider/fake_provider_outputs/kernel_demo.compare_and_classify_v1.json` (new).
- Events: none new (existing `action.*`/`provider.*`/`artifact.*` event types).
- Frontend: none (no OpenAPI/type-shape change).

## Implementation steps

- [x] Design the strict input/output JSON schemas (`subject_text`/`reference_text`/`categories[]`
      (`minItems: 2`, `uniqueItems`)/`criteria[]` (`id`/`description`/optional positive `weight`)
      -> `verdict`/`confidence` (0-1)/`deltas[]` (`criterion_id`/`status` enum/`evidence`)/
      `rationale` (`maxLength: 500`)); close outer/nested objects with `additionalProperties: false`.
- [x] Resolve the open contract question ("is every input criterion mandatory in output.deltas?")
      explicitly with the user rather than defaulting silently — decided: full coverage required.
- [x] Write `CompareAndClassifyInputValidator` (duplicate `criteria[*].id` rejection) and
      `CompareAndClassifyCrossValidator` (categories-membership + deltas existence/uniqueness/
      full-coverage).
- [x] Write the prompt `compare_and_classify.v1.md`, incl. chain-of-thought prohibition on
      `rationale` and the non-calibrated-probability note on `confidence`.
- [x] Register action config/prompts.yaml/fake-provider fixture; wire both validators into the
      production `input_validators`/`output_cross_validators` in
      `apps/platform-worker/.../composition.py` (not just the test harness).
- [x] Add schema fixture tests (`test_compare_and_classify_schema.py`): minimal/full valid,
      missing required, unexpected property (top-level and nested), category count/uniqueness,
      criterion weight bounds, delta status enum, confidence bounds, rationale maxLength.
- [x] Add `TestCompareAndClassifyInputValidator`/`TestCompareAndClassifyCrossValidator` unit tests,
      a DB-free executor-level semantic-retry test, and ActionRunner e2e + real-ledger
      validation-retry + input-rejection tests (postgres-marked, mirroring the A07/A09 precedent).
- [x] Update `docs/architecture/action-model.md` with the finalized A11 contract shape; regenerate
      `docs/generated/*`.
- [x] Review round 1: add the missing early-return guard in `CompareAndClassifyCrossValidator` for
      malformed (non-list) `input.criteria`, matching `ExtractStructuredFieldsCrossValidator`'s
      established defensive pattern — otherwise malformed input gets misattributed as an
      output-model defect.
- [x] Review round 2: extract a shared `_reject_duplicate_ids(items, *, id_key, error_label)`
      helper and have both `ExtractStructuredFieldsInputValidator` and
      `CompareAndClassifyInputValidator` delegate to it, removing near-verbatim duplication
      between the two input validators (error-message format preserved exactly).
- [x] Add this execution plan (`AGENTS.md`/CLAUDE.md's "Before coding" section requires one under
      `docs/exec-plans/active/`; missed during initial implementation, caught on explicit request
      to verify docs — same gap the any-259/any-253 precedents already document).
- [ ] Run `python scripts/agent/runner.py postgresql-check` against a real PostgreSQL instance
      (no PostgreSQL available in this sandbox); commit and open PR.

## Validation

- [x] `uv run pytest packages/backend/platform-actions/tests -k "compare_and_classify or cross_validation" -q`
- [x] `uv run pytest packages/backend/platform-core/tests/unit/test_action_runner.py --collect-only -q`
      (postgres-marked; DB unavailable in this sandbox, so only collection — not execution — was
      verified locally; expected to run in CI/against a real Postgres instance)
- [x] `python scripts/agent/runner.py validate-configs`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py generate-docs --check`
- [x] `python scripts/agent/runner.py quick-check` (546 passed, 361 deselected, 0 failed — re-run
      clean after both review-round fixes)
- [ ] `python scripts/agent/runner.py postgresql-check` — not run; no PostgreSQL available in this
      sandbox (see Follow-up debt)

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-13 | `deltas` must cover every `input.criteria` id exactly once (full coverage), not a partial subset | Ticket explicitly flagged this as an open contract question requiring an explicit decision, not a default. Asked the user directly; chosen option matches the atom's goal of comparing against "explicit criteria" with complete evidence, and the existing `ExtractStructuredFieldsCrossValidator` (A01) precedent of requiring full accounting of requested fields |
| 2026-08-13 | Added `CompareAndClassifyInputValidator` (duplicate `criteria[*].id` rejection) as a pre-provider-call input validator, not just a cross-validator concern | Mirrors the A01 `ExtractStructuredFieldsInputValidator` precedent; a duplicate id would make the full-coverage cross-validation check ambiguous (which delta maps to which criterion), so it's better rejected before any provider spend |
| 2026-08-13 | Added an early-return guard in `CompareAndClassifyCrossValidator` for non-list `input.criteria` | Review round 1 (CONFIRMED, low priority): without it, malformed input.criteria left `known_criterion_ids` empty, so any non-empty `output.deltas` was misattributed as a model output defect rather than an input problem. Unreachable in production (schema guarantees `criteria` is a valid array first) but inconsistent with the established `ExtractStructuredFieldsCrossValidator` defensive pattern in the same file |
| 2026-08-13 | Extracted `_reject_duplicate_ids()` shared helper for `ExtractStructuredFieldsInputValidator`/`CompareAndClassifyInputValidator` immediately, rather than deferring to a third occurrence | Review round 2 (CONFIRMED, low priority, non-bug DRY note) recommended waiting for a third such validator; asked the user explicitly given the YAGNI tension, and the user chose to extract now |
| 2026-08-13 | Added this execution plan retroactively | `AGENTS.md`'s "Before coding" section requires one under `docs/exec-plans/active/`; missed during initial implementation (task context came from `plans/ANY-255.md`'s Linear import, not this directory), caught when explicitly asked to verify documentation completeness — same gap the any-259/any-253 exec plans document as a recurring pattern in this series |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-13 | Implemented strict input/output schemas, input validator, cross-validator, prompt, config/composition-root wiring, fake-provider fixture, and full test coverage (schema/unit/executor-retry/ActionRunner); `quick-check` green (545 passed) | Address code review round 1 |
| 2026-08-13 | Review round 1 (CONFIRMED, low priority): added early-return guard in `CompareAndClassifyCrossValidator` for malformed `input.criteria`, plus a regression test; `quick-check` green (546 passed) | Address code review round 2 |
| 2026-08-13 | Review round 2 (CONFIRMED, low priority, non-bug DRY note): extracted shared `_reject_duplicate_ids()` helper, refactored both input validators to use it; `quick-check` still green (546 passed) | Verify documentation completeness on request |
| 2026-08-13 | Caught missing `docs/exec-plans/active/` entry on explicit "check if docs are done" request; added this execution plan | Commit, run `postgresql-check` against a real DB, open PR |

## Open questions

- None.

## Follow-up debt

- The three `pytest.mark.postgresql` ActionRunner tests added for this atom (e2e success,
  real-ledger validation retry, input-validation rejection) were only verified via
  `pytest --collect-only` in this sandbox (no PostgreSQL instance available) — must be executed
  against a real database (`postgresql-check` or CI's managed Postgres job) before merge.
- Unused module constants in `text_compare_and_classify.py` (`INPUT_SCHEMA_REF`,
  `OUTPUT_SCHEMA_REF`, etc. are never imported elsewhere) — pre-existing pattern shared by every
  sibling `definitions/*.py` file (see same note in the any-259 exec plan), not specific to this
  atom; not fixed here to avoid an unrelated repo-wide diff.
