# Execution Plan: ANY-228 Acceptance Builder Bundle And Workflow

## Status

- State: active
- Owner: agent
- Created: 2026-09-25
- Last updated: 2026-09-25
- Review date: 2026-09-29
- Next action: run the full validation set, open the PR, address review.
- Blocker: none

## Goal

Define the `acceptance_builder` Freelancer Suite product bundle as a real product config directory
loaded through `FreelancerSuiteBundle.config_roots()`: `A01 + A11`, composed through A10, using
only generic atoms -- no Platform Core changes, no product Python code.

## Scope

### In scope

- `packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products/acceptance_builder/`:
  product, scenario, frontend, workflow, action-config, prompt, schema, quota and
  renderer-contract config.
- `FreelancerSuiteBundle.config_roots()` wiring; README, `add-product-recipe.md` and
  `mvp-b-handoff-note.md` root counts.
- Eight deterministic fake-provider fixtures: happy path and weak input for each of the four
  action configs.
- Tests in `apps/platform-api/tests` (quick-check) and `freelancer-suite/tests` (full-check).

### Out of scope

`apps/web-mirror` page, registry entry and smoke (ANY-244); Chrome Extension (ANY-236);
`handoffs.yaml` and the Brief Decoder -> Acceptance Builder map (ANY-26); product events
(`analytics.yaml`); an A02 variant; any Platform Core, atom or mapping-DSL change; custom backend
endpoints; a live-provider action-config variant.

## Relevant docs

- `docs/product-specs/add-product-recipe.md`
- `docs/product-specs/atom-ready-product-inventory.md`
- `docs/architecture/action-model.md`
- `docs/architecture/workflow-model.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`

## Contracts touched

- API: none (generic scenario start/result/next-action runtime only).
- DB: none.
- Config: new product tree under `freelancer-suite`; `FreelancerSuiteBundle.config_roots()`.
- Events: `client.next_action_clicked` via the generic `copy_result` next action only.
- Frontend: `frontends.yaml` registers one `web_mirror` entry (a runtime requirement for any
  scenario start); no page code.

## Design decisions

1. **Two scenarios, one product** (confirmed by the owner): `acceptance_builder.draft_v1`
   (brief -> acceptance criteria; input `brief_text`) and `acceptance_builder.check_v1` (check a
   deliverable against the brief; input `brief_text`, `deliverable_text`). Each is one workflow
   run, so the "second run receives an explicit user-selected string" criterion is met by having
   no second run; a test pins the scenario set and the absence of array indexing. The split is
   needed because `when` has no optional key and a required `deliverable_text` would make a
   handoff from Brief Decoder (which has no deliverable text) impossible.
2. **A11, not A02.** The ticket's "comparison verdict" is categorical; A02 yields a numeric score
   with an arithmetic validator and requires weights. "A02" in "`A01 + A11` or A02" is an
   explicit narrowing for v1.
3. **Comparison criteria are a config literal**, not A01 output: four general criteria
   (`scope_coverage`, `requirement_fit`, `completeness`, `clarity`, weighted) and categories
   `meets_expectations | partially_meets | does_not_meet`. A01 yields strings; A11 needs
   `{id, description}` objects and the mapping DSL cannot convert. The renderer contract and the
   verdict section say the verdict is not a per-extracted-criterion check.
4. **A01 extracts three lists** (`acceptance_criteria`, `assumptions`, `deliverables`), not
   strict; the prompt separates extraction from invention and gaps go to `missing_fields`.
5. **One shared `extract_v1` action config** for both scenarios, plus `compare_v1`,
   `draft_document_v1`, `check_document_v1`. Fixtures are keyed by action config id, so one
   extract fixture serves both scenarios.
6. **Product schemas are the only control over A10 output.** Each output schema pins the document
   sections (ids, titles, order, list metadata), the A01 "present XOR missing" invariant, one
   delta per criterion id in workflow order, `meets_expectations` => no `mismatch` and
   `does_not_meet` => at least one `mismatch` (A11's cross-validator relates neither).
7. **Handoff readiness**: `draft_input.brief_text` is a plain string so ANY-26 can fill it from
   Brief Decoder's `document.summary`; no `handoffs.yaml` here. To make that hold for every valid
   Brief Decoder artifact (not just today's fixtures), `brief_decoder.decode_output_v1`'s
   `document.summary` now carries the same `maxLength` (8000) and trimmed-text `pattern` as
   `brief_text`, and a test compares the two schemas. This tightens the ANY-232 schema: a summary
   over 8000 characters or with surrounding whitespace now fails that run instead of failing the
   later handoff.

## Implementation steps

1. Product, scenario, frontend, quota, schema, action-config, prompt and workflow config.
2. Four closed schemas (generated once from a shared shape so the `extracted` block cannot drift).
3. Four prompts; `renderer_contract.yaml` with a per-scenario `scenarios:` list.
4. Eight fixtures.
5. Bundle wiring and root-count docs.
6. Tests: `apps/platform-api/tests/test_acceptance_builder_bundle.py`,
   `freelancer-suite/tests/test_acceptance_builder_product.py`, `test_bundle_loads.py`.

## Validation

```
python scripts/agent/runner.py validate-configs
python scripts/agent/runner.py validate-architecture
python scripts/agent/runner.py quick-check
python scripts/agent/runner.py generate-docs --check
python scripts/agent/runner.py validate-docs
python scripts/agent/runner.py full-check
```

## Decision log

- 2026-09-25: decisions 1-5 fixed; owner confirmed the two-scenario shape.

## Open questions

- Activation rule for `draft_v1` (no verdict): decided by ANY-244.
- Quota limit 3 is a starting value, not validated.
- Product priority: Linear calls Acceptance Builder "required #4"; repo docs keep it in the
  backlog outside the release order. README wording is unchanged on that point.

## Follow-up debt

- Quota is charged before input validation (inherited Platform Core gap, separate task).
- The Linear blocked-by list omits A11/A02 and includes unused A07; left as is.
