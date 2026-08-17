# Execution Plan: ANY-257 A20b3. A03 text.score_multidimensional_axes Contract And Runtime

## Status

- State: completed
- Owner: agent
- Created: 2026-08-14
- Last updated: 2026-08-17
- Review date: 2026-08-14
- Next action: none; PR #73 merged and no plan-scoped work remains.
- Blocker: none

## Goal

Implement the product-neutral `text.score_multidimensional_axes` atom (legacy A03 `score_multidim`)
as a strict, independently runnable JSON-schema contract — `text`/`axes[]` in,
`scores[]`/`dominant_axes[]`/`weakest_axes[]` out — executed through the existing
`StructuredLlmActionExecutor`/`ProviderGateway`/`ActionRunner`, so ANY-218 can count this atom
toward 11/11 without a placeholder/smoke qualification.

## Scope

### In scope

- Strict, closed (`additionalProperties: false`) input/output JSON schemas replacing the previous
  fully-permissive placeholders (`score_multidim_{input,output}.schema.json`).
- `ScoreMultidimensionalAxesInputValidator`: rejects duplicate `axes[*].id` before any provider
  call (JSON Schema can't express partial-key uniqueness); shares the `_reject_duplicate_ids`
  helper extracted alongside this change with `ExtractStructuredFieldsInputValidator`.
- `ScoreMultidimensionalAxesCrossValidator`: enforces `scores` maps exactly once onto `axes`
  (exists + unique + exhaustive), then recomputes `dominant_axes`/`weakest_axes` outside the model
  response as the tie-preserving, input-order set of axis ids at the max/min reported score and
  rejects any mismatch (no numeric aggregate to recompute here, unlike sibling A02 — direct
  equality against the model's own reported per-axis scores).
- Product-neutral prompt (`score_multidimensional_axes.v1.md`) instructing the model to report
  every axis tied for the max/min score, in input order.
- Registration: `kernel_demo` `action_configs.yaml`/`prompts.yaml`, deterministic fake-provider
  fixture, and production `output_cross_validators`/`input_validators` wiring in
  `apps/platform-worker/.../composition.py`. (The action definition YAML and `schemas.yaml` entry
  already existed as placeholders pointing at the now-strict schema files.)
- Schema/cross-validation/ActionRunner test coverage plus config/architecture/docs/quick-check
  gates.

### Out of scope

- The sibling A20b atoms (`text.compare_and_classify` / ANY-255, `text.score_match_by_rubric` /
  ANY-256) — neither is merged to `main` yet; this branch does not depend on or rebase onto them.
- Any product-specific axis meaning, taxonomy, or weighting scheme (Ethos/Pathos/Logos,
  AI-cliché-detection axes, etc.) — explicitly MVP-B scope per the parent ANY-49 issue. `weight` is
  accepted and passed through the schema but never read by the platform contract.

## Relevant docs

- `docs/architecture/action-model.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- Sibling atoms' cross-validator shape (not yet merged, referenced for pattern only):
  `ScoreMatchByRubricCrossValidator` (weighted-aggregate recompute + tolerance) and
  `CompareAndClassifyCrossValidator` (exists/unique/exhaustive mapping, no aggregate) — this atom's
  cross-validator is closest to the latter, plus a new tie-preserving dominant/weakest recompute
  that has no prior precedent in this module.

## Contracts touched

- API: none directly (action-runner atom, not an HTTP endpoint).
- DB: none (uses existing `action_runs`/`provider_calls`/`artifacts`/event tables; no migration).
- Config:
  - `configs/kernel/schemas/score_multidim_{input,output}.schema.json` (now strict).
  - `configs/kernel/products/kernel_demo/action_configs.yaml`
    (`kernel_demo.score_multidimensional_axes_v1` added).
  - `configs/kernel/products/kernel_demo/prompts.yaml`
    (`kernel_demo.score_multidimensional_axes.v1` added).
  - `configs/kernel/products/kernel_demo/prompts/score_multidimensional_axes.v1.md` (new).
  - `tests/fixtures/provider/fake_provider_outputs/kernel_demo.score_multidimensional_axes_v1.json`
    (new).
- Events: none new (existing `action.*`/`provider.*`/`artifact.*` event types).
- Frontend: none (no OpenAPI/type-shape change).

## Implementation steps

- [x] Design the strict input/output JSON schemas (`text`/`axes[]` ->
      `scores[]`/`dominant_axes[]`/`weakest_axes[]`); close outer/nested objects with
      `additionalProperties: false`; `axes[*].weight` optional, `exclusiveMinimum: 0` when present.
- [x] Extract `_reject_duplicate_ids` helper (generalized from `ExtractStructuredFieldsInputValidator`'s
      inline duplicate-name check) and write `ScoreMultidimensionalAxesInputValidator` on top of it.
- [x] Write `ScoreMultidimensionalAxesCrossValidator` (exists+unique+exhaustive axis mapping +
      tie-preserving, input-order dominant/weakest recompute and exact-match check).
- [x] Write the prompt `score_multidimensional_axes.v1.md`, incl. the tied-axis reporting
      instruction and an explicit chain-of-thought prohibition on `commentary`.
- [x] Register `action_configs.yaml`/`prompts.yaml`/fake-provider fixture; wire both validators
      into production `output_cross_validators`/`input_validators` in
      `apps/platform-worker/.../composition.py`.
- [x] Add schema fixture tests (`test_score_multidimensional_axes_schema.py`): minimal/full valid,
      missing required, unexpected property (top-level and nested axes/scores items), empty
      `axes`/`scores`/`dominant_axes`/`weakest_axes`, non-positive `weight`, out-of-range scores,
      tied-dominant-axes-allowed.
- [x] Add `TestScoreMultidimensionalAxesInputValidator`/`TestScoreMultidimensionalAxesCrossValidator`
      unit tests (incl. tied dominant/weakest, wrong order, missing tied entry) and ActionRunner
      deterministic fake-provider execution + validation-retry (provider-call-accounting) tests.
- [x] Update `docs/architecture/action-model.md` with the finalized A03 contract shape and
      `generate-docs` regen.
- [x] Final `python scripts/agent/runner.py generate-docs --check` / `quick-check` /
      `postgresql-check` pass.

## Validation

- [x] `uv run pytest packages/backend/platform-actions/tests -q` (full package: schema +
      cross-validation + registration tests)
- [x] `python scripts/agent/runner.py validate-configs`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py validate-docs`
- [x] `python scripts/agent/runner.py generate-docs --check`
- [x] `python scripts/agent/runner.py quick-check` (551 passed)
- [x] `python scripts/agent/runner.py postgresql-check` — run against a throwaway Docker Postgres
      container (`postgres:16-alpine`) in this sandbox with
      `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL=postgresql+psycopg://...` (the `+psycopg` driver
      suffix is required — `.quick-check-venv` has `psycopg[binary]` per `pyproject.toml`, not
      `psycopg2`, and a bare `postgresql://` URL makes SQLAlchemy default to the psycopg2 dialect
      and fail every postgres-marked test with `ModuleNotFoundError`, unrelated to this change).
      All postgres-marked tests across platform-core/platform-actions/platform-api/platform-worker
      passed; not run against CI's managed instance.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-14 | `axes[*].weight` kept optional with only `exclusiveMinimum: 0`, no upper bound, and never read by the cross-validator | The ticket's Canonical Contract lists `weight` only as optional axis metadata; unlike A02's rubric, A03's Output section has no aggregate field for weight to feed into — axes are explicitly "independent." Accepting-but-ignoring keeps the schema forward-compatible with an MVP-B consumer that wants it, without inventing platform-level weighting semantics the ticket doesn't ask for. |
| 2026-08-14 | `dominant_axes`/`weakest_axes` cross-validated by exact list equality (order-sensitive), no numeric tolerance | Unlike A02's weighted-average recompute (an independently-computed float compared against the model's own aggregate, needing a rounding tolerance), here both sides are pure functions of the model's own already-validated per-axis `scores` — tie-set membership and input order are deterministic given those scores, so exact equality is the correct check, not an approximation. |
| 2026-08-14 | Did not rebase on or import from the unmerged ANY-255/ANY-256 branches; `_reject_duplicate_ids` written fresh in this branch | Per the ticket's own estimate, neither sibling atom is in `main` yet. Depending on either branch would couple this PR's mergeability to branches outside this ticket's control; the helper is small (single generalized loop) and both siblings will naturally converge on it (or a merge conflict will surface the duplication) whichever branch merges first. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-14 | Implemented strict input/output schemas, both validators (with the `_reject_duplicate_ids` extraction done inline rather than deferred to a review round), prompt, config wiring, fake-provider fixture, and full test coverage (schema + cross-validation + ActionRunner retry-ledger) | Run full validation gate suite and address any `/code-review` findings |

## Open questions

- None.

## Follow-up debt

- If ANY-255 or ANY-256 merges first with a differently-named `_reject_duplicate_ids` (e.g. a
  different keyword-arg name), this branch's copy will need a small rebase-time rename to match
  whichever version lands in `main` first — not a functional risk, just a merge-order detail
  flagged by the ticket's own risk note.
