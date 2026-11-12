# Execution Plan: Shared run waiting progress (ANY-842)

## Status

- State: active
- Owner: agent
- Created: 2026-11-12
- Last updated: 2026-11-12
- Review date: 2026-11-19
- Next action: user review and explicit permission before pushing to GitHub.
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
  Show the 10–40-second expectation initially, then reassurance at 30 and 60 seconds.
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
