# Execution Plan: ANY-464 review follow-up

## Status

- State: completed
- Owner: agent
- Created: 2026-09-20
- Last updated: 2026-09-20
- Review date: 2026-09-20
- Blocker: none
- Next action: none; implementation and verification are complete.

## Goal

Resolve the confirmed review regressions without expanding ANY-464 beyond the Atom Lab contract
editor: preserve exact string and dictionary payloads, clear errors for removed values, and restore
correct focus and ARIA state after edits.

## Implementation steps

- [x] Add failing browser regressions for all five review findings.
- [x] Separate readable path labels from collision-free internal path identities.
- [x] Preserve multiline unrestricted strings and maintain input errors across subtree mutations.
- [x] Resolve compound-field focus targets and reset validation-owned ARIA attributes.
- [x] Reject Form-mode numbers that cannot round-trip without precision loss.
- [x] Connect the real Chromium suite to canonical `frontend-check` and `full-check` CI paths.
- [x] Run focused and canonical validation, then update the pull request.

## Validation

- [x] `pnpm --filter @anytoolai/atom-lab-browser-tests test` — 22 passed.
- [x] `pnpm --filter @anytoolai/atom-lab-browser-tests browser` — 13 passed in Chromium.
- [x] `pnpm --filter @anytoolai/atom-lab-browser-tests lint`.
- [x] Focused API and architecture tests — 28 passed.
- [x] `python3 scripts/agent/runner.py quick-check` — 1864 passed, 479 deselected.

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-09-20 | Verified all five review findings against the current head and reproduced each in Chromium. | Implement the fixes. |
| 2026-09-20 | Added exact-payload, error-recovery, ARIA, and compound-focus fixes with browser coverage. | Complete. |
| 2026-09-20 | Rebased recoverable input errors when dynamic dictionary keys are renamed. | Complete. |
| 2026-09-20 | Rejected lossy JSON numbers and fixed collection focus, recovery ARIA, and duplicate-key rename behavior. | Complete. |
| 2026-09-20 | Applied exact-number validation to untyped and schema-declared numeric Form controls. | Complete. |
| 2026-09-20 | Made the package's canonical test run state plus Chromium suites and installed Chromium deterministically in both frontend CI paths. | Complete. |
| 2026-09-20 | Fixed the Linux Chromium narrow-layout regression exposed by the newly canonical browser suite by allowing grid cards and long atom titles to shrink and wrap. | Re-run both required CI paths. |
