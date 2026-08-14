# Execution Plan: ANY-8 A15 CE Kit MVP API Client closeout

## Status

- State: completed
- Owner: agent
- Created: 2026-08-07
- Last updated: 2026-08-13
- Review date: 2026-08-13
- Next action: none; PR #61 merged and all A15a-c children are complete on `main`.
- Blocker: none

## Goal

ANY-8 is the coordinating parent for A15a (ANY-170, merged in PR #49), A15b (ANY-171, merged in
PR #52), and A15c (ANY-226, merged in PR #62 on 2026-08-10, after this plan was first written). All
three are now complete on `main`. This plan covers the closeout work only: a line-by-line DoD/AC
audit of the parent ticket and all three children against the merged code, and fixing the one real
gap the audit found.

## Scope

### In scope

- Audit every AC bullet in the parent ANY-8 and all three children (ANY-170, ANY-171, ANY-226)
  against `packages/frontend/ce-kit/src` and its tests, file by file. For ANY-226 specifically:
  `src/results/getResult.ts` implements typed `getResult()` over `GET /v1/results/{artifact_id}`,
  `src/results/types.ts`'s `ResultArtifact` carries no raw/debug/provider fields, and
  `test/results/getResult.test.ts` (6 cases: happy path, id percent-encoding, not-found, unavailable,
  malformed/invalid-response, abort) covers its AC.
- Audit for stale "A16 owns `PlatformApiClient`/`startScenario()`/`getQuota()`" references outside
  `docs/exec-plans/completed/`.
- Remove the fake-success stubs (`pollJob`, `getArtifact`, `createHandoff`, `openHandoffConsent`,
  `captureEmail`, `trackClientEvent`) from `src/index.ts`. ANY-8's "Deferred" section explicitly
  defers these capabilities to later tickets (ANY-36, ANY-6/A18, artifact/event backend contracts)
  and states "unsupported capabilities must not ship as fake-success helpers" -- but they still
  shipped fake-success payloads, mitigated only by a README disclaimer. Confirmed zero consumers
  repo-wide (`grep` across `packages/`, `extensions/`, `apps/` found only `index.ts` itself;
  `extensions/kernel-demo-ce` doesn't import `ce-kit` at all yet -- wiring it up is ANY-39, a
  separate blocked-by ticket). Note `createHandoff`/`openHandoffConsent` are removed for a different
  reason than the other four: the `/v1/handoffs` backend (create/get/accept/decline) already exists
  and is in the generated OpenAPI types -- only the CE-kit client helpers are deferred, to
  ANY-222/A18a.
- Delete the now-unused empty placeholder files those stubs lived behind
  (`src/artifacts/getArtifact.ts`, `src/events/trackClientEvent.ts`,
  `src/handoffs/createHandoff.ts`, `src/handoffs/openHandoffConsent.ts`,
  `src/scenarios/pollJob.ts` -- all were `export {}` with no real implementation). `captureEmail` had
  no separate placeholder file; it was defined inline in `src/index.ts` and removed from there
  directly.
- Update the README's opening disclaimer to match (no longer describes stubs present in
  `src/index.ts`; explains why they're absent instead).
- Re-run `frontend-check`/`full-check` after the removal.

### Out of scope

- Any new capability implementation (handoff helpers/A18, email capture/ANY-36, client-event
  ingestion) -- all separate tickets per ANY-8's own Deferred section. `getResult()`/A15c/ANY-226
  was merged separately (PR #62) and is already real on `main`; this plan only needed to fold that
  fact into the README and this doc, since both predated it.
- `renderQuotaState()`, `renderJobStatus()`, `renderError()` -- pure formatting helpers with no
  backend call to fake, not mentioned in ANY-8's Deferred list, left untouched.
- Wiring `extensions/kernel-demo-ce` to consume `ce-kit` (ANY-39).

## Verification

- `python scripts/agent/runner.py doctor` -- passed.
- `python scripts/agent/runner.py frontend-check` -- passed before the stub removal (baseline) and
  again after (typecheck, `pnpm -r test` 216/216 including `test/results/getResult.test.ts`,
  `generate-api-types:check`, build all green).
- `python scripts/agent/runner.py full-check` -- passed before and after the stub removal (backend
  pytest suites unaffected, frontend re-verified).
- `grep -rn "A16 owns" docs/ packages/ extensions/ apps/` (excluding
  `docs/exec-plans/completed/`) -- no matches.
- `grep -rln "pollJob|getArtifact|createHandoff|openHandoffConsent|captureEmail|trackClientEvent"
  packages/ extensions/ apps/` -- only `src/index.ts` before the fix; confirms zero consumers.
- Cross-checked every parent/child AC bullet against a named, matching unit or integration test
  (`test/identity/guestIdentity.test.ts` for single-flight/guest-storage races,
  `test/scenarios/prepareScenarioStart.test.ts` for idempotency-key generation/reuse/isolation,
  `test/integration/scenarioLifecycle.test.ts` for the required
  `create guest -> get quota -> prepare keyed start -> retry -> assert same session/job -> poll ->
  one quota unit consumed` flow plus the `429 quota_exhausted` no-fake-state case,
  `test/scenarios/pollScenarioSession.test.ts` for bounded/cancellable polling and the "never
  starts/replays/configures workflow execution" invariant).
- Scanned all public `types.ts` files (`api/client/types.ts`, `scenarios/types.ts`,
  `quota/types.ts`, `runtime/types.ts`, `identity/guestIdentity.ts`) for
  prompt/provider/model/policy/LiteLLM/PydanticAI/secret leakage -- none found (`quotaPolicyId` is
  a quota rate-limit policy id, unrelated to `provider_policy_ref`).
- Swept every `*.md` file mentioning ANY-8/A15/CE-kit
  (`docs/architecture/frontend-boundaries.md`, `docs/architecture/quota-model.md`,
  `docs/architecture/scenario-session-model.md`, `docs/product-specs/mvp-a2-client-surfaces.md`,
  `docs/product-specs/mvp-scope-source-of-truth.md`,
  `docs/exec-plans/active/mvp-a-mvp-b-linear-epics.md`) -- all describe the current real
  implementation accurately, including `frontend-boundaries.md` already crediting A15c/ANY-226 as
  delivered; no stale claims found beyond the README disclaimer fixed above. Flipped the
  Linear-epics tracker table's "A15 CE-kit parent | ANY-8 | In progress" row to "Done" now that all
  three children are merged to `main`.

## Decision log

- Removed the fake-success stubs rather than replacing them with explicit throwing stubs or leaving
  them with a stronger README disclaimer: zero consumers made removal risk-free, and it's the only
  option that satisfies the literal "must not ship as fake-success helpers" text rather than
  documenting around it. Confirmed with the ticket owner before making the change.
- Did not touch `renderQuotaState()`/`renderJobStatus()`/`renderError()` even though the old README
  disclaimer grouped them with the fake-success stubs -- they don't call a backend or fake a
  success/failure outcome (no I/O to fake), and they aren't named in ANY-8's Deferred list, so
  removing them would be scope creep beyond what the ticket's explicit text requires.
