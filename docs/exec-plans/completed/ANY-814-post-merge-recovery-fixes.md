# ANY-814 — Recover capacity-rejected forms and config-drifted executions

## Status

- State: completed
- Owner: Vyacheslav
- Created: 2026-11-05
- Last updated: 2026-11-06
- Review date: 2026-11-06
- Next action: none for implementation; PR #257 follows GitHub's merge requirements.
- Blocker: none in the implementation; local validation limitations are recorded below.
- Required CI and review: completed for implementation head `85abcb92`.
- Issue: [ANY-814](https://linear.app/paveldik/issue/ANY-814).
- Related issue: [ANY-507](https://linear.app/paveldik/issue/ANY-507), merged in PR #256.
- Delivery PR: [#257](https://github.com/gushinets/anytoolai-platform/pull/257).
- Base: `main` at `4cd2e0aa39b67d648cd40540db0a59a2559fd4f2`.

## Goal and scope

Recover the original execution without a duplicate start or charge. A rejected attempt does not
prove that an earlier send of the same key was rejected. Reading an accepted execution does not
require the configuration or admission permission needed to create a new one.

In scope: shared product-runtime recovery, durable replay/session reads, focused regressions and
the owning architecture docs. Out of scope: paid HTTP/Portal integration, migrations, new access
control systems, provider policy changes and production activation. Commit, push and PR-description
updates were authorized on 2026-11-06 after local review.

Relevant contracts: [scenario sessions](../../architecture/scenario-session-model.md),
[frontend boundaries](../../architecture/frontend-boundaries.md) and
[quota model](../../architecture/quota-model.md).

## Decisions

- Keep one uncertainty record per prepared start. Later 4xx responses, including backend envelopes,
  cannot erase an earlier unresolved outcome. Repeated definite rejections alone do not create
  uncertainty. Capacity rejection retains the key for an unchanged retry; safe edits use a new key.
  An explicit key/hash conflict proves the key belongs to another request and allows a new handle.
- Accepted replay checks owner/scope and request hash, then reads persisted execution/bucket IDs.
  Current config only enriches next actions; missing config grants none. New admission and action
  execution retain current-config checks. Session polling retains its existing version guard.
- The live-canary token authorizes new admission. Accepted matching replay needs no new token,
  including after rotation/removal, consistently with existing public session/result reads. This
  intentionally supersedes ANY-221's config-dependent pre-replay token check. New canary starts
  still fail closed. Atom Lab scope isolation and Result API validation are unchanged; no saved
  visibility flag, backfill or migration is needed.

## Execution

- [x] Deliver `171f767d` and `d255f0d9`: config-independent reads and uncertainty across capacity
  retries, already published in PR #257.
- [x] Trace review findings to older ANY-150/221/414/656 behavior. Reproduce late acceptance after
  config removal and the inverse false lock after definite capacity rejection then HTML 403.
- [x] Add regressions for later generic/quota/identity rejections, actual client timeout, safe
  repeated rejections, canary replay versus new admission and completed legacy action suppression.
- [x] Replace the first-send approximation with the existing uncertainty record; remove the
  config-dependent pre-replay token gate without changing reserve/finalize/release.
- [x] Consolidate current docs and mark the superseded canary ordering as historical.
- [x] Run applicable checks, inspect the final diff and record the baseline environment limitation.
- [x] Review the combined PR and local follow-up; no new confirmed defects found.
- [x] Obtain all required CI passes and reviewer approval for `85abcb92`.

## Validation

Frontend checks reach same-key result recovery and cover field/Submit/mode locks, automatic/manual
retry, explicit key conflicts and fresh-key independence. The timeout case uses an abort-aware fetch
and the actual client request timer. PostgreSQL checks cover original IDs, one execution/reservation, unchanged rows,
counters/events, token rotation, removed scenario/association/product and rejection of new or
foreign starts. Completed legacy replay checks configured actions versus none after removal.

Verification is pinned to implementation head `85abcb92`. Regression tests reproduced
the unsafe unlock, false lock and config-dependent canary behavior before the production changes.
Production acceptance is not claimed.

## Completed CI and review

The [implementation CI run](https://github.com/gushinets/anytoolai-platform/actions/runs/42170441896)
passed all five required jobs: `full-check`, `postgresql-quota-concurrency`, `atoms-proof`,
`baseline (windows-latest)` and `compose-smoke-prod`.
The PostgreSQL 18.6 gate passed all 648 cases without skips. The baseline passed on Linux
(3,031 passed, 12 skipped) and Windows (3,016 passed, 27 skipped); skipped tests are not counted
as executed. Full-check also passed frontend checks and the 247-case product backend suite.
[Reviewer approval](https://github.com/gushinets/anytoolai-platform/pull/257#pullrequestreview-5796647162)
confirmed no merge-blocking defects. Both original CodeRabbit threads were re-evaluated and
resolved by CodeRabbit. Subsequent documentation-only status updates do not change this verified
implementation; GitHub must still validate any later PR head.

## Local validation history and limitations

- Doctor: passed using the managed Python 3.12 environment.
- `frontend-check`: passed lint, typecheck, all 824 unit/component tests, all 88 Atom Lab browser
  tests, OpenAPI drift and production builds. The final focused component run passed all 133 tests.
- PostgreSQL: the full canonical selection passed 644 tests; one unchanged migration test failed
  because the temporary Unix-socket profile supplied no TCP host. That test passed with a loopback
  URL. Three additional late-acceptance regressions passed separately, covering all 648 currently
  selected PostgreSQL cases across those runs. Focused canary/admission/legacy checks also passed
  (18 cases). The disposable local server was PostgreSQL 14; CI uses PostgreSQL 18. The initial
  full-gate exit was a failure, not a claimed fresh full-gate pass.
- Config, architecture, documentation and generated-docs checks: passed.
- Production Python Ruff: clean; changed test modules add no findings over HEAD. Diff check passed.
- Local review: an additional temporary HTTP diagnostic passed both configured/removed-scenario
  cases through actual Atom Lab admission. Authorized replay survives token/config removal;
  unauthenticated Lab access and public replay/polling remain rejected, without new runtime rows.
- `quick-check`: interrupted after about 85% of its 3,043 selected tests. The confirmed failure is
  the unchanged `test_activation_marker_is_readable_by_non_root_api_user`: `sudo -n -u nobody`
  requires a password in this environment. The remaining baseline was not completed; no checks
  were suppressed. This local attempt is not claimed as a pass; the successful CI results are
  recorded above. Sanitized failure context was captured locally with `collect-context`.

No credentialed provider calls, real paid HTTP/Portal integration or production operations were
performed. Temporary PostgreSQL clusters were stopped and removed. The local sudo and temporary
database-profile issues are validation limitations, not unresolved implementation or merge blockers.
