# Execution Plan: ANY-260 A08 text.generate_gap_rewrites Contract And Runtime

## Status

- State: completed
- Owner: agent
- Created: 2026-08-13 (retroactive — see decision log)
- Last updated: 2026-08-14
- Review date: 2026-08-13
- Next action: none; PR #68 merged and no plan-scoped work remains.
- Blocker: none

## Goal

Implement the product-neutral `text.generate_gap_rewrites` atom (A20c3, legacy A08) as a strict,
independently runnable JSON-schema contract — `source_text`/`gap`/`style`/optional `n` (1-5,
default 3) in, `rewrites[]`/`best_pick` out — executed through the existing
`StructuredLlmActionExecutor`/`ProviderGateway`/`ActionRunner`, following the conventions
established by the sibling A20a/A20c atoms (A05/A07/A10).

## Scope

### In scope

- Strict, closed (`additionalProperties: false`) input/output JSON schemas replacing the previous
  permissive placeholders.
- `GapRewritesCrossValidator`: `len(rewrites) == n` (constraint the static schema cannot express
  since `n` lives on the input side), distinctness after whitespace/case normalization, and
  `best_pick` in-bounds — with correct handling of JSON Schema `type: integer` also accepting
  integer-valued floats (`n: 2.0`, `best_pick: 1.0`) for both `n` and `best_pick`.
- Product-neutral prompt (`generate_gap_rewrites.v1.md`) and `kernel_demo.generate_gap_rewrites_v1`
  product-level action config/fake-provider fixture.
- Deterministic fake-provider execution through `ActionRunner`, validated output artifact with
  action/provider/artifact event lineage, and a validation-retry proof through
  `StructuredLlmActionExecutor`.
- Focused platform-core/platform-actions test coverage plus config/architecture/docs/postgresql
  gates.
- Split the accreted `structured_llm/cross_validation.py` (six unrelated per-atom validators plus
  A07's markdown/HTML helpers in one 431-line file) into a `cross_validation/` package, one module
  per atom, once this ticket's A08 addition made the file's lack of structure hard to navigate.

### Out of scope

- Wiring `text.generate_gap_rewrites` into any Kernel Demo workflow (DoD only requires independent
  ActionRunner runnability, matching ANY-252's precedent for A07).
- The sibling A20a/A20c atoms already implemented on other branches (A05/A07/A10).
- A dynamic per-`n` fake-provider fixture-selection mechanism. The static demo fixture always
  returns exactly 3 rewrites (the schema's default `n`), so any caller-requested `n != 3` is
  unsatisfiable against the demo path and fails cross-validation on the single physical call
  `default_fake_provider_v1` allows. Building dynamic fixture selection would touch the shared
  `FakeProviderAdapter`/executor used by every atom — disproportionate to this ticket's scope, and
  the same latent limitation already exists for A01/A04/A09, just masked by their more permissive
  cross-validators. Closed instead by a regression test proving the failure is safe and
  deterministic (see Validation).

## Relevant docs

- `docs/architecture/action-model.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`

## Contracts touched

- API: none (action-runner atom, not an HTTP endpoint).
- DB: none (existing `action_runs`/`provider_calls`/`artifacts`/event tables; no migration).
- Config: `configs/kernel/schemas/generate_gap_rewrites_{input,output}.schema.json` (now strict),
  `configs/kernel/products/kernel_demo/{prompts,action_configs}.yaml` (new
  `generate_gap_rewrites_v1` entries), new prompt
  `configs/kernel/products/kernel_demo/prompts/generate_gap_rewrites.v1.md`,
  `tests/fixtures/provider/fake_provider_outputs/kernel_demo.generate_gap_rewrites_v1.json` (new).
- Events: none new (existing `action.*`/`provider.*`/`artifact.*` event types).
- Frontend: none.

## Implementation steps

- [x] Design the input/output JSON schemas (`source_text`/`gap`/`style` enum/optional `n` 1-5
      default 3 -> `rewrites[]`/`best_pick`); close outer schemas with `additionalProperties: false`.
- [x] Write the product-neutral prompt `generate_gap_rewrites.v1.md`.
- [x] Add the `kernel_demo.generate_gap_rewrites_v1` product-level action config and prompt
      registration.
- [x] Add the deterministic fake-provider fixture (3 distinct rewrites, `best_pick: 2`).
- [x] Add `GapRewritesCrossValidator` and register it in the production composition root
      (`apps/platform-worker/.../composition.py`) and the test-side `_build_runner`
      helpers used by `test_action_runner.py`/`test_workflow_runner.py`/
      `test_structured_llm_executor.py`.
- [x] Add ActionRunner tests: deterministic execution with full event lineage.
- [x] Add a validation-retry proof through `StructuredLlmActionExecutor`.
- [x] Add focused schema/cross-validator boundary tests (count mismatch, duplicate rewrites after
      normalization, `best_pick` out of bounds, malformed output).
- [x] Round 1 `/code-review`: fix `n`/`best_pick` integer-valued-float coercion (`_coerce_integer_valued`
      helper) and consolidate the missing-output guard behind `_require_output` across all three
      pre-existing cross-validators, not only the new one.
- [x] Round 2 `/code-review`: reuse `_coerce_integer_valued` for A01's `_FIELD_TYPE_CHECKS["integer"]`
      (same bug class left unfixed); centralize the default `n=3` behind `GAP_REWRITES_DEFAULT_N`
      with a schema-vs-code consistency test; fix a missing trailing newline in the input schema
      file.
- [x] Round 3 `/code-review`: add a regression test proving the fake-provider demo path fails
      safely and deterministically (single physical call, clean `StructuredOutputValidationError`,
      `action_run.status == "failed"`) for any `n` other than the fixture's fixed 3, converting an
      unverified risk into intentional, contract-compliant, tested behavior.
- [x] Split `cross_validation.py` into `cross_validation/` (one module per atom + `_shared.py`),
      `__init__.py` re-exporting the same public names so no call site changed.
- [x] Regenerate generated action/config documentation (`generate-docs --check`).
- [x] Add this execution plan (retroactive — see decision log).
- [x] Final `postgresql-check` pass.

## Validation

- [x] `uv run pytest packages/backend/platform-actions/tests -q`
- [x] `uv run pytest packages/backend/platform-core/tests/unit -q`
- [x] `uv run pytest apps/platform-worker/tests -q`
- [x] `python scripts/agent/runner.py validate-configs`
- [x] `python scripts/agent/runner.py generate-docs --check`
- [x] `python scripts/agent/runner.py doctor`
- [x] `python scripts/agent/runner.py postgresql-check` (ephemeral local `postgres:16` Docker
      container, `postgresql+psycopg://` URL matching CI's `backend.yml`; full pass after every
      review round and again after the merge from `main` and the `cross_validation` package split)
- [x] `test_action_runner_generate_gap_rewrites_fails_safely_for_non_default_n` — dedicated
      regression proving the round-3 out-of-scope decision (no dynamic fixture selection) resolves
      to a safe, single-physical-call, deterministic `StructuredOutputValidationError` rather than
      a silent success, a retry hang, or an unhandled crash.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-12 | Coerce integer-valued floats (`2.0`) for `n` and `best_pick` via a shared `_coerce_integer_valued` helper instead of a bare `isinstance(x, int)` check | JSON Schema `type: integer` accepts integer-valued floats and the `jsonschema` library does not coerce them; a bare `isinstance` check silently fell back to the default `n` or rejected a valid `best_pick`, both confirmed by `/code-review` round 1 |
| 2026-08-12 | Reused the same helper for A01's pre-existing `_FIELD_TYPE_CHECKS["integer"]` | `/code-review` round 2 found the identical bug class already present and unfixed in A01's field-type check, which predates this ticket but shares the same root cause |
| 2026-08-12 | Centralized the default `n=3` behind `GAP_REWRITES_DEFAULT_N`, asserted equal to the schema's declared `default` by a dedicated test | The value was independently hardcoded in the schema, the prompt, and the cross-validator; `/code-review` round 2 flagged the silent-drift risk of three independent sources of truth |
| 2026-08-12 | Did not build dynamic per-`n` fake-provider fixture selection; added a safe-failure regression test instead | `/code-review` round 3 found the static fixture (fixed at 3 rewrites) makes any `n != 3` request unsatisfiable through the demo path; re-architecting the shared `FakeProviderAdapter` to select fixtures by input was out of proportion to this ticket and would affect every atom, so the fix converts the risk into verified, intentional, contract-compliant failure behavior instead |
| 2026-08-13 | Split `structured_llm/cross_validation.py` into a `cross_validation/` package, one module per atom, on explicit request rather than as part of the original implementation | The file had accreted to six unrelated per-atom validators (A01/A04/A05/A07/A08) plus A07's markdown/HTML detection helpers in one 431-line module; `__init__.py` re-exports the same public names so the change is purely organizational — no call site (`composition.py` or the four test files that import from it) needed to change |
| 2026-08-13 | Added this execution plan retroactively, after implementation, three review rounds, and the file split had already landed | `AGENTS.md:69-76` requires an execution plan under `docs/exec-plans/active/` for any non-trivial work before coding; flagged by the user pointing at that requirement, mirroring the same gap ANY-252/ANY-254 found and closed the same way |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-12 | Implemented strict schemas, prompt, `kernel_demo.generate_gap_rewrites_v1` config/fixture, `GapRewritesCrossValidator`, and ActionRunner/executor/schema test coverage | Address `/code-review` round 1 findings |
| 2026-08-12 | Fixed integer-valued-float coercion for `n`/`best_pick` and consolidated `_require_output` across all cross-validators | Address `/code-review` round 2 findings |
| 2026-08-12 | Fixed A01's same coercion bug, centralized `GAP_REWRITES_DEFAULT_N`, fixed a missing trailing newline in the input schema | Address `/code-review` round 3 finding |
| 2026-08-12 | Added the safe-failure-for-non-default-`n` regression test; merged `main` (brought in ANY-254's A05 atom) with no conflicts; verified full test suite + `postgresql-check` + `generate-docs --check` still pass | None outstanding from implementation |
| 2026-08-13 | Split `cross_validation.py` into a `cross_validation/` package, one module per atom, on request; re-verified full test suite + `postgresql-check` + `generate-docs --check`; added this execution plan and ran `doctor` | None outstanding |

## Open questions

- None outstanding.

## Follow-up debt

- None outstanding. The fake-provider fixed-`n=3` fixture limitation is documented as an accepted,
  tested, out-of-scope trade-off above (shared by A01/A04/A09), not open debt specific to this
  ticket.
