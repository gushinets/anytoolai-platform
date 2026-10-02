# Execution Plan: ANY-228 Acceptance Builder Bundle And Workflow

## Status

- State: completed
- Owner: agent
- Created: 2026-09-25
- Last updated: 2026-10-02
- Review date: 2026-09-29
- Next action: none; PR #150 merged; no plan-scoped work remains.
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
6. **Product schemas are the only control over A10 output**, so they carry the invariants A11's
   and A10's own validators do not:
   - Sections are pinned (ids, titles, order, list metadata) and the A01 "present XOR missing"
     rule holds.
   - `comparison.deltas` has one entry per criterion id in workflow order, and the verdict is a
     partition of the statuses: all `match` => `meets_expectations`, any `mismatch` =>
     `does_not_meet`, otherwise `partially_meets` (team-lead review #1: the earlier one-sided
     rules still accepted `meets_expectations` + `partial` and `partially_meets` + all `match`).
     Criterion weights therefore do not decide the verdict.
   - The document is bound to its structured authority (team-lead review #1): the `check_v1`
     verdict section must start with the pinned phrase for `comparison.verdict` and carry one
     `<Label>: <status>` marker per delta; for both scenarios a list absent from `extracted.values`
     must read "Not specified in the brief." (a present one must not) and `open-gaps` must name
     every `missing_fields` entry. These are per-value `if/then` patterns generated from the closed
     enums, so a live A10 answer that contradicts the verdict, a status or a missing field fails
     validation. Ceiling: the schema cannot compare free text to dynamic values, so verbatim list
     items, evidence sentences and the summary prose cannot be pinned -- decision 8 makes that safe.
7. **No Brief Decoder handoff target in this ticket.** Three review rounds showed no handoff
   source that is both faithful and expressible today: `document.summary` is a readiness note;
   `output_mapping` cannot echo `scenario.input` (Platform Core change, out of scope); a
   structured target (`brief` + `issues` + `questions`) forks Acceptance Builder's drafting
   semantics into a second workflow and copies another product's DTO (team-lead review #1). The
   owner chose to remove it. `draft_v1` (brief text) stays the one drafting contract. The
   Brief Decoder -> Acceptance Builder route is an explicit ANY-26 decision: either Brief Decoder
   exposes a faithful brief field (or the mapping capability is extended) so the handoff converges
   on `draft_v1`, or ANY-26 defines an Acceptance Builder-owned handoff input.

8. **Copy text is derived from structured data, not from `document`** (review #5). A schema cannot
   bind A10's list items or prose to the values they restate, and there is no per-product
   validator hook (validators are registered per atom type in `platform-actions`; A10's is
   `none`; a grounding validator would be a `platform-actions` change outside this ticket). So
   `renderer_contract.yaml` no longer names `document` the canonical field: the copy-ready text is
   composed deterministically from `comparison` (verdict, deltas, rationale), `extracted.values`
   and `extracted.missing_fields`, and `document` is A10's display-only narrative
   (`copy_text.not_copyable_fields`). Nothing a model invents in `document` can reach what the
   user sends. The schema bindings from decision 6 stay as defence in depth for what is shown.
   ANY-244 implements the composition and decides whether to show the narrative at all. Trade-off:
   A10's document duplicates the structured facts and is not the copy source.

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
- 2026-09-26/28: reviews #2 and #3 iterated a structured `draft_from_brief_v1` handoff target.
- 2026-09-29: team-lead review #1 found it forks the drafting contract; the owner chose to remove
  it and leave the handoff route to ANY-26 (decision 7). The verdict partition and the
  document-to-result binding were added (decision 6).
- 2026-10-02: resolved after this plan's scope. Activation rule for `draft_v1` (no verdict): decided in
  ANY-244 (a non-empty acceptance-criteria list counts as the first display). Brief Decoder -> Acceptance
  Builder handoff route (decision 7): delivered by ANY-26 (PR #156) and proven end to end by ANY-244
  (PR #158).

## Open questions

- Product priority: Linear calls Acceptance Builder "required #4"; repo docs keep it in the
  backlog outside the release order. README wording is unchanged on that point.

## Follow-up debt

- Quota is charged before input validation (inherited Platform Core gap, separate task).
- Quota limit 3 is a starting value, not validated. Validating it needs usage data and is outside
  this plan's completion criteria; it is tracked as separate follow-up debt, not as work owned here.
- The Linear blocked-by list omits A11/A02 and includes unused A07; left as is.
