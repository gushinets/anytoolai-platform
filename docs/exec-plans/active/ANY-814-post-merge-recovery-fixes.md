# ANY-814 — Recover capacity-rejected forms and config-drifted executions

## Status and scope

- State: active
- Owner: Vyacheslav
- Next action: review required CI and findings on PR #257 before merge.
- Created: 2026-11-05.
- Last updated: 2026-11-05
- Review date: 2026-11-05
- Blocker: none locally; required CI must validate the updated PR head.
- Issue: [ANY-814](https://linear.app/paveldik/issue/ANY-814).
- Related completed issue: [ANY-507](https://linear.app/paveldik/issue/ANY-507).
- Base: `main` at `4cd2e0aa39b67d648cd40540db0a59a2559fd4f2`, merged PR #256.

The two validated P2 findings are the [capacity-rejection form lock](https://github.com/gushinets/anytoolai-platform/pull/256#discussion_r4479036352)
and [config-dependent accepted replay](https://github.com/gushinets/anytoolai-platform/pull/256#discussion_r4479189233).
The legacy guest replay dependency predates ANY-507; the reservation path inherited it.

## Intended behavior

1. A definite `quota_capacity_reserved` rejection keeps the prepared key available for an
   unchanged retry, but does not mark an unaccepted request as an active execution. Fields,
   ordinary Submit, mode switching and the shell's busy indication unlock only when that key
   has no earlier unresolved send. Edited input gets a new key when editing is safe. Ambiguous
   failures and accepted/attached executions retain their existing locks, including after a
   subsequent capacity rejection.
2. Owner/hash-checked accepted replay returns persisted session/job/result and original bucket
   even if the current scenario/product association is absent. Current config only enriches
   next actions when available; absent config grants no actions. New starts and action execution
   still require current configuration. Apply this to reservation/legacy replay and the session
   snapshot read that the client polls immediately after replay.

No paid HTTP, Portal/access/outbox integration, schema migration, production activation or
general runtime/UI refactor belongs to this issue.

## REV-1 follow-up — 2026-11-05

Read-only review of `171f767d` confirmed that a timed-out first start can still be accepted after
its retry returns `quota_capacity_reserved`. A controlled PostgreSQL schedule reproduced that
late acceptance; a UI probe observed fields, Submit and mode selection incorrectly unlocked.

- [x] Remember unresolved outcomes per prepared start across automatic and manual retries.
- [x] Unlock capacity rejections only when that key has no unresolved earlier send; retain
  same-key recovery and the capacity-specific message otherwise.
- [x] Cover first/repeated definite rejection, uncertain automatic/manual retries, late accepted
  execution/result recovery and the actual shell mode guard with regression tests.
- [x] Re-run affected frontend and documentation checks, review the final diff and prepare the
  PR #257 update.

The backend replay/finalization changes stay at their already verified implementation. Required
CI passed for `171f767d`; it is historical evidence until the follow-up head is checked.

## Execution

- [x] Reproduce findings independently; create a related follow-up issue and isolated branch.
- [x] Run doctor; read quota/scenario/client boundaries and relevant callers/tests.
- [x] Add frontend and PostgreSQL regression tests for the required behaviors.
- [x] Make the smallest shared-runtime and persisted-readback changes.
- [x] Verify identity/hash safeguards and unchanged terminal/quota semantics in regression tests;
  retain the existing early internal-only/live-canary check and scenario-version guard.
- [x] Run focused suites, required applicable repository checks and document real limitations.
- [x] Prepare the isolated delivery branch and template-compliant PR linked from ANY-814.

## Validation strategy

Frontend tests cover same-key retry, editing/new key, mode switching, busy indication and
existing ambiguous/attached-run locks. PostgreSQL tests exercise a real fake-provider worker
through canonical success and one consumption, then remove scenario configuration or product
association and replay the same key for guest and typed-paid owners. Verify original IDs,
unchanged rows/counters, empty next actions without config and normal rejection of new requests.
Legacy replay and shared checkpoint tests cover the old path without synthesizing reservations.

Doctor passed before implementation. Earlier validation probes are evidence for the defects,
not evidence for the fixes: the capacity probe failed its three unlock assertions; two unchanged
replay controls passed and four config-removal/disassociation probes failed as expected.

## Results

### Initial implementation (`171f767d`)

Implemented capacity-specific unlock with prepared-key retention and optional configuration lookup
only for accepted replay/session reads. New admission and next actions retain strict configuration
requirements. Missing definitions expose no next actions; Result API validation is unchanged.

- Focused frontend regression suite: 150 tests passed.
- Complete `frontend-check`: lint/typecheck, 809 unit/component tests, 88 Atom Lab browser tests,
  generated OpenAPI drift check and production builds passed.
- New PostgreSQL replay regression subset: 16 tests passed (12 reserved guest/typed-paid cases
  and four legacy guest cases). Includes a real worker with a fake provider for completed runs,
  HTTP polling/result reads, unchanged IDs/events/quota counters and negative admission checks.
- `validate-configs`, `validate-architecture`, `validate-docs`, `generate-docs --check` and
  `git diff --check` passed. Production Python files have no Ruff findings; the changed PostgreSQL
  test modules retain only the same 16 findings present in `origin/main`.
- Complete `postgresql-check`: all 637 selected tests passed on a disposable PostgreSQL 18
  instance. The canonical runner exited successfully; collection separately confirmed the count.
- Additional scenario unit/API and live-canary token checks: eight passed, 55 PostgreSQL-marked
  tests deselected in this focused run (covered by the complete PostgreSQL gate).
- `quick-check`/`full-check` have not been run locally for this change; required CI must validate
  the published head. No paid HTTP integration or credentialed provider calls were exercised.

### REV-1 remediation

The prepared handle now remembers whether any send had an unresolved outcome. The flag is set
before automatic retry and on other unknown start outcomes (including unreadable acceptance).
Capacity rejection changes the message but cannot discard that history. Existing successful-start
tracking still resumes polling, and each new logical submission has a distinct handle.

Six permanent regression cases cover repeated definite rejection; gateway timeout, network loss,
manual 5xx retry and unreadable acceptance followed by repeated capacity rejection; same-key
recovery through polling/result rendering; a subsequent new key remaining editable; and the actual
Client Update Writer mode-switch/busy-warning guard. Five failed before the production fix, while
the definite-rejection controls passed. After the fix all 11 selected capacity/uncertainty tests
passed; the other 113 tests in those files were filtered out of that focused run.

Doctor, config/architecture/docs/generated-docs validation and diff check pass. The first complete
frontend run passed lint/typecheck/unit checks but Chromium launch failed inside the sandbox
(`Operation not permitted`). The complete canonical `frontend-check` then passed with browser
execution permitted: lint/typecheck, 815 unit/component tests (52 shared UI, 327 CE-kit, 436 web),
88 Atom Lab browser tests, OpenAPI drift check and production builds. No tests were suppressed to
obtain this result. Backend behavior and migrations are unchanged; the earlier 637 PostgreSQL
passes are reused rather than claimed as a new local run. Required CI must validate the follow-up
head after publication.
