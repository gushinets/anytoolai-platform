# Execution Plan: ANY-231 Task Finder Bundle And Workflow

## Status

- State: active
- Owner: agent
- Created: 2026-10-06
- Last updated: 2026-10-06
- Review date: 2026-10-13
- Next action: run the full validation set, then open the PR.
- Blocker: none

## Goal

Define the `task_finder` Freelancer Suite product bundle (one scenario, `task_finder.fit_v1`) as a
real product config directory loaded through `FreelancerSuiteBundle.config_roots()`, using only A11
`text.compare_and_classify` and A02 `text.score_match_by_rubric` -- no Platform Core changes, no
product Python code.

## Scope

### In scope

- `packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products/task_finder/`:
  product, frontends, scenario, workflow, action-config, prompt, schema, quota and renderer-contract
  config.
- `FreelancerSuiteBundle.config_roots()` wiring and the docs that list the product roots.
- Four deterministic fake-provider fixtures (happy and weak input for each action config).
- Tests: `apps/platform-api/tests/test_task_finder_bundle.py` (quick-check) and
  `packages/backend/product-platforms/freelancer-suite/tests/test_task_finder_product.py`
  (full-check).

### Out of scope

The `apps/web-mirror` page, registry, i18n and smoke (ANY-247); the Chrome Extension (ANY-239);
a Task Finder -> ProposalAI `handoffs.yaml`; A01/A09 steps; a structured freelancer profile;
forcing the score and the verdict to agree; a live provider; Platform Core, atom or mapping-DSL
changes; any change to the wording about release order.

## Relevant docs

- `docs/product-specs/atom-ready-product-inventory.md`
- `docs/product-specs/mvp-b-freelancer-validation-bundle.md`
- `docs/product-specs/add-product-recipe.md`
- `docs/architecture/action-model.md`
- `packages/backend/product-platforms/freelancer-suite/README.md`

## Contracts touched

- API: none (generic start/result endpoints only).
- DB: none.
- Config: new product config tree under `freelancer-suite`; `FreelancerSuiteBundle.config_roots()`.
- Events: `client.next_action_clicked` via the generic `copy_result` next action; no new event types.
- Frontend: `frontends.yaml` registers one metadata-only `web_mirror` entry (required for a
  scenario to start); no page code ships here.

## Design decisions

1. One scenario, one workflow, `allowed_next_actions: [copy_result]`. The inventory says
   "Workflow runs: 1", so there is no second run and no array indexing in the mapping DSL.
2. A11 + A02 only. A01 and A09 are optional in the inventory and are not in v1: A09 needs
   `signals` objects that no step produces (the mapping DSL cannot build or index them), and A01
   yields only values and string arrays that A11/A02 cannot take as structure. The renderer
   contract says structured extraction and angle are not produced in this version.
3. Input `task_text` and `freelancer_positioning`: the same names, limits and trim pattern as
   ProposalAI's input, so a later handoff maps fields one to one. The profile is free text.
4. The workflow echoes both inputs into its output (`scenario.input.*`, ANY-540 pattern), so a
   later Task Finder -> ProposalAI route needs no schema version bump (Brief Decoder needed one in
   ANY-26). Cost: the artifact holds up to 8000 more characters.
5. Four shared weighted criteria in one literal used by both atoms: `skills_fit` 3,
   `experience_fit` 2, `scope_fit` 2, `constraints_fit` 1. A02 requires weights, A11 accepts them.
   Categories: `strong_fit | partial_fit | weak_fit`.
6. The output schema binds the verdict to the delta statuses (all match -> strong, any mismatch ->
   weak, else partial), requires exactly one delta and one score per criterion id in any order
   (the atom validators check id coverage, not array order), and inlines the atom output shapes
   (a test pins them to the kernel schemas). It deliberately does not bind the score
   to the verdict: they come from two independent model calls, and a threshold would fail whole
   live runs on a disagreement. The renderer contract shows them as two indicators.
7. No `handoffs.yaml` and no `analytics.yaml`: the ProposalAI route is an optional later step.
8. Quota: `scenario_run`, `lifetime`, `product`, limit 3 -- a starting value, not validated.
9. A weak input (vague task, thin profile) is a valid low-score result, not an error. Information
   the texts do not state is `partial`, never `mismatch` (compare prompt), so the weak fixture is
   a low-confidence `partial_fit`; `weak_fit` needs a clear conflict or a clear lack.

## Implementation steps

1. Product config, schemas, prompts and the renderer contract.
2. Four fixtures with arithmetic that agrees with the A02 weighted-average validator.
3. Wire `task_finder` into `config_roots()`; update the stale four-root lists in docs and tests.
4. Add the quick-check and full-check tests.
5. Run the validation commands below.

## Validation

```bash
python scripts/agent/runner.py validate-configs
python scripts/agent/runner.py validate-architecture
python scripts/agent/runner.py quick-check
python scripts/agent/runner.py generate-docs --check
python scripts/agent/runner.py validate-docs
python scripts/agent/runner.py full-check
```

## Decision log

- 2026-10-06: A01/A09 left out of v1 (decision 2); input echo included (decision 4); no handoff
  file (decision 7). Defaults taken for the open questions; revisit if the owner disagrees.

## Progress log

- 2026-10-06: product config, fixtures, wiring and both test files written; product and
  platform-api tests pass.

- 2026-10-07: code-review round 1, bugs 1-7 fixed. The output schema no longer fixes the array
  order of deltas and scores (the atom validators check id coverage only); the compare prompt
  uses `partial`, not `mismatch`, for information the texts do not state; the renderer contract
  shows statuses and scores as two separate lists, covers every output property (the input echo
  is in `excluded_fields`); the weak fixtures carry their own `fixture_id`; a test records the
  `copy_result` event; the kernel-copy sync test compares limits; `test_validate_configs.py` lists
  `task_finder`.

- 2026-10-07: review follow-up. The happy compare fixture marks `scope_fit` as `mismatch` (the
  task requires a mobile app, the profile says web only), so its verdict is `weak_fit`; the happy
  score fixture's `scope_fit` is 40 and the total 64. The happy path now exercises `weak_fit`
  and the weak-input path `partial_fit`.

## Open questions

- Owner: confirm A01/A09 stay out of v1, and whether the input echo should stay (if it is
  removed, a ProposalAI handoff will need a schema version bump).
- Release status: Linear calls Task Finder "required validation product #5", while the repo docs
  place it in the capability backlog. Wording about release order is unchanged here.

## Follow-up debt

- Both atoms share one criteria literal that appears twice in `workflows.yaml`; a test pins the
  copies equal, but the duplication stays until the mapping DSL can share literals.
- The weak-input fixtures are reachable only through the test adapter; `dev-up` serves the happy
  fixtures.
