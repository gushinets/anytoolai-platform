# Execution Plan: ANY-122 Agent-First Repository Transition

## Status

- State: active
- Owner: agent
- Created: 2026-07-15
- Last updated: 2026-07-15
- Review date: 2026-07-15
- Next action: deliver ANY-126, then begin ANY-127.
- Blocker: GitHub authentication is required before the prepared child branches can be published.
- Linear: `ANY-122`

## Goal

Make the repository reliably agent-legible, reproducible, truthful, and diagnosable while MVP-A
and MVP-B continue under their own feature plans.

## Scope

### In scope

- `ANY-126`: documentation and execution-plan gardening.
- `ANY-127`: canonical commands and truthful CI.
- `ANY-128`: documentation and generated-artifact freshness checks.
- `ANY-129`: lightweight worktree-aware runtime commands.
- `ANY-130`: structured diagnostics and safe context collection.

### Out of scope

- Missing MVP-A or MVP-B domain behavior, APIs, migrations, product bundles, and UI journeys.
- Full observability stacks, global port registries, autonomous cleanup, autonomy trials, and
  automerge.

## Delivery order

- [ ] `ANY-126` documentation gardening.
- [ ] `ANY-127` canonical commands and CI.
- [ ] `ANY-128` documentation/generated freshness.
- [ ] `ANY-129` worktree-aware runtime.
- [ ] `ANY-130` structured diagnostics.

Each child issue uses one child execution plan and one cohesive PR.

## Integration rule

MVP-A/MVP-B feature issues own tests and documentation for the behavior they introduce. This plan
must not implement missing product behavior merely to demonstrate the harness. No required gate may
use passing placeholders, silent skips, permanent xfails, or ignored failures.

## Validation

- [ ] `python scripts/agent/runner.py doctor`
- [ ] `python scripts/agent/runner.py quick-check`
- [ ] Child-specific checks recorded in each child plan.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-15 | Use five sequential child tickets/PRs. | Keeps independent risk and rollback domains reviewable during MVP development. |
| 2026-07-15 | Keep MVP-A/MVP-B implementation outside ANY-122. | The harness should support feature delivery rather than compete with it. |
| 2026-07-15 | Keep all merges human-approved. | Autonomy expansion is deferred until stable vertical slices exist. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-15 | Created Linear children `ANY-126` through `ANY-130`; began documentation gardening. | Complete `ANY-126`. |
| 2026-07-15 | ANY-126 implementation is locally complete; publishing is blocked by GitHub authentication. | Begin ANY-127 on its stacked child branch. |
| 2026-07-15 | Began ANY-127 on `codex/any-127-truthful-ci`. | Align runner, dependencies, and CI. |
| 2026-07-15 | ANY-127 is locally complete and green; began ANY-128. | Enforce documentation and generated-artifact freshness. |

## Open questions

- None.

## Follow-up debt

- Deferred capabilities remain listed in `ANY-122` and should be promoted only after a real MVP
  trigger demonstrates need.
