# Execution Plan: MVP-A1/A2 And Client Surfaces Reorganization

## Status

- State: completed
- Owner: agent
- Created: 2026-08-06
- Last updated: 2026-08-06
- Review date: 2026-08-06
- Next action: deliver the planned MVP-A1 proof and MVP-A2 client issues through their own feature plans.
- Blocker: none

## Goal

Split MVP-A into the MVP-A1 Atom Runtime Proof and MVP-A2 Client Surfaces delivery milestones,
reorganize the Platform Core and Freelancer Suite Linear backlogs accordingly, and align the
repository source-of-truth documentation without implementing deferred runtime features.

## Scope

### In scope

- Create and populate the Linear `Client Surfaces` project.
- Reframe, move, split, and relate the agreed Platform Core issues.
- Turn each Freelancer product issue into a parent with bundle, Chrome Extension, and E2E children.
- Update MVP scope, architecture, product, quality, and Linear delivery-map documentation.

### Out of scope

- Runtime implementation of the result API, atom proof harness, live provider canary, web mirror,
  CE journeys, or Freelancer products.
- Chrome Web Store publishing, billing, authentication, and UI polish.

## Relevant docs

- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/product-specs/mvp-b-freelancer-validation-bundle.md`
- `docs/architecture/frontend-boundaries.md`
- `docs/exec-plans/active/mvp-a-mvp-b-linear-epics.md`

## Contracts touched

- API: document the planned frontend-safe `GET /v1/results/{artifact_id}` contract only.
- DB: none.
- Config: none.
- Events: none.
- Frontend: ownership and release-boundary documentation only.

## Implementation steps

- [x] Inventory current Linear project, issue, parent, blocker, status, and assignee state.
- [x] Create Client Surfaces and apply the agreed Platform Core/Client Surfaces issue changes.
- [x] Create and relate the 24 Freelancer product child issues.
- [x] Audit Linear for preserved status/history, complete hierarchies, and acyclic dependencies.
- [x] Update the repository source-of-truth and delivery-map documentation.
- [x] Run documentation, architecture, generated-doc, and quick-check validation.
- [x] Move this execution plan to completed with final evidence.

## Validation

- [x] Linear project/issue audit
- [x] `python scripts/agent/runner.py validate-docs`
- [x] `python scripts/agent/runner.py generate-docs --check`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py quick-check` (`229 passed`, `301 deselected`)

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-06 | Name the new project `Client Surfaces`. | It owns shared web and Chrome client surfaces, not backend services. |
| 2026-08-06 | Split each Freelancer product into three child issues. | Bundle, CE, and E2E work have distinct dependencies and completion evidence. |
| 2026-08-06 | Keep backend contracts in Platform Core. | Client Surfaces consumes frontend-safe APIs but does not own runtime state. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-06 | Plan created from the approved reorganization specification. | Inventory and mutate Linear in reviewable batches. |
| 2026-08-06 | Created Client Surfaces, moved/reframed A2 work, created A1 proof and result-API issues, and added 24 Freelancer children. | Audit project ownership and dependency invariants. |
| 2026-08-06 | Linear audit passed: eight parents have exactly three children, A1 and product CEs do not depend on web mirror, and no blocker cycle was found. | Run repository validation. |
| 2026-08-06 | All requested repository checks passed, including 229 quick-check tests. | Complete the reorganization plan. |

## Open questions

None.

## Follow-up debt

Runtime implementation remains intentionally represented by Linear work and is outside this
reorganization change.
