# ANY-777: Keep waiting for accepted web scenarios

## Status

- State: active
- Owner: agent
- Created: 2026-11-09
- Last updated: 2026-11-09
- Review date: 2026-11-09
- Next action: Review the stale-attachment fix and its recorded Chrome MCP evidence.
- Blocker: None for this frontend fix; canonical frontend-check passed on 2026-11-09.

## Goal

A web form must display a result even when generation takes longer than 60 seconds. Waiting or
retrying reads the accepted session; it must not trigger another paid generation.

## Scope

CE-kit polling, the shared web runtime used by ProposalAI, Brief Decoder, Client Update Writer and
Acceptance Builder, regression tests and SDK documentation. API, DB, provider policy, prompts,
model selection and visual tokens retain their contracts. Kernel demo also consumes the bounded
SDK default; it does not use the web continuation behavior.

## Relevant docs

- `docs/architecture/frontend-boundaries.md`
- `docs/architecture/llm-runtime.md`
- `docs/agent/coding-conventions.md`

## Implementation steps

- [x] Verify provider budget and accepted-session lifecycle.
- [x] Set the SDK window to 600 seconds; continue healthy windows in the web runtime.
- [x] Verify late results, multiple windows, recovery, cancellation and product regressions.
- [x] Run frontend/docs checks and a controlled browser journey exceeding 60 seconds.

### Stale-attachment recovery (authorized 2026-11-09)

- [x] Classify a definite backend 404 or a known incompatible scenario separately from ambiguous failures.
- [x] Add explicit pre-runtime discard in the route owner; retain begin/end protection and unrelated newer/active sessions.
- [x] Open a fresh form without execution, clear effective attachment state, and retain transient retries of the same session.
- [x] Cover both products, URL/storage/reload, all valid modes, failed boot and storage races with regression tests.
- [x] Run web checks/build and Chrome MCP recovery journeys; compare execution/provider/quota records before and after.

No backend contract, provider policy, dependency or design-token changes are needed. A discarded
attachment is only a local reference; this action neither cancels nor starts a backend execution.
Missing scenario identity remains ambiguous, so it preserves the accepted session for retry.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-11-09 | 600s bounded SDK window; web renews only healthy started/running snapshots | 480s physical-call budget plus 120s overhead does not bound queue/recovery time. |
| 2026-11-09 | Preserve TypeScript implementation | This defect belongs to existing browser code; Python remains the repository command interface. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-11-09 | Read task, runtime, shared callers and policy. System Python doctor failed: pytest/pydantic missing; pnpm launcher also fails. | Use the existing project environment and installed tools for validation. |

## Open questions

The historical failure near 33 seconds has no surviving logs; do not claim its cause is established.

## Follow-up debt

Server watchdog/deadline behavior and reload persistence are outside this change.

## Validation results

- Project Python 3.12 doctor passed. System Python 3.14 lacks pytest/pydantic.
- All workspace lint and typecheck passed; generated API contract drift check passed.
- CE-kit: 38 files / 331 tests passed. A prior parallel run exceeded the existing 5s timeout in
  the ESLint-config test; its isolated rerun and the full SDK rerun passed without changing it.
- Web mirror: final full run passed 22 files / 450 tests, including 94 shared-runtime tests.
  This covers all four product suites and mode switching, late completion, multiple 600s windows,
  attached sessions, network/request-timeout recovery, unmount and Copy.
- Documentation validation and generated documentation check passed.
- Canonical frontend-check reached pnpm install, then stopped: registry DNS failure and the
  installed modules require a non-interactive purge confirmation. Dependencies were not purged.
  Its lint/typecheck/test/contract/build phases are validated separately where stated here.
- A parallel workspace test command also failed in CE-kit under load. The full SDK suite passed
  when rerun by itself. Do not count that recursive command as a passing full gate.

## Browser acceptance evidence

Real Next.js frontend, API, worker, canonical artifacts and quota services ran against isolated
SQLite. Test-only fake-provider calls slept 35 seconds per step; its timeout was raised to 60s
only inside the harness. No live model or provider credentials were used. No HTTP response was
fabricated or delayed by browser interception.

The UI displayed the result at 72,293 ms. The real API still returned running at 61,680 ms.
There was one start POST, Copy succeeded, used quota went 0 → 1, reserved went 0 → 1 → 0.
This proves the permitted artificial-delay acceptance path, not model quality or PostgreSQL
production concurrency semantics. Screenshot and trace were captured locally.

## Review

The web loop renews only timeout outcomes carrying a successful started/running snapshot. Failed
GETs retain recovery through the accepted session; actual terminal states retain existing handling.
The controller and active-session guard run after each await. Each bounded SDK window retains
per-request timeout, sleep and abort handling, so extending a window neither restarts execution
nor creates overlapping polling loops. No new transport retries or backend deadline are introduced.

The historical 33-second incident remains unexplained; recovery tests cover its plausible GET
failure class without claiming that incident was reproduced.

- Workspace builds passed for CE-kit, shared UI, result kit, kernel-demo extension and the
  configured product smoke packages. The web production build required execution outside the
  network sandbox to fetch existing next/font resources; compilation and static generation passed.
- Final diff whitespace check passed. The repository-wide forbidden-phrase scan found only
  pre-existing occurrences in unrelated execution reports; those files were left untouched.

## Chrome MCP acceptance review — 2026-11-09

Report-only verification; product source, configuration and tests were not edited in this round.
The default MCP process lacked DISPLAY. A separate instance of the installed Chrome DevTools MCP
1.12.0 was connected over stdio with DISPLAY=:0; global MCP configuration was not changed.
The production Next.js build was served on 31777 and its baked-in rewrite used the real API on
18000. The isolated worker used the documented two artificial 35s fake-provider delays.

| AC | Result | Evidence |
|---|---|---|
| Client window matches provider budget and documents rationale | Passed | 600s constant with 480s physical-call formula and queue/recovery caveat; web renews healthy windows. |
| Running stays pending and a late result is rendered | Passed | 16 poller and 94 runtime tests passed again, including 70s completion and multiple windows. |
| Browser run over 60s shows a result | Passed with artificial delay | Chrome MCP observed disabled submit and generation at 61,000.6ms; real running GET at 61,070.4ms; artifact received at 71,264.8ms; UI confirmed by 85,589.9ms. |

One POST start and one session throughout. Copy showed success and its backend next action returned
200. Used quota was 1, reserved 0 and available 9 afterwards. No console warnings/errors on the
successful run. Brief Decoder, Client Update Writer and Acceptance Builder opened with usable
fields and no error alerts; full new browser generations for those products were not run here.
The mobile form at 390px had no horizontal overflow. Changing mobile emulation reloads the page;
that observation does not prove result persistence or the mobile result view.

Additional observation outside the three AC: a raw ProposalAI URL containing an existing session
id, followed by reload, showed the empty form and made no session GET. The route stores the id,
but ProposalAIProduct drops attach props instead of passing them to ProductRunPage. Brief Decoder
and Client Update Writer share the omission by inspection; Acceptance Builder forwards them.
No configured incoming handoff targets ProposalAI or those other two products, so the observed
ProposalAI case used a manually constructed URL, not a current generated handoff journey.
This pre-existing limitation does not invalidate the ordinary submit/poll/result AC above and was
not fixed during the review. The historical 33s incident remains unproven.

The local API/worker and web server remain up for the user's own inspection. No paid provider
requests, GitHub writes, issue updates, or source fixes were performed in this review.

## Authorized follow-up: restore attached sessions in product wrappers

The user authorized fixing all wrappers with the omission and verifying restoration through
Chrome MCP without a new generation or quota charge. The shared runtime and route owner already
implement the lifecycle; the root cause is missing prop forwarding in three product adapters.

- [x] Forward AttachProps in ProposalAI and Brief Decoder.
- [x] Forward AttachProps in Client Update Writer to its Update mode, using the existing
  MultiModeProduct attachModeId contract. Acceptance Builder keeps its existing Draft contract.
- [x] Test actual product components with useAttachSession: URL restore, reload, transient poll
  recovery, no start POST, unchanged quota readback, and forgetting the session on New task.
- [x] Verify restored results and backend quota in Chrome MCP for all three repaired products;
  retain the existing Acceptance Builder regression coverage.
- [x] Run web tests, lint/typecheck/build and documentation checks.

The optional attach contract selects one declared mode; adding automatic scenario/mode discovery
for arbitrary ReplyDraft/PrepaidRequest or Check sessions is outside this prop-forwarding fix.

### Follow-up outcome

All three product wrappers now forward the existing AttachProps. Client Update Writer declares
Update as its attach mode; Acceptance Builder's Draft contract is unchanged. There is still one
route owner and one shared runtime. Schema/version checks and terminal failure handling remain.

Six new actual-product tests cover successful URL attachment and transient poll recovery,
remounting from the route's persisted tab state, no start POST, unchanged quota readback and
forgetting the session on New task. All 456 web tests passed, including existing Acceptance
Builder and shared runtime cases. Web lint, typecheck and production build passed.

Chrome DevTools MCP verified six restores against the actual API/worker and deterministic fake
provider: URL plus reload for ProposalAI, Brief Decoder and Client Update Writer's Update mode.
Each rendered the same session/artifact and made zero new start requests. ProposalAI remained
used=1, reserved=0, available=9; Brief Decoder remained used=1, reserved=0, available=2. Client
Update Writer has no configured quota policy, so its live proof is no repeated execution rather
than a claim about a nonexistent quota counter.

A direct read of the isolated backend database confirmed exactly one scenario session and one job
per product for the test guest. Provider-call totals were the original two ProposalAI calls,
four Brief Decoder calls and one Client Update Writer call, with no duplicate generation.
The three baseline sessions were created once through the real start API before restoration;
no browser-intercepted result or fabricated network response was used. The test-only artificial
provider delay from the earlier long-run proof was removed for these restoration checks.

This supersedes the previously recorded missing-prop limitation for the supported attach modes.
Automatic mode discovery, new handoff routes and new quota policies are not introduced. Local
services remain available for inspection. The canonical install gate still needs CI confirmation
as recorded earlier; no GitHub/Linear writes or commits were made.

## Implementation plan: restore every mode from server identity

The user requires every Client Update Writer mode. Replace the fixed attach mode model with
server-owned scenario identity: add scenario_id to the shared session response, expose it through
CE-kit, and resolve the matching definition before mounting a mode. Apply the same shared model
to Acceptance Builder. Keep the form and mode switch blocked until identity is known, preserve
retry/abort and tab persistence, reject foreign/unknown scenarios, and never start execution.

Test running and completed sessions in every mode, reload, transient identity-read failure,
unsupported identity, unmount and mode-switch cleanup. Verify all three Client Update Writer modes
through Chrome MCP and compare backend execution counts before/after repeated restoration.

## All-mode restoration completed — 2026-11-09

The prior Update-only boundary is superseded. The session response now carries the stored
scenario_id; the core snapshot and its ExecutionAcceptance subclass preserve it, and CE-kit
validates/maps it to scenarioId. Start response shape, DB schema and quota policy are unchanged.
The generated OpenAPI and SDK contract were regenerated and drift checks pass. Legacy API payloads
still parse, but mode resolution requires server identity and never guesses from output text,
workflow-name heuristics, local input or a default mode.

MultiModeProduct reads identity before mounting its run page, resolves any declared mode and keeps
form/mode switching locked during that read or a retryable failure. Abort/unmount ignores late
responses. Existing tab storage remains the sole persistence owner. Both Client Update Writer's
three modes and Acceptance Builder's Draft/Check use the general model; fixed attachModeId was
removed. The initial loading view is identical on server and first browser render, fixing the
React hydration mismatch when only the browser can read the tab's stored session.

Tests: all 465 web tests and 336 SDK tests passed. The three actual Client Update Writer mode/API
cases additionally assert scenario_id on a queued session before its result exists and after
completion. Twenty API failures exposed by full quick-check came from the inherited quota
acceptance constructor missing the new required field; that constructor was corrected and all
20 failed API cases passed a focused rerun. The remaining unrelated quick-check failure is the
existing activation-marker test requiring passwordless sudo to run as nobody. Full quick-check
is not reported green. Workspace typecheck, web/SDK lint, production build, generated contracts
and documentation checks passed. The PostgreSQL API suite was not counted as evidence because
its fixture skips without a configured test database.

Chrome MCP repeated URL restore and reload for Update, Reply Draft and Prepaid Request on the
final production build. All six checks rendered the original artifact in the correct mode and
made zero start requests. All three final console checks had no warnings/errors. The same test
guest still owns exactly three sessions, three jobs, three action runs and three provider calls,
matching the initial one-per-mode runs. Guest quota rows stayed zero: Client Update Writer has
no configured guest quota policy. No paid provider was called. Isolated SQLite and deterministic
fixtures were used; PostgreSQL production concurrency is not asserted.

The backend identity API and matching frontend must be deployed together for mode restoration.
Local services remain up for inspection. No commit, GitHub write or Linear update was performed.


## Stale-attachment blocker resolved — 2026-11-09

Both multi-mode products now distinguish a definite backend 404 or known incompatible scenario
from ambiguous reads. The former offers explicit New task, which opens an empty form without
starting execution; network/timeout/5xx, missing identity, and malformed responses retain the
session and retry the same GET. Shared copy is translated in all seven locales.

The route owner has an explicit pre-boot discard callback, independent of guarded begin/end.
Cleanup removes only the matching reference, preserves another active/newest session and its
ordering, and clears the route's in-memory ID. The resolver follows its effective ID instead of
re-reading a discarded initial prop. A bare link also preserves an explicitly opened session whose
order is unknown. The fresh form restores keyboard focus to the selected mode. No API/backend,
dependency, quota-policy or design-token change was required.

Canonical frontend-check passed: locked installation, workspace lint/typecheck, all tests
(including 501 web, 336 SDK, 52 shared UI, 57 Atom Lab Node, 339 Atom Lab browser and six
stakeholder-demo Node tests), generated API type drift and all builds. Installation initially
hit esbuild postinstall EPERM inside sandbox; the same gate passed outside it. Documentation
validation passed. Generated docs check initially hit a LiteLLM remote-cost-map import race;
using its supported local cost-map option passed without changing dependencies or source.

Chrome MCP verified real 404 → explicit exit → every mode → reload without restoring the bad ID,
and foreign identity → explicit exit, in both products. One explicitly injected 503 per product
retained the same ID and Retry restored the original result. URL and reload checks restored the
original artifact in all three Client Update Writer and both Acceptance Builder modes, with
zero start requests. On the final canonical build, repeated invalid bare links/discards preserved
another active session (including its unknown-rank state); reload restored that original result.
Final console checks were clean.

After baseline execution, global isolated DB counts remained sessions=10, jobs=10, action_runs=19,
provider_calls=19, execution_reservations=6. Every quota row was unchanged. Acceptance Builder
remained used=2/reserved=0/available=1, also confirmed through its real quota API in Chrome.
Client Update Writer has no configured quota policy: unchanged execution/provider counts prove
no regeneration, without inventing a quota charge. See
[the recorded evidence](any-777-stale-attachment-recovery-evidence.json).

All providers were deterministic fakes and storage was isolated SQLite. No paid provider or
PostgreSQL concurrency run. No GitHub reply or PR edit was made in this follow-up.
