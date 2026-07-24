# Execution Plan: ANY-144 Handoff Mapping Target Collisions

## Status

- State: active
- Owner: agent
- Created: 2026-07-24
- Last updated: 2026-07-24
- Review date: 2026-07-24
- Next action: commit and push the reviewed changes, then confirm final CI
- Blocker: publication was not requested; the local canonical quick-check wrapper timed out during
  aggregate pytest, although its exact 346 fast pytest targets passed in isolated groups

## Goal

Reject ambiguous handoff mapping target paths during config loading, regardless of declaration
order, while preserving valid sibling mappings.

## Scope

### In scope

- Detect duplicate or prefix-conflicting target paths in `context_mapping` and `preview_mapping`.
- Return structured config diagnostics with the handoff id, mapping type, and conflicting path.
- Cover both conflict orders, deeper conflicts, both mapping types, and valid siblings.
- Reconcile A17 execution-plan validation status with the successful PostgreSQL CI job.

### Out of scope

- Handoff token, acceptance, expiry, or runtime orchestration changes.
- Arbitrary user-created handoff routes.
- Committing or pushing the changes.

## Relevant docs

- `docs/architecture/config-model.md`
- `docs/architecture/handoff-model.md`
- `docs/product-specs/mvp-a-platform-kernel.md`

## Contracts touched

- API: none
- DB: none
- Config: handoff mapping target paths must be non-conflicting
- Events: none
- Frontend: none

## Implementation steps

- [x] Add deterministic prefix-collision validation to the config loader.
- [x] Add acceptance-criteria tests for context and preview mappings.
- [x] Update stale A17 execution-plan validation evidence.
- [x] Correct remaining A17 review documentation to use canonical runner commands.
- [x] Replace PR #36's empty template with a complete description and validation record.

## Validation

- [ ] `python scripts/agent/runner.py quick-check` final wrapper/CI run after publication
- [x] Exact fast quick-check pytest target set: 346 passed in isolated groups
- [x] `python scripts/agent/runner.py validate-configs`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py validate-docs`
- [x] `python scripts/agent/runner.py generate-docs --check`
- [x] Focused config-loader and handoff tests: 59 passed

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-24 | Validate collisions after individual path syntax checks. | Diagnostics remain structured and no invalid path reaches collision comparison. |
| 2026-07-24 | Treat strict-prefix relationships as conflicts and equal paths as duplicates. | Runtime mappings must not depend on YAML declaration order. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-24 | Confirmed ANY-144 scope and current PR head. | Run doctor, implement validation, and add tests. |
| 2026-07-24 | Added collision validation and tests; 59 focused tests passed. | Reconcile review documentation and run canonical checks. |
| 2026-07-24 | All implementation, documentation, PR-description, and local validation work completed. | Publish the changes and confirm final CI. |

## Open questions

None.

## Follow-up debt

None expected.
