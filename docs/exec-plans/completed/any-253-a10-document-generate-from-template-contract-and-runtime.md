# Execution Plan: ANY-253 A10 document.generate_from_template Contract And Runtime

## Status

- State: active
- Owner: agent
- Created: 2026-08-11
- Last updated: 2026-08-11
- Review date: 2026-08-11
- Next action: none outstanding from review; keep in sync with any further review rounds.
- Blocker: none

## Goal

Implement the product-neutral `document.generate_from_template` atom (legacy A10 `generate_document`)
as a strict, independently runnable JSON-schema contract — `template_ref`/`data`/optional `style` in,
non-empty ordered `sections`/`summary` out — executed through the existing
`StructuredLlmActionExecutor`/`ProviderGateway`/`ActionRunner`, and migrate the Kernel Demo
`extract_detect_report_v1` workflow's `generate_report` step onto it, so ANY-218 can count this atom
toward 11/11 without a placeholder/smoke qualification.

## Scope

### In scope

- Strict, closed (`additionalProperties: false`) input/output JSON schemas replacing the previous
  fully-permissive placeholders (`generate_document_{input,output}.schema.json`).
- `sections[].metadata.kind` bounded to an explicit enum (`heading | paragraph | list | table | note`)
  and required whenever `metadata` is present, so an empty `metadata: {}` is rejected.
- Product-neutral prompt (`generate_report.v1.md`) rewritten for structured `sections`/`summary`
  JSON output instead of free-form markdown.
- Migrating the Kernel Demo `extract_detect_report_v1` workflow's `generate_report` step: consolidate
  `source_text`/`extracted`/`issues` into a `data` object plus a `template_ref` literal, instead of
  flat top-level input-mapping fields.
- Dropping the duplicate product-level `kernel_demo.report_output_v1` schema in favor of the
  workflow's `output_schema_ref` pointing directly at `kernel.schemas.generate_document_output_v1`
  (the `generate_report` step passes its output straight through with no transformation, so the
  duplicate added no value and had drifted out of sync with the repo's own open/strict convention).
- Deterministic fake-provider fixture set (minimal/full valid, missing-required, unexpected-property,
  invalid-enum, malformed-structured-output), ActionRunner event/artifact lineage test, and a
  validation-retry proof through the real `ProviderGateway`/`ProviderCallRepository` DB ledger.
- Focused platform-core/platform-actions test coverage plus config/architecture/docs/quick-check
  gates.

### Out of scope

- The sibling A20a atoms (`text.compose_reply` / ANY-252, `text.generate_clarifying_questions` /
  ANY-254).
- Closing the other still-open Kernel Demo workflow output schemas (`kernel_demo.extract_output_v1`)
  — ANY-217's handoff allowlist-mapping design decision for those is untouched by this change; only
  `report_output_v1` was superseded, because it had become a byte-for-byte duplicate of the atom's
  own strict schema rather than an intentionally softer workflow-level schema.
- Word-count or other deterministic metrics — explicitly required by the issue to be computed outside
  the model response, not part of this contract's runtime.

## Relevant docs

- `docs/architecture/action-model.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/exec-plans/active/any-217-frontend-safe-result-artifact-api.md` (superseded
  `report_output_v1` reference reconciled by this plan — see decision log)

## Contracts touched

- API: none directly (action-runner atom, not an HTTP endpoint); the static OpenAPI doc-example in
  `apps/platform-api/.../routers/runtime_config.py` was updated to stop referencing the removed
  `kernel_demo.report_output_v1`.
- DB: none (uses existing `action_runs`/`provider_calls`/`artifacts`/event tables; no migration).
- Config:
  - `configs/kernel/schemas/generate_document_{input,output}.schema.json` (now strict).
  - `configs/kernel/products/kernel_demo/workflows.yaml` (`generate_report` step's
    `input_mapping` migrated to `data.*`/`literal:`; workflow `output_schema_ref` now points at
    `kernel.schemas.generate_document_output_v1`).
  - `configs/kernel/products/kernel_demo/schemas.yaml` (`kernel_demo.report_output_v1` entry
    removed).
  - `configs/kernel/products/kernel_demo/schemas/report_output.schema.json` (deleted; was a
    byte-for-byte duplicate of the atom's own output schema).
  - `configs/kernel/products/kernel_demo/prompts/generate_report.v1.md` (rewritten).
  - `tests/fixtures/provider/fake_provider_outputs/kernel_demo.generate_report_v1.json`
    (rewritten to structured `response_json`).
- Events: none new (existing `action.*`/`provider.*`/`artifact.*` event types).
- Frontend: `docs/generated/openapi.json` and generated
  `packages/frontend/ce-kit/src/api/generated/platformApi.ts` regenerated (doc-comment example
  only; no type-shape change).

## Implementation steps

- [x] Design the strict input/output JSON schemas (`template_ref`/`data`/optional `style` enum ->
      non-empty `sections[]`/`summary`); close outer schemas with `additionalProperties: false`.
- [x] Rewrite the prompt `generate_report.v1.md` for structured JSON output.
- [x] Migrate the `extract_detect_report_v1` workflow's `generate_report` step input-mapping to a
      `data` object plus `template_ref` literal.
- [x] Register the schemas (kernel level) and drop the duplicate `kernel_demo.report_output_v1`
      product-level schema, pointing the workflow's `output_schema_ref` directly at the atom schema.
- [x] Replace the fake-provider fixture with structured `response_json`.
- [x] Add schema fixture tests (`test_generate_document_schema.py`): minimal/full valid, missing
      required, unexpected property, invalid enum, malformed section, empty `metadata`.
- [x] Add an ActionRunner test proving deterministic execution with full action/provider/artifact
      event lineage.
- [x] Add a validation-retry test through the real `ProviderGateway`/`ProviderCallRepository` DB
      ledger (not only an in-memory spy), asserting on persisted `provider_calls` rows.
- [x] Update `test_workflow_runner.py` assertions for the migrated `generate_report` step
      input/output shape.
- [x] Require `metadata.kind` whenever `sections[].metadata` is present (review fix — an empty
      `metadata: {}` was previously valid).
- [x] Reconcile the stale `kernel_demo.report_output_v1` reference in the ANY-217 exec plan (this
      plan's own review finding).
- [x] Add this execution plan (raised by team-lead review #1 — see decision log).
- [ ] Update `docs/architecture/action-model.md` with the finalized A10 contract shape.
- [ ] Final `python scripts/agent/runner.py generate-docs --check` / `quick-check` /
      `postgresql-check` pass and PR.

## Validation

- [x] `uv run pytest packages/backend/platform-actions/tests/test_generate_document_schema.py -q`
- [x] `uv run pytest packages/backend/platform-core/tests/unit/test_workflow_runner.py -q`
- [x] `uv run pytest packages/backend/platform-core/tests/unit/test_action_runner.py -q`
- [x] `uv run pytest packages/backend/platform-actions/tests/test_structured_llm_executor.py -q`
- [x] `python scripts/agent/runner.py quick-check` (after each review round)
- [x] `python scripts/agent/runner.py postgresql-check` (local Postgres 16 container; covers the
      real-ledger retry test)
- [x] `pnpm -r --if-present generate-api-types:check` (after `openapi.json` regeneration)
- [ ] `python scripts/agent/runner.py generate-docs --check` (final pass before PR)

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-11 | Bound `sections[].metadata` to a single `kind` enum (`heading \| paragraph \| list \| table \| note`) instead of an open object | The issue leaves "explicitly bounded metadata" undefined; a single closed enum is the minimum that satisfies "explicitly bounded" without inventing unrequested per-kind fields |
| 2026-08-11 | Dropped the duplicate `kernel_demo.report_output_v1` product schema; pointed the workflow's `output_schema_ref` directly at `kernel.schemas.generate_document_output_v1` | Code review found the product schema had become a byte-for-byte clone of the atom's own strict schema; the `generate_report` step forwards its output untransformed, so the duplicate added no independent value and broke the repo's own open/strict workflow-schema convention it was originally meant to preserve |
| 2026-08-11 | Also updated the static OpenAPI doc-example (`runtime_config.py`) referencing the removed `report_output_v1` | Found outside the original diff's blast radius while verifying no dangling references remained; left unfixed it would have been a stale doc-example, not a runtime bug |
| 2026-08-11 | Required `metadata.kind` (was previously optional inside an already-optional `metadata` object) | Review found an empty `metadata: {}` was valid, which is a no-op field with no bounded meaning; requiring `kind` whenever `metadata` is present closes that gap |
| 2026-08-11 | Replaced the in-memory spy-gateway validation-retry test with one going through a real `ProviderGateway` + `ProviderCallRepository`, asserting on persisted `provider_calls` rows | Review found the original test used `session = object()` and a bespoke in-memory spy, so it could not catch missing/incorrect ledger rows or events — the same gap ANY-252's team-lead review #2 flagged for that sibling atom |
| 2026-08-11 | Added this execution plan and reconciled the ANY-217 plan's stale `report_output_v1` references, rather than treating them as separate follow-ups | `AGENTS.md:71-78` requires an execution plan under `docs/exec-plans/active/` before non-trivial work; team-lead review #1 additionally flagged that ANY-217's plan still directs future work to preserve a schema this change deleted — fixing only one without the other would leave a second stale source of truth |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-11 | Implemented strict input/output schemas, rewrote prompt and fake-provider fixture, migrated the `generate_report` workflow step to `data`/`template_ref`, added schema/ActionRunner tests (`f80b821`) | Address first code-review pass (duplicate `report_output_v1` schema) |
| 2026-08-11 | Dropped the duplicate `kernel_demo.report_output_v1` schema in favor of a direct `kernel.schemas.generate_document_output_v1` reference; fixed the stale OpenAPI doc-example; regenerated generated docs/API types | Address team-lead review #1 (missing execution plan, stale ANY-217 reference) |
| 2026-08-11 | Required `metadata.kind`; replaced the in-memory spy validation-retry test with a real `ProviderGateway`/ledger-backed one (`ef4f101`) | Add the execution plan and reconcile ANY-217 (team-lead review #1) |
| 2026-08-11 | Added this execution plan; reconciled the two stale `report_output_v1` references in `any-217-frontend-safe-result-artifact-api.md` | Update `docs/architecture/action-model.md` and run a final `generate-docs --check`/`quick-check` pass |

## Open questions

- None.

## Follow-up debt

- `docs/architecture/action-model.md` has not yet been updated with the finalized A10 contract
  shape.
- `kernel_demo.extract_output_v1` remains open (`additionalProperties: true`) per ANY-217's
  handoff allowlist-mapping design decision; this plan only reconciled `report_output_v1`, which
  had become an exact duplicate rather than an intentionally softer schema. Revisiting
  `extract_output_v1` is out of scope here and still tracked under ANY-217's own follow-up debt.
