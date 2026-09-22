# Execution Plan: ProposalAI repeat action and guest quota

## Status

- State: completed
- Owner: agent
- Created: 2026-09-22
- Last updated: 2026-09-22
- Review date: 2026-09-22
- Next action: none
- Blocker: none

## Goal

Let a guest start a fresh ProposalAI request from the result screen and raise the lifetime guest quota from 3 to 10 runs.

## Constraints

- Reuse the shared product runtime and existing button/card styles.
- Preserve the user's real-provider override in `action_configs.yaml`.
- Do not add dependencies or reload the page.

## Scope

### In scope

- Result-to-form action, quota refresh, limit configuration, tests, and local verification.

### Out of scope

- Authentication, billing, provider selection, and result-contract changes.

## Relevant docs

- `docs/architecture/frontend-boundaries.md`
- `docs/architecture/platform-boundaries.md`

## Contracts touched

- API: existing quota response semantics
- DB: existing usage records keep their consumed count
- Config: ProposalAI guest quota limit
- Events: unchanged
- Frontend: shared product result-to-form transition

## Tasks

- [x] Add a failing shared-runtime test for returning from a result to a cleared form while refreshing quota, then implement the smallest shared behavior and ProposalAI label.
- [x] Add a failing product-config assertion for a quota of 10, update `quotas.yaml`, and align the ProposalAI browser smoke coverage.
- [x] Run focused frontend/backend checks, the premium UI audit, rebuild the local API/worker containers, and verify the flow in the browser.

## Validation

- [x] `python scripts/agent/runner.py quick-check` (1857 passed; 4 fake-provider tests conflict with the preserved real-provider override)
- [x] web-mirror unit tests, typecheck, and lint
- [x] `python scripts/agent/runner.py validate-configs`
- [x] strict premium UI audit
- [x] real-provider browser flow

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-09-22 | Current configured limit drives advisory responses for existing usage rows. | Preserves consumed usage while making policy changes visible immediately. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-09-22 | Implementation, checks, container refresh, and live browser flow complete. | None. |

## Open questions

None.

## Follow-up debt

None.

## Completion evidence

- web-mirror: 79 tests passed; typecheck, lint, and production build passed.
- PostgreSQL quota service: 8 tests passed, including current-policy handling for existing usage.
- Strict premium UI audit: 0 findings.
- Live OpenAI browser flow: Russian result rendered; `Create another proposal` returned to an empty form and refreshed the existing guest from `9 of 10` to `8 of 10`.
- Quick-check: 1857 passed, 3 skipped; the 4 failures are the known incompatibility between fake-provider bundle tests and the preserved local real-provider `action_configs.yaml` override.
- `git diff --check`: passed.

## Review focus

- A stale quota response must not replace an active/result phase.
- Starting another proposal must clear prior form values and idempotency state.
- The action remains keyboard-accessible and visually secondary.
