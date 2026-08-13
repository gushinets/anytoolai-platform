# Execution Plan: ANY-254 A05 text.generate_clarifying_questions Contract And Runtime

## Status

- State: completed
- Owner: agent
- Created: 2026-08-12 (retroactive — see decision log)
- Last updated: 2026-08-13
- Review date: 2026-08-13
- Next action: none; merged (`6927658`) and Done in Linear. Plan closed and moved to
  `docs/exec-plans/completed/` (ANY-37 parent-DoD verification pass).
- Blocker: none

## Goal

Implement the product-neutral `text.generate_clarifying_questions` atom (legacy A05
`generate_questions`) as a strict, independently runnable JSON-schema contract — finalized-A04
`issues[]`/`context`/`target_audience`/optional `max_questions` in, `questions[]` out — executed
through the existing `StructuredLlmActionExecutor`/`ProviderGateway`/`ActionRunner`, reachable
through a real configured workflow/scenario, so ANY-218 can count it toward 11/11 without a
placeholder/smoke qualification.

## Scope

### In scope

- Strict, closed (`additionalProperties: false`) input/output JSON schemas replacing the previous
  fully-permissive placeholders; `issues[]` matches the finalized A04 `issue_detection_output`
  item shape exactly (ANY-251).
- `GenerateClarifyingQuestionsCrossValidator`: `source_issue_index` bounds-check against
  `len(issues)`, deterministic ordering (priority, then source index), `max_questions` cap —
  constraints the static output schema cannot express.
- Product-neutral prompt (`generate_clarifying_questions.v1.md`) and
  `kernel_demo.generate_clarifying_questions_v1` product-level action config/fake-provider
  fixture.
- Deterministic fake-provider execution through `ActionRunner` fed the literal finalized-A04
  issue shape (proves the direct A04→A05 mapping without an adapter step), validated output
  artifact with action/provider/artifact event lineage, explicit empty-`questions` success case,
  and a validation-retry proof through `StructuredLlmActionExecutor`.
- A real configured workflow (`kernel_demo.detect_questions_v1`) and scenario
  (`kernel_demo.detect_questions_smoke_v1`), registered in the `kernel_demo` product definition,
  chaining `detect_issues.output.issues` directly into this action's `issues` input through the
  config-driven `WorkflowRunner` mapping engine — not just a hand-built `ActionRunner` call.
- Focused platform-core/platform-actions test coverage plus config/architecture/docs/full-check
  gates.

### Out of scope

- The sibling A20a atoms (`text.compose_reply` / ANY-252, `document.generate_from_template` /
  ANY-253).
- A real (non-fake) LLM provider adapter for this or any atom.
- Graceful workflow-level degrade when `detect_issues` legitimately returns zero issues (see
  Follow-up debt).

## Relevant docs

- `docs/architecture/action-model.md` — `A05 generate_questions | text.generate_clarifying_questions`
  mapping row (line 56) verified unchanged since scaffold; no per-atom contract-shape section
  exists for any Wave 1 atom to update.
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`

## Contracts touched

- API: none directly (action-runner atom); the new scenario is reachable through the existing
  `/v1/products/{product_id}/scenarios/{scenario_id}/start` route once registered in
  `product.yaml`.
- DB: none (existing `action_runs`/`provider_calls`/`artifacts`/`jobs`/event tables; no migration).
- Config: `configs/kernel/schemas/generate_questions_{input,output}.schema.json` (now strict),
  `configs/kernel/products/kernel_demo/{prompts,action_configs,workflows,scenarios,product}.yaml`
  (new `generate_clarifying_questions_v1` entries, `detect_questions_v1` workflow,
  `detect_questions_smoke_v1` scenario), new prompt
  `configs/kernel/products/kernel_demo/prompts/generate_clarifying_questions.v1.md`,
  `tests/fixtures/provider/fake_provider_outputs/kernel_demo.generate_clarifying_questions_v1.json`
  (new; trimmed to 1 question so the real chained scenario stays in-bounds against
  `detect_issues_v1.json`'s 1-issue fixture).
- Events: none new (existing `action.*`/`provider.*`/`artifact.*`/`workflow.*` event types).
- Frontend: none.

## Implementation steps

- [x] Design the input/output JSON schemas (`issues[]` matching finalized A04 exactly,
      `context`/`target_audience` required non-empty, `max_questions` 1–10 default 5); close outer
      schemas with `additionalProperties: false`.
- [x] Write the product-neutral prompt `generate_clarifying_questions.v1.md`.
- [x] Add the `kernel_demo.generate_clarifying_questions_v1` product-level action config and
      prompt registration.
- [x] Add the deterministic fake-provider fixture.
- [x] Add `GenerateClarifyingQuestionsCrossValidator` and register it in the production
      composition root (`apps/platform-worker/.../composition.py`) and in the test-side
      `_build_runner` helpers used by `test_action_runner.py`/`test_structured_llm_executor.py`.
- [x] Add ActionRunner tests: direct finalized-A04-shape execution with full event lineage, and an
      explicit empty-`questions` success case through a real fake-provider path
      (`EmptyQuestionsFakeAdapter`).
- [x] Add a validation-retry proof through `StructuredLlmActionExecutor` (out-of-bounds
      `source_issue_index` → deterministic physical retry).
- [x] Add focused schema/cross-validator boundary tests (missing/unexpected properties,
      enum/range violations, bounds/order/cap violations, malformed output).
- [x] Wire the atom into a real workflow (`kernel_demo.detect_questions_v1`) and scenario
      (`kernel_demo.detect_questions_smoke_v1`), registered in `product.yaml`, proving the direct
      `steps.detect_issues.output.issues` → this action's `issues` mapping through the real
      `WorkflowRunner` config engine (team-lead review #1, #2).
- [x] Regenerate generated action/config documentation (`generate-docs --check`).
- [x] Add this execution plan (retroactive — see decision log).
- [x] Final `full-check` pass.

## Validation

- [x] `uv run pytest packages/backend/platform-actions/tests -k "clarifying_questions or generate_questions" -q`
- [x] `uv run pytest packages/backend/platform-core/tests/unit/test_action_runner.py -q`
- [x] `uv run pytest packages/backend/platform-core/tests/unit/test_config_loader.py -q`
- [x] `uv run pytest packages/backend/platform-core/tests/unit/test_workflow_mappings.py -q`
- [x] `uv run pytest apps/platform-api/tests/test_runtime_config.py -q`
- [x] `python scripts/agent/runner.py generate-docs --check`
- [x] `python scripts/agent/runner.py full-check` (final pass: 424 passed / 352 deselected +
      vitest 216/216 + typecheck/build/generate-api-types:check)
- [ ] `python scripts/agent/runner.py postgresql-check` — not run in this environment (no local
      Postgres available); the Postgres-gated tests added by this ticket
      (`test_action_runner.py`, `test_workflow_runner.py`, `test_structured_llm_executor.py`)
      collect correctly and were spot-checked via direct `resolve_step_input()`/`jsonschema`
      invocation instead. Same pre-existing sandbox limitation noted on ANY-252/ANY-253.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-11 | Reused the existing custom-`fake_adapter` pattern (`_build_runner(session, fake_adapter=...)`) for the empty-output test instead of adding a second `action_config_id`/fixture file | Gives the same real event/artifact lineage coverage through `ActionRunner` without expanding the production config with a scenario that doesn't exist in prod |
| 2026-08-12 | Added an isolated `kernel_demo.detect_questions_v1` workflow rather than extending the shared `kernel_demo.extract_detect_report_v1` | The shared workflow is exercised for real via `FakeProviderAdapter` in `apps/platform-api/tests/test_scenario_runtime_api.py`, and its `detect_issues_v1.json` fixture returns only 1 issue; chaining A05 in directly would have tripped the cross-validator's bounds-check against the then-2-question fixture (team-lead review #1) |
| 2026-08-12 | Trimmed `kernel_demo.generate_clarifying_questions_v1.json` from 2 questions to 1 | Keeps the new real-execution scenario in-bounds against `detect_issues_v1.json`'s single issue; the corresponding `test_action_runner.py` assertion was narrowed to match, while its *input* still feeds 2 hand-built issues to keep proving multi-item A04 input validates |
| 2026-08-12 | Registered `kernel_demo.detect_questions_smoke_v1` in `product.yaml` | Team-lead review #2: a scenario present in `scenarios.yaml` but absent from the product's `scenarios` list is unreachable through the public API — `ScenarioRuntimeService._require_product_scenario` rejects it with `ScenarioNotFoundError` |
| 2026-08-12 | Restored `GenerateClarifyingQuestionsCrossValidator`'s production wiring (`composition.py`), both A05 `test_action_runner.py` tests, and the `kernel_demo.generate_clarifying_questions.v1` `prompts.yaml` entry, all silently dropped by the `main` merge (`d307112`) | Same overlapping-insertion merge-drop pattern documented on ANY-252's plan (`64ba09f`): `main`'s ANY-252 additions landed at the same file locations as this ticket's A05 additions, and the merge kept only `main`'s side in three separate files with no conflict markers — the `prompts.yaml` drop broke the entire `kernel_demo` config registry load (`generate-docs --check` failed), not just A05 |
| 2026-08-12 | Removed 4 unused post-merge duplicate spy-gateway classes and de-duplicated `GenerateClarifyingQuestionsCrossValidationRetrySpyGateway` into the shared `_TwoAttemptSpyGateway` in `test_structured_llm_executor.py` | `main`'s merge left both its own consolidated `_FixedResponseSpyGateway`/`_TwoAttemptSpyGateway` helpers and this ticket's now-redundant single-purpose spy classes in the same file (`/code-review` finding); confirmed via grep that the 4 removed classes had zero call sites |
| 2026-08-12 | Added this execution plan retroactively, after implementation and four review rounds had already landed | `AGENTS.md:69-76` requires an execution plan under `docs/exec-plans/active/` for any non-trivial work before coding; `/code-review` flagged that no such plan existed for this branch, mirroring the same gap ANY-252's team-lead review #4 found and closed the same way |
| 2026-08-12 | Extended `output_mapping` to accept `literal:` sources (mirroring `input_mapping`'s existing support), and used it to seed `context.workflow_output = {"questions": []}` from the always-run `detect_issues` step, plus added `when: steps.detect_issues.output.issues` to skip `generate_questions` when empty | Closed the `issues: []` schema-mismatch follow-up debt below: `apply_output_mapping`/`_validate_output_mapping` previously only allowed a step's own output as an output_mapping source, so a skipped step (whose `output_mapping` never runs) had no way to leave a valid final output behind; seeding the default from the *prior*, always-run step sidesteps the need for a new skip-time primitive entirely. Verified via the non-Postgres-gated `test_workflow_mappings.py` (no DB needed to exercise the pure mapping functions) |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-11 | Implemented strict input/output schemas, prompt, `kernel_demo.generate_clarifying_questions_v1` config/fixture, `GenerateClarifyingQuestionsCrossValidator`, and initial ActionRunner tests; added the explicit empty-output ActionRunner test after a review pass flagged its absence | Address team-lead review #1 (atom unreachable through any configured workflow) |
| 2026-08-12 | Added the isolated `detect_questions_v1` workflow/scenario, trimmed the fixture for real-execution bounds coherence, added a `WorkflowRunner`-level mapping proof test | Address team-lead review #2 (scenario not registered in `product.yaml`) |
| 2026-08-12 | Registered `detect_questions_smoke_v1` in `product.yaml`, updated `test_runtime_config.py`'s hardcoded scenario list; while verifying, found and fixed 3 further silent regressions from the `main` merge (`composition.py` cross-validator wiring, both `test_action_runner.py` tests, `prompts.yaml` registry entry) | Address `/code-review` findings on the resulting diff |
| 2026-08-12 | Removed dead/duplicate spy-gateway classes in `test_structured_llm_executor.py`; added this execution plan | Confirm `full-check` is green end-to-end and hand off remaining `issues: []` workflow gap as documented follow-up debt |
| 2026-08-12 | Closed the `issues: []` follow-up debt: extended `output_mapping` to accept `literal:` sources and used it to seed a `{"questions": []}` default from `detect_issues`, added a `when:` skip guard on `generate_questions`, added coverage in `test_workflow_mappings.py` | None outstanding |
| 2026-08-13 | Merged as `6927658`; ticket confirmed Done in Linear during the ANY-37 parent-DoD verification pass | None — plan closed and moved to `docs/exec-plans/completed/` |

## Open questions

- None outstanding.

## Follow-up debt

- None outstanding. The `issues: []` graceful-degrade gap (previously documented here) is closed
  — see the 2026-08-12 decision-log entry on `literal:` output_mapping sources.
