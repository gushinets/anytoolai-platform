# Execution Plan: ANY-128 Documentation and Generated-Artifact Freshness

## Status

- State: completed
- Owner: agent
- Created: 2026-07-15
- Last updated: 2026-07-15
- Review date: 2026-07-15
- Next action: None; PR #27 merged to `main`.
- Blocker: None.
- Linear: ANY-128

## Goal

Fail quickly when indexed documentation, execution-plan state, or generated repository contracts
drift from canonical sources.

## Scope

- Validate local links, required index links, plan state/location, and active-plan metadata.
- Generate OpenAPI, config, action, event, and DB documents deterministically.
- Add non-mutating generate-docs --check.
- Emit stable error codes with remediation and authoritative guidance.
- Keep recurring gardening manual during MVP.

## Validation

- [x] python scripts/agent/runner.py validate-docs
- [x] python scripts/agent/runner.py generate-docs --check
- [x] focused validator/generator tests
- [x] python scripts/agent/runner.py quick-check (238 passed)

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-15 | Added stable DOC error codes, plan/link validation, deterministic five-document generation, non-mutating drift checks, and real docs CI. | Run the complete baseline and publish after GitHub authentication is restored. |
| 2026-07-15 | Rebased PR #27 onto merged ANY-127 so it inherits pinned pnpm setup; previous red full-check was CI tool provisioning, not validator behavior. | Push with lease and verify fresh CI. |
| 2026-07-15 | Fresh CI passed and PR #27 merged. | Archive this completed plan. |
