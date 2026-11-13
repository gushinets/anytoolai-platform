# Execution Plan: Shared run waiting progress (ANY-842)

## Status

- State: active
- Owner: agent
- Created: 2026-11-12
- Last updated: 2026-11-13
- Review date: 2026-11-19
- Next action: review acceptance-aware messages and complete required CI before merging.
- Blocker: the baseline activation-marker test requires passwordless sudo, unavailable here.

## Goal

Show elapsed time and reassuring waiting hints during generation across all web products.

## Scope

Shared React/TypeScript runtime, optional stored run timestamp, all seven host locales,
component and recovery tests, browser checks and frontend documentation.

## Implementation steps

1. Preserve an optional validated start timestamp in version 1 drafts.
2. Add shared text progress with 30/60-second hints and a timer outside the live status region.
3. Track submission, resume and attachment starts; preserve same-run retry timing.
4. Cover cleanup, thresholds, retries, regeneration and recovery with existing test tooling.
5. Run repository validation and browser acceptance checks; record evidence and limitations.

## Validation

- Environment: Linux, Node 24.22.1, managed Python 3.12.13.
- Base revision: a3e5071f38303bbcf378e0548263889f3202d45f on feature/ANY-842.
- Passed: 259 focused tests covering storage, progress, runtime, own-run recovery, ProposalAI
  and all seven locale message trees. Standalone web typecheck passed.
- Passed: ten Chromium journeys on the local Next development host with mocked Platform API
  responses, across ProposalAI, Brief Decoder and all three Client Update Writer modes in EN/RU
  at Pixel 5 width (393px). Each checked initial/ticking elapsed time, 30/60-second hints,
  no error after 65 seconds, completion cleanup, regeneration with the previous result visible,
  fresh-run reset, terminal error cleanup and no horizontal overflow. Eight opt-in recovery
  journeys also reloaded at 17 seconds without resetting the counter or submitting again.
- Browser inputs were representative task/profile text and a long repeated brief; the original
  attachment's named brief A/profile P1 were not available locally. API/provider execution was
  mocked; no live provider timing claim is made. Russian mobile screenshot inspected visually.
- Passed: complete frontend-check with pinned pnpm 10.34.1 and workspace concurrency 1:
  workspace lint/typechecks, 704 web tests, 336 CE-kit tests, 55 result-kit tests,
  349 Chromium cases, generated API contracts and production builds.
- Passed: validate-docs, generate-docs --check and whitespace checks. Standalone generated-doc
  verification used managed Python with the local LiteLLM model-cost map to avoid a remote
  catalogue import during a documentation-only operation.
- quick-check: 3,652 passed, 12 skipped, 657 deselected; one unchanged failure in
  `tests/test_runner.py::test_activation_marker_is_readable_by_non_root_api_user` because
  `sudo -n -u nobody` reports "interactive authentication is required". No test was weakened,
  excluded or marked expected-failure. Config, architecture, docs and generated-doc gates passed.
- full-check reproduced the same baseline outcome: 3,652 passed, 12 skipped, 657 deselected,
  with only the unchanged sudo-dependent activation-marker failure. It stopped at that gate,
  so its downstream product-suite stage did not run. The standalone frontend-check passed in full.

## Decision log

- User confirmed TypeScript implementation because this ticket changes the existing web runtime.
- Production measurements: ProposalAI 8–35 seconds, Brief Decoder 13–42 seconds,
  Client Update Writer 4.5–13 seconds; testers reported discomfort from about 20 seconds.
  Once the start is accepted, show the 10–40-second expectation initially, then reassurance
  at 30 and 60 seconds. While submitting, show a neutral confirmation hint at every duration.
- Use the client clock because scenario status has no server start timestamp. Attachment timing
  starts when locally attached; legacy saved runs start timing when resumed.
- Keep the elapsed counter outside the polite live region; announce only status/hint changes.
- Reuse shared tokens, existing type scale and result-card layout; no animation or dependencies.
- ANY-777 owns polling timeout correctness; leave polling, quota and idempotency behavior intact.
- Pass submission time directly to the async start continuation; no mirrored state ref is needed.

## Progress log

- 2026-11-12: Read the task, shared runtime, storage callers and repository guidance. System
  Python doctor failed (missing pytest/pydantic); managed Python 3.12 doctor passed.
- 2026-11-12: Added validated optional timing without changing storage version; implemented
  shared progress and seven translations. Same prepared-start retries retain timing as well as
  accepted-session retries. Timer cleanup and quiet live-region behavior have focused coverage.
- 2026-11-12: Focused tests and all ten mocked Chromium journeys passed. Initial validation
  encountered sandbox network/browser restrictions; rerunning with the needed permissions.
  Reverted Next's automatic manifest/lockfile edit and restored the pinned toolchain; no
  dependency changes are part of this ticket.
- 2026-11-12: Full frontend validation passed. Baseline completed with the sole sudo-dependent
  environment failure above; collecting sanitized failure context and running full-check.
- 2026-11-12: Full-check confirmed the same single environment failure. Implementation and
  task-specific acceptance checks are complete; sanitized context collected. No backend/provider
  live run, GitHub write or Linear status/comment update was performed. Commit locally as requested;
  pushing requires the user's explicit permission under their supplied repository rules.
- Repository terminology check found pre-existing local review-command references in unrelated
  ANY-17, ANY-339, ANY-391, ANY-221 and ANY-227 documents; those files are unchanged.

## Follow-up debt

- Server-provided `started_at` on the scenario-session status would let attached handoff sessions
  show the true elapsed time. This is out of scope here.

## Review round 1 implementation plan

1. Merge origin/main at 7c22bf20, retaining both shared-runtime test additions in the conflict.
2. Expose elapsed time as an accessible timer with live announcements off, outside the status
   region; retain the existing stage-change announcements and interval cleanup.
3. Use the existing safe-capacity-rejection predicate when choosing a start timestamp. A proved
   rejection starts timing afresh on retry while retaining the prepared request/key. Ambiguous
   attempts and accepted sessions keep their original timing.
4. Reproduce the findings with tests, including delays above 60 seconds, both retry buttons,
   and ambiguous 5xx followed by a capacity rejection. Run focused and frontend checks, the
   merged baseline and docs validation; record limitations without weakening checks.

### Review round 1 progress

- 2026-11-13: Read all PR inline comments (no replies); confirmed both P2 findings. Managed
  Python doctor passed. Merged main's data-processing-notice change, preserving both conflicting
  test additions; 115 shared-runtime and notice tests passed before applying review fixes.
- Merge commit: ffb1447d; includes origin/main 7c22bf20 without rewriting published history.
- Reproduced both findings before fixing: the accessible timer query failed, and delayed clean
  capacity retries through both buttons incorrectly entered the long stage. The final regression
  matrix covers repeated clean rejections and repeated capacity rejections following an ambiguous
  5xx, preserving the request key in each case. Ordinary submit remains disabled for ambiguous
  starts, so that case exercises its reachable Try again path.
- Changed the counter to `role="timer"` with `aria-live="off"`; the status region still excludes
  ticking content. Timestamp selection reuses `capacityRejectedSafely`, keeping the existing
  positive-proof boundary instead of adding another uncertainty flag.
- Passed: 219 focused runtime/progress/recovery/handoff tests, web typecheck and lint.
- Passed: six Chromium checks on the local development host with mocked API responses,
  ProposalAI at Pixel 5 width in EN/RU. The browser accessibility tree includes the elapsed
  timer; live announcements are off and status text stays unchanged across ticks. Both clean
  capacity-retry buttons start at zero after 65 seconds, while 5xx then capacity rejection keeps
  elapsed time. All paths preserve the idempotency key, persist the correct timestamp through
  reload without another start, and remove the timer on completion. No browser page errors.
  Native screen-reader audio was not tested. The first navigation exceeded 30 seconds during
  initial dev compilation; all six checks passed after compilation completed.
- Passed: full frontend-check after merge and fixes: 733 web tests, 336 CE-kit tests,
  55 result-kit tests, 349 Chromium cases, all workspace lint/typechecks, generated API contracts
  and production builds. Documentation validation and whitespace checks passed.
- Merged quick-check: 3,678 passed, 12 skipped, 657 deselected; the only failure remains
  `tests/test_runner.py::test_activation_marker_is_readable_by_non_root_api_user`, with sudo
  requiring interactive authentication. No tests were weakened or excluded. Config, architecture,
  documentation and generated-doc checks passed. Sanitized failure context collected.
- No dependency or lockfile changes. Full-check was not repeated because its baseline gate
  remains blocked by the same environment requirement; the complete frontend gate was run above.
  No GitHub comments/review resolution, PR edit, push or live-provider call in this follow-up.

## Review round 2 implementation plan

1. Fast-forward to reviewed PR head e63b9d70, retaining its main merges. Read inline comments
   and replies; verify the pre-acceptance retry path against the shared runtime.
2. Use the existing submitting/running phase as the message boundary, independent of elapsed
   time. Submitting shows the host Starting status plus a neutral confirmation hint at every
   duration; accepted running sessions retain product status and timed generation hints.
3. Add the confirmation hint in all seven host locales. This covers both the long-stage
   server claim and affirmative slow-stage/product status strings across all shared products.
4. Test two ambiguous failures followed by a delayed pending retry, then acceptance without
   resetting elapsed time or the request key. Check normal/slow/long presentation transitions.
5. Run focused, frontend, baseline and documentation checks; distinguish mocked browser
   evidence from live provider execution, and record limitations without weakening tests.

### Review round 2 progress

- Read all inline comments; no replies. Confirmed the shared renderer uses generation copy
  before start acceptance, including product-specific status and several slow-stage translations.
  Fast-forwarded to e63b9d70; managed Python doctor passed. No separate acceptance state needed.
- Reproduced four failures before fixing: initial pending status in both terminal outcomes,
  plus delayed ambiguous 503/network retries falsely claiming server-side generation.
- The existing phase now selects the status and hint in the shared renderer/component.
  Added one confirmation message in all seven host locales; running hints and timing remain
  unchanged. No retry, polling, persistence, idempotency or dependency changes.
- Passed 123 focused component/runtime tests, including pending-to-running transitions at
  normal, slow and long thresholds; ambiguous retries preserve elapsed time and request keys.
- Passed four Chromium journeys with mocked API responses: ambiguous 503/network failures,
  EN/RU at Pixel 5 width, delayed pending retry, quiet accessible timer, acceptance without
  resetting time, reload continuity and completion cleanup. No browser page errors.
- Passed complete frontend-check: 738 web tests, 336 CE-kit tests, 55 result-kit tests,
  349 Chromium cases, workspace lint/typechecks, generated API contracts and production builds.
  Documentation, generated-doc and whitespace checks passed.
- Baseline: 3,695 passed, 12 skipped, 657 deselected, two failures. The architecture source
  scan encountered a temporary CE-kit fixture that the parallel frontend test deleted; the
  complete provider-boundary test module passed when rerun after frontend-check. The remaining
  activation-marker failure is unchanged: sudo requires interactive authentication. No tests
  were weakened or excluded. Sanitized failure context collected.
- Full-check was not repeated because its baseline still requires unavailable passwordless
  sudo; its downstream product-suite stage remains unverified. No live provider run or native
  screen-reader audio check. GitHub review comments and resolution remain outside this fix.
