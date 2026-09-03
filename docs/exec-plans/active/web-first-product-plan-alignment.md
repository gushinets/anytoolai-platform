# Execution Plan: Web-First Product Plan Alignment

## Status

- State: active
- Owner: agent
- Linear: [ANY-410](https://linear.app/paveldik/issue/ANY-410/align-repository-scope-with-web-first-product-validation)
- Created: 2026-09-03
- Last updated: 2026-09-04
- Review date: 2026-09-04
- Next action: commit the aligned documentation as one reviewable commit.
- Blocker: none

## Goal

Make the repository describe one executable web-first validation plan before product code changes:
ProposalAI is the first web product, `apps/web-mirror` is the shared multi-product web host, the
six-product validation set replaces the old CE-first release train, and the 21 atom-ready concepts
remain a capability inventory rather than committed releases.

## Scope

### In scope

- Add ADR-0008 for the web-first multi-product host and its relationship to ADR-0005.
- Make `docs/product-specs/mvp-scope-source-of-truth.md` the controlling web-first statement.
- Align Client Surfaces, Freelancer Validation Bundle, Freelancer Suite, the web-first design spec,
  the product inventory, the repository knowledge map, and top-level architecture summary.
- Define the v1 metric contract in the existing web-first design spec.
- Record the six-product validation order:
  ProposalAI, Client Update Writer, Brief Decoder, Acceptance Builder, Task Finder, Send-Ready.
- Record immediate-only, same-tab web handoff semantics for the validation set.
- Validate documentation and generated artifacts.

### Out of scope

- Product pages, result renderer implementation, or browser tests.
- `POST /v1/client-events`, event producers, or event-log schema changes.
- Product configs, workflows, prompts, schemas, or handoff maps.
- Changes to atoms, workflow/action runners, Provider Gateway, scenario/quota/handoff runtime, or
  mapping DSL.
- Deferred web-handoff continuation.
- A new frontend package, generic form builder, analytics dashboard, or machine-readable metric
  registry.
- Shipping all 21 atom-ready concepts.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/core-beliefs.md`
- `docs/adr/0005-separate-product-chrome-extensions.md`
- `docs/adr/0006-event-log-as-core.md`
- `docs/architecture/frontend-boundaries.md`
- `docs/architecture/event-taxonomy.md`
- `docs/architecture/handoff-model.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/product-specs/mvp-a2-client-surfaces.md`
- `docs/product-specs/mvp-b-freelancer-validation-bundle.md`
- `docs/product-specs/freelancer-suite-v0.md`
- `docs/product-specs/atom-ready-product-inventory.md`
- `docs/superpowers/specs/2026-09-03-web-first-product-framework-design.md`

## Contracts touched

- API: documentation continues to reserve `POST /v1/client-events`; no endpoint is implemented here.
- DB: none.
- Config: none.
- Events: documentation only; `client.result_copied` remains reserved with no live producer and is
  excluded from v1 metrics.
- Frontend: ownership and planned route behavior only; no frontend source changes.
- Handoff: documentation limits the first web validation path to existing backend-owned tokens,
  `immediate` target start, and same-tab navigation.

## Implementation steps

- [x] Step 1: Add `docs/adr/0008-web-first-multi-product-host.md`. Record that the existing
  `apps/web-mirror` hosts multiple product routes, shared runtime must not import product semantics,
  product definitions remain product-owned, and ADR-0008 supplements rather than rewrites ADR-0005.
- [x] Step 2: Update `docs/index.md` to index ADR-0008 and the approved web-first design spec.
- [x] Step 3: Update `docs/product-specs/mvp-scope-source-of-truth.md` so web pages are the default
  product Definition of Done, Chrome Extensions are later and optional unless explicitly selected,
  and the six-product validation set replaces the eight-product CE-first order.
- [x] Step 4: Update `ARCHITECTURE.md` and `docs/core-beliefs.md` only where their CE-first summaries
  conflict with the controlling web-first decision. Preserve MVP-A1 and backend ownership boundaries.
- [x] Step 5: Update `docs/product-specs/mvp-a2-client-surfaces.md` and
  `docs/architecture/frontend-boundaries.md` so `apps/web-mirror` owns product routes in addition to
  result, consent, paywall, and onboarding routes. Keep prompts, workflows, provider/model choice,
  quota authority, and scenario state outside the frontend.
- [x] Step 6: Update `docs/product-specs/mvp-b-freelancer-validation-bundle.md` and
  `docs/product-specs/freelancer-suite-v0.md` to describe the six-product web validation set. Remove
  the requirement for one Chrome Extension and three delivery children per validation product;
  retain product-owned configs, prompts, schemas, renderers, events, and handoff maps.
- [x] Step 7: Correct `docs/superpowers/specs/2026-09-03-web-first-product-framework-design.md`:
  make ProposalAI activation `client.next_action_clicked` with `next_action_id=copy_result` after a
  successful clipboard write; keep `client.result_copied` reserved and unused; define
  `value_produced`, per-product `activation`, `value_take_rate`, and `activation_gap`; define metric
  `producer`, closed `trust_class`, and `blind_spots`; document active identity and session timeout;
  and state that analytics delivery failure cannot undo a successful user action.
- [x] Step 8: In the same spec, define the four allowed metric trust classes as
  `backend_produced`, `backend_recorded_client_action`, `client_observed`, and `derived`. Keep this
  metadata in documentation rather than adding it to each event-log row or creating a registry.
- [x] Step 9: In the same spec, define `value_produced` as `scenario.completed` correlated with its
  canonical result artifact. Treat a completed scenario without that artifact as a data-quality
  invariant violation, not a second completion category.
- [x] Step 10: In the same spec, define the future migration rule for `client.result_copied`: if a
  live producer is introduced, activation queries must deduplicate it against
  `client.next_action_clicked(copy_result)` for the same scenario/user action before switching the
  canonical metric.
- [x] Step 11: Document Brief Decoder to Acceptance Builder as an `immediate` same-tab handoff. The
  CTA means "create draft", acceptance queues the target workflow immediately, and later editing is
  local editing or a new scenario run rather than deferred handoff continuation.
- [x] Step 12: Update `docs/product-specs/atom-ready-product-inventory.md` so its build-order section
  is explicitly a capability backlog, while a separate validation-set note links to the controlling
  six-product order. Keep all 21 atom-ready concepts and SP007 as an SP002 feature.
- [x] Step 13: Search the repository documentation for stale controlling statements including
  `CE-first`, `eight product`, `eight thin`, `separate Chrome Extension`, and the previous activation
  definition. Correct only statements that claim current scope; preserve historical ADR context.
- [x] Step 14: Run documentation validation and inspect every failure before changing unrelated
  files.
- [x] Step 15: Review the final diff for one source of truth, no implementation claims, no new
  abstractions, and no accidental changes to existing untracked files.
- [ ] Step 16: Commit the aligned documentation as one reviewable documentation commit.
- [ ] Step 17: Move this plan to `docs/exec-plans/completed/` and record the commit and validation
  evidence in its progress log.
- [ ] Step 18: Create a separate active implementation plan for the ProposalAI vertical slice. That
  plan begins with tests for the real `/r/{artifact_id}` renderer and the copy-button activation
  path; it must not assume that a generic framework exists before the first product proves it.

## Validation

- [x] `python scripts/agent/runner.py validate-docs`
- [x] `.quick-check-venv/Scripts/python.exe scripts/agent/runner.py generate-docs --check`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `rg -n "CE-first|eight (production|product|thin)|separate Chrome Extension|first successfully viewed" ARCHITECTURE.md docs` (remaining matches are historical ADR/plan context)
- [x] `git diff --check`

`quick-check` is not required for this documentation-only alignment unless the changed documentation
validation exposes a generated/config dependency. The ProposalAI implementation plan will require
the relevant backend, frontend, and full checks.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-09-03 | Split documentation alignment from ProposalAI implementation. | Requirements must be internally consistent before code is planned against them. |
| 2026-09-03 | Keep `apps/web-mirror` as the first multi-product web host. | Reuses the existing app and avoids a speculative package or application. |
| 2026-09-03 | ADR-0008 supplements ADR-0005. | Separate product CEs remain a valid extension decision; web products use a different composition model. |
| 2026-09-03 | Keep 21 concepts as inventory and validate six products. | Capability coverage is not a commitment to 21 releases. |
| 2026-09-03 | Keep `client.result_copied` reserved but unused in v1 metrics. | The taxonomy already contains it, but no live producer exists. |
| 2026-09-03 | Use `client.next_action_clicked(copy_result)` for ProposalAI activation. | It has an existing backend-recorded path and represents successful copy-button use. |
| 2026-09-03 | Do not extend mapping DSL or deferred handoff for the first web slice. | Current contracts support user-selected gaps through a second run and immediate handoff already works. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-09-03 | Created the documentation-alignment execution plan after repository doctor passed. | Add ADR-0008, then align the controlling scope document. |
| 2026-09-03 | Added ADR-0008 for the existing multi-product web host, product/runtime boundary, and immediate same-tab handoff. | Index ADR-0008, then align the controlling scope document. |
| 2026-09-03 | Indexed ADR-0008 and made the repo-local MVP scope the controlling web-first source with a six-product validation set. | Align top-level architecture and core beliefs. |
| 2026-09-03 | Aligned the top-level architecture map and core beliefs with web-first validation while preserving Platform Core boundaries. | Align Client Surfaces ownership and frontend boundaries. |
| 2026-09-03 | Aligned Client Surfaces and frontend boundaries: MVP-A2 owns the host/runtime; MVP-B owns product definitions and optional CEs. | Align the Freelancer validation bundle and suite. |
| 2026-09-03 | Replaced the eight-product CE-first release train with the six-product web validation set and two reviewable delivery outcomes. | Correct the web-first design spec and metric contract. |
| 2026-09-03 | Defined truthful v1 metrics, product activations, identity/session limits, reserved-event migration, and immediate handoff in the web-first spec. | Align the product inventory with the validation set. |
| 2026-09-03 | Reframed the 21 concepts as capability inventory, added the controlling six-product set, and left the remaining concepts unprioritized. | Audit stale controlling CE-first statements. |
| 2026-09-03 | Updated current repo guidance and marked the old Linear issue map as a non-controlling legacy snapshot pending a separate Linear audit. | Run the complete documentation validation set. |
| 2026-09-03 | Validation passed under the repository-managed environment. System Python reports false OpenAPI drift because it has FastAPI 0.115.6 instead of managed 0.137.0; the existing `generated-doc-locked-environment-parity.md` plan owns that runner defect. | Review the complete documentation diff. |
| 2026-09-03 | Independent review found five documentation inconsistencies; all were fixed, validation reran cleanly, and focused re-review returned no remaining findings. | Commit the aligned documentation. |

## Open questions

None. Product-specific activation definitions beyond the six-product validation set are deliberately
deferred until those products enter validation.

## Follow-up debt

- ProposalAI vertical-slice implementation plan.
- Client Update Writer reuse proof after ProposalAI works.
- Deferred handoff start UX only when a validated product requires it.
- Machine-readable metric definitions only when code must consume them.
