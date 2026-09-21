# Execution Plan: ANY-232 Brief Decoder Bundle And Workflow

## Status

- State: active
- Owner: agent
- Created: 2026-09-21
- Last updated: 2026-09-21
- Review date: 2026-09-28
- Next action: open the PR (validation green).
- Blocker: none

## Goal

Define the `brief_decoder` Freelancer Suite product bundle as a real product config directory
loaded through `FreelancerSuiteBundle.config_roots()`: workflow `A01 + A04 -> A05`, composed
through A10, using only generic atoms -- no Platform Core changes, no product Python code.

## Scope

### In scope

- `packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products/brief_decoder/`:
  product, scenario, frontend, workflow, action-config, prompt, schema, quota and renderer-contract
  config.
- `FreelancerSuiteBundle.config_roots()` wiring; README and `add-product-recipe.md` root counts.
- Deterministic fake-provider fixtures: happy path, weak input, and an empty-issues A04 variant.
- Tests in `apps/platform-api/tests` (quick-check) and `freelancer-suite/tests` (full-check).

### Out of scope

`apps/web-mirror` page/renderer (ANY-248), Chrome Extension (ANY-240), the Brief Decoder ->
Acceptance Builder handoff (ANY-26), a live-provider action-config variant, any Platform
Core/atom/mapping-DSL change, custom backend endpoints.

## Relevant docs

- `docs/product-specs/add-product-recipe.md`
- `docs/architecture/action-model.md`
- `docs/architecture/workflow-model.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `packages/backend/product-platforms/freelancer-suite/README.md`

## Contracts touched

- API: none (generic `/v1/products/{product}/scenarios/{scenario}/start` runtime only).
- DB: none.
- Config: new product tree under `freelancer-suite`; `FreelancerSuiteBundle.config_roots()`.
- Events: `client.next_action_clicked` via the generic `copy_result` next action only; no
  `analytics.yaml`, no `handoffs.yaml`.
- Frontend: `frontends.yaml` registers one `web_mirror` entry (runtime requirement for any
  scenario start); no page code.

## Design decisions

1. **One scenario, one workflow, four steps, one run.** `brief_decoder.decode_v1`. Per
   `atom-ready-product-inventory.md` Brief Decoder has a single workflow run, so the acceptance
   criterion "any second run receives an explicit user-selected string" is satisfied by having no
   second run; a test pins the single scenario. No mapping path indexes an array.
2. **All four steps are `structured_llm`**, A10 included (no template registry:
   `template_ref` is a string and its meaning lives in the product prompt
   `generate_summary.v1.md`, as in `kernel_demo`). Each step has its own action config, prompt and
   fixtures.
3. **Product decisions no doc specifies** (input, A01 fields, taxonomy, audience):
   - Input: one required trimmed `brief_text` (max 8000).
   - A01 fields, all `required: false`, `strict: false` so a vague brief yields `missing_fields`
     rather than a failed run: `project_goal`, `deliverables`, `deadline`, `budget`,
     `target_audience`, `constraints` (`deadline`/`budget` are strings, worded as the brief words
     them, not `date`).
   - A04 taxonomy: `missing_information`, `ambiguity`, `scope_risk`, `timeline_risk`,
     `budget_risk`, `contradiction`.
   - A05 `target_audience`: "the client who wrote the brief".
4. **A01 -> A04 is order-only** (`action-model.md`): A04 reads the original brief text.
5. **Composed output.** Each step writes its own key of `context.workflow_output`
   (`brief`, `issues`, `questions`, `document`); the result is one closed object validated against
   `brief_decoder.decode_output_v1`. No committed workflow composed output this way before; the
   end-to-end tests are the proof. Fallback if it ever proves brittle: expose only A10's output.
   Because the A01 field list and taxonomy are config-owned, the output schema closes
   `brief.values` with explicit properties and enumerates categories; a test ties the literals in
   `workflows.yaml` to the schema so they cannot drift.
6. **A04 -> A05 contract mismatch.** A04 `issues` may be empty; A05 `issues` has `minItems: 1`.
   Guard as in `kernel_demo.detect_questions_v1`: A04 seeds `questions: []`, A05 has
   `when: steps.detect_issues.output.issues`, A10 reads `?steps.generate_questions.output.questions`.
   An empty question list is a valid, non-activating result.
7. **Quota**: `quotas.yaml` (3 runs per guest, lifetime, per product), mirroring `proposal_ai`.
   Not required by the ticket; motivated by four provider calls per run. The limit is a starting
   value.
8. **`renderer_contract.yaml`** is product-owned and never read by `ConfigLoader`; it names the
   four parts (brief, issues, clarifying questions, summary document) and is asserted against
   `workflows.yaml`/`scenarios.yaml` by the product's own test.

## Implementation steps

- [x] Exec plan (this file).
- [x] Product config tree.
- [x] `FreelancerSuiteBundle.config_roots()` wiring + README / recipe root counts.
- [x] Nine fixtures (4 happy, 4 weak, 1 empty-issues A04).
- [x] Tests: `apps/platform-api/tests/test_brief_decoder_bundle.py`,
      `freelancer-suite/tests/test_brief_decoder_product.py`.
- [x] Verification (below).

## Validation

- [x] `python scripts/agent/runner.py validate-configs`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py quick-check`
- [x] `python scripts/agent/runner.py validate-docs` / `generate-docs --check`
- [x] `python scripts/agent/runner.py full-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-09-21 | Single run, no second-run input | Inventory says one workflow run; AC is conditional |
| 2026-09-21 | Guard A05 with `when` + seeded `questions: []` | A05 input requires >= 1 issue; precedent `detect_questions_v1` |
| 2026-09-21 | Composed per-key `workflow_output` | Delivers all four renderer parts; fallback is A10-only output |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-09-21 | Config tree, fixtures, wiring and both test suites written; new tests green | Open PR |

## Open questions

None blocking. The input/field/taxonomy choices in decision 3 are product decisions a reviewer may
want to change; they drive the output schema and all nine fixtures.

## Follow-up debt

- `kernel_demo.composite_analyze_and_clarify_v1` has the same missing empty-issues guard; not
  fixed here (out of scope).
- Brief Decoder -> Acceptance Builder handoff is ANY-26.
