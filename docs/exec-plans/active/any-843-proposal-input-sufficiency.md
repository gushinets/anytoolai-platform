# Execution Plan: ProposalAI input sufficiency (ANY-843)

## Status

- State: active
- Owner: agent
- Linear: ANY-843
- Created: 2026-11-13
- Last updated: 2026-11-16
- Review date: 2026-11-20
- Next action: review the separately reopened delayed-quota finding; live model smoke still needs a valid provider key.
- Blocker: local baseline requires passwordless sudo for the unchanged activation-marker test;
  round-3 live model smoke is blocked by an expired provider API key.

## Goal and boundaries

Missing task descriptions and missing information about the freelancer must produce localized
inline hints at their respective fields, never a copy-ready proposal. Preserve empty/length
validation. Short meaningful inputs, recipe-writing work, honest beginners, and profiles lacking
a particular required skill remain valid. An experience gap is not missing profile information.

The proposed minimal change reuses A04 and A06, retains the public text/gaps shape, and adds no
provider call, dependency, generic atom schema, or workflow DSL feature. Semantic rejection still
completes the backend workflow and consumes quota. The owner explicitly approved retaining this
policy. Python covers backend tests; the existing frontend is TypeScript.

## Implementation plan

1. Reproduce the exact pairs `№№№` / `привет`, `Напиши рецепт борща` / `привет`, and
   `привет` / `1234`, plus empty inputs and a meaningful short counterexample. Record SHA,
   environment, inputs, session/artifact identifiers, complete output and observed quota.
2. Add product-owned `missing_task_description` and `missing_profile_information` categories to
   A04, distinct from `experience_gap`; align the composer, renderer contract and Python tests.
3. Decode known categories into localized field errors before committing a result in the shared
   runtime. Preserve input and selection; clear the terminal request, draft run and previous
   result; focus the first invalid field. Keep stale-response and idempotency protections.
4. Add hints in all seven UI locales. Preserve shared-ui tokens and existing accessible fields.
   Reject unknown/malformed categories safely; retain compatibility with valid old artifacts.
5. Test field mapping, no result/copy/view activation, correction and fresh submission, prior
   results, unmount, attached/resumed sessions, and other product runtime behavior.
6. Run eight input families in Russian, English and Spanish, twice each (48 workflow runs).
   Inspect full outputs and language on valid cases. If classification fails consistently,
   compare those cases on Sol/Terra using backend configuration. Verify browser behavior and
   quota, run applicable repository checks, and record remaining acceptance limits.

## Scope

Product prompts, workflow taxonomy, renderer contract, ProposalAI UI and messages, the optional
runtime output-to-field-errors hook, frontend tests, Python product/API tests, and existing eval
fixtures/evidence. Brief Decoder's similar need belongs to ANY-849. Other products require shared
runtime regression checks; code inspection alone does not confirm semantic-input defects there.

## Initial evidence

- Branch `feature/ANY-843`, clean checkout at `8a0ae64773c16482301ccde4978604443269a785`.
- Managed Python 3.12.13 passes repository doctor. System Python 3.14 lacks pytest and pydantic;
  use the managed environment for checks. Node is 24.22.1.
- No local Docker services were initially running. Starting the repository's isolated local
  live stack with canonical quota; production version and behavior are not yet verified.
- A04 currently permits only `experience_gap`; the UI accepts any string `text` as a result.
  These are code observations, not a claim that a live model reproduced the historical report.
- Live baseline on the identified local build reproduced all three reported failures. Symbols plus
  a greeting yielded an English request for a brief; recipe plus greeting yielded a Russian offer
  to write it; greeting plus digits yielded a Russian clarification as a successful text result.
  A short recipe task with a copywriter profile produced a valid Russian proposal.
- Baseline model: `openai/gpt-6-luna`, medium effort, two provider calls per run. Four runs cost
  USD 0.00356615 in the provider ledger. This is local live evidence, not production evidence.
- Existing ProposalAI/shared runtime frontend tests before changes: 150 passed. The sandboxed
  backend baseline stalled after 57 tests; it is not claimed as a completed baseline test run.
  Focused backend tests after changes passed outside the sandbox (69 tests).

## Implementation decisions

- Parse the result once in the product definition, then let an optional `resultFieldErrors` hook
  map that parsed result before any display or activation commits. This is equivalent to the
  proposed output hook without parsing the same network payload twice.
- Restored runs mark only fields that still equal the submitted input. Attached results without
  local input can mark only empty form fields. Rejection clears its saved run and previous result.
- Current quota behavior and the existing stack were explicitly approved before product edits.


## Acceptance evidence — 2026-11-13

| Criterion | Local result |
| --- | --- |
| Missing task/profile information | Correct missing-input categories in all 48 planned RU/EN/ES workflow runs; 18 rejected and 30 accepted. |
| No false ready proposal | Real RU and EN browser runs show inline hints, no proposal/Copy, and no `web.result_viewed` request for the rejected session. |
| Empty fields and valid short inputs | Empty and whitespace submissions create zero browser start requests. Short design tasks, recipe-writing, beginners and unrelated experience remain accepted. |
| Language on valid briefs | All 30 valid matrix outputs manually inspected by the agent: selected proposal language matches. Mixed-source-language cases included. No ANY-771 language failure observed in this sample. |
| Exact QA regressions | Repeated all four baseline pairs after changes: all three invalid pairs now have the expected categories; the short recipe/copywriter pair remains valid in Russian with automatic language. |
| Correction and quota | Each browser flow creates one rejected run and one corrected run. UI quota 10 → 9 → 8; database reservations both `consumed`, zero reserved units; two provider calls per run. |
| Recovery/accessibility | Deterministic tests cover all seven locales, field-specific focus, unchanged input/tone/language, correction/new idempotency key, previous result removal, stale draft fields, attach/resume and unmount. |

The candidate matrix used `openai/gpt-6-luna`, medium effort: 96 physical provider calls,
USD 0.03470666 ledger-estimated cost. No semantic-classification failures required the conditional
Sol/Terra comparison. The exact-input recheck and browser runs are additional bounded regression
checks, separate from the 48-run matrix. Human acceptance remains pending.

Four of six short logo/design cases reported an unnecessary ordinary `experience_gap` (RU attempt
1, EN attempts 1 and 2, ES attempt 2). These inputs were accepted and produced proposals. The raw
category mismatch is preserved in the review evidence; this is a gap-quality caveat, not a missing-
input-classification pass disguised by changing expectations. Do not extend this ticket into
unbounded proposal-quality tuning. This meets the input-sufficiency goal for this iteration,
subject to the documented environment blocker and owner review.

## Verification and review notes

- Managed Python 3.12 doctor, config, architecture, docs and generated-doc checks passed.
- Focused backend product/API tests: 69 passed. Complete Python product suite: 264 passed.
- Complete web-app suite: 722 passed across 28 files, including the additional single-field focus
  cases and all products sharing this runtime. Frontend typecheck passed.
- Canonical frontend lint initially caught an untyped mock assertion in a new test; fixed it.
- The next frontend run passed lint/typecheck, then hit the unrelated CE-kit
  `reactHooksAppliesToTsFiles` test's 5-second timeout (335 other tests passed). The unchanged test
  passed alone in 2 seconds. A canonical frontend retry with
  `npm_config_workspace_concurrency=1` passed the entire frontend gate: lint, typecheck, unit
  tests, 349 Chromium tests, generated API-contract drift check and all builds. No tests or
  timeouts were altered. CE-kit: 336 passed; shared-ui: 55 passed; web app: 722 passed.
- Canonical full-check baseline: 3,701 passed, 1 failed, 12 skipped, 657 deselected. Failure:
  `tests/test_runner.py::test_activation_marker_is_readable_by_non_root_api_user`;
  `sudo -n -u nobody` reports that interactive authentication is required. The runner and this
  test are unchanged. No test was skipped or weakened to hide the environment blocker.
  Repository `collect-context` diagnostics were collected. Later frontend/product stages were
  invoked separately because full-check stops at this baseline failure.
- Chrome connector could not start without an X server. Installed Playwright with headless Chrome
  completed both real-browser flows. An initial browser driver used the wrong Russian Copy label;
  corrected the driver and reran both flows. Stored request payloads were separately checked using
  their real `event_type` field: zero rejected-result events and one corrected-result event each.
- Self-review checked product parsing, taxonomy validation, workflow consumers, saved-run ownership,
  stale responses, attach cleanup, idempotency, quota and result events. No existing PR was found
  for this branch, so there were no inline thread replies to read. No GitHub/Linear writes made.
- Production deployment and candidate CI are unverified; these are local worktree changes.


Evidence files:

- [Baseline outputs](../../../tests/fixtures/proposal_ai_eval/acceptance/any-843/baseline.jsonl)
  and [exact-input recheck](../../../tests/fixtures/proposal_ai_eval/acceptance/any-843/regression.jsonl).
- [48 candidate outputs](../../../tests/fixtures/proposal_ai_eval/acceptance/any-843/candidate.jsonl),
  [per-run review](../../../tests/fixtures/proposal_ai_eval/acceptance/any-843/review.json), and
  [environment/source hashes](../../../tests/fixtures/proposal_ai_eval/acceptance/any-843/environment.json).
- [Browser outputs and requests](../../../tests/fixtures/proposal_ai_eval/acceptance/any-843/browser.json),
  [quota/provider ledger](../../../tests/fixtures/proposal_ai_eval/acceptance/any-843/browser-ledger.json),
  [Russian hints](../../../tests/fixtures/proposal_ai_eval/acceptance/any-843/hints-ru.png), and
  [English hints](../../../tests/fixtures/proposal_ai_eval/acceptance/any-843/hints-en.png).


## Final disposition

Implementation and local acceptance checks are complete. Keep this plan active for owner review;
no issue status, GitHub review, commit, push or deployment was performed. The task's plan was
updated with the same outcome. Test web/API/worker services started for this work were stopped
without removing the database volume. The 48-run matrix and full-output agent review do not
replace product-owner acceptance or production/CI verification.


## Review round 1: retain errors for unchanged inputs

The owner authorized the fix and regression tests after verification on `f1acefd6`.
The current submit path replaces server-derived errors with required/length validation, allowing
another quota-consuming start when a rejected field has not changed. The existing test corrected
both fields before submitting and missed this transition.

Implementation plan:

1. Keep the last semantic rejection's input and per-field errors together in the shared runtime.
   Combine matching errors with structural validation on submit and edited-field revalidation.
   Structural errors take precedence; returning to a rejected value restores its semantic error.
2. Retain rejection knowledge across edits and network retries; replace it on the next semantic
   verdict and clear it on successful result/New task. Existing stale-session guards remain the
   authority for accepting a result. Do not persist another draft format or collect error history.
3. Add regression cases for either partially corrected field, unchanged submit, tone/language-only
   edits, reverting a field, structural errors, successful correction and recovery/reset behavior.
4. Run focused red/green tests, the shared runtime/product suites, frontend gate and docs checks.
   This is a frontend state fix; prompts, provider policy and quota finalization are unchanged.

Implementation and verification:

- The shared runtime retains the latest rejection with its input values. Both submit and live
  field validation merge matching semantic errors with structural errors. A successful result or
  New task clears the rejection. Draft persistence and the existing stale-response guards are
  unchanged; rejected-value memory lasts for the current mounted page.
- Eight new regression cases failed before the fix and passed afterward. The three focused
  product/runtime/handoff test files passed all 221 tests. Recovery tests additionally check
  blocked resubmission and restored hints when an edited draft returns to rejected input.
- Repository doctor and documentation validation passed. Canonical frontend-check passed with
  serial workspace execution: lint, typecheck, 769 web-app tests, 336 CE-kit tests, 55 shared-ui
  tests, 349 Chromium tests, generated API-contract drift check and all builds.
- No live model calls, backend full-check, production or CI verification were repeated for this
  frontend-only fix. The earlier full-check sudo blocker remains. The owner subsequently
  authorized committing, pushing and updating the PR description with these results.
- A repository text scan found pre-existing local-command wording in unrelated execution plans
  for ANY-17, ANY-221, ANY-227, ANY-339 and ANY-391; those files were left untouched.

## Review round 2: compare the values sent to the backend

The owner authorized this fix and regression tests for both fields after verification on
`3fed43b6`. A formatting-only edit changes the raw textarea value but not the normalized request;
raw equality therefore loses a known error and allows a duplicate, quota-consuming start.

Implementation plan:

1. Add a product-owned normalization contract preserving form keys. ProposalAI reuses the same
   `trimBackendWhitespace` normalization for request mapping and rejection matching. Raw form and
   draft values remain unchanged; products without the contract retain their existing behavior.
2. Use normalized values for the rejection snapshot, submit/live validation and the existing
   recovered-result comparison. Preserve structural error precedence, stale-session guards,
   network retry idempotency and the approved quota policy.
3. Add red/green regressions for both fields: adding/removing outer whitespace, Unicode whitespace,
   true payload changes (including inner newlines and U+FEFF), preserved drafts, recovery and
   successful correction. Keep the existing partial-correction, revert and tone/language tests.
4. Run focused product/runtime tests, the canonical frontend gate and documentation validation.
   No new dependency, persisted error history, prompt or backend changes are needed.

Implementation and verification:

- ProposalAI's `normalizeValues` uses `trimBackendWhitespace` for both text fields and is shared
  by its request mapper and the runtime's rejection matching. The runtime snapshots normalized
  values and compares them during submit, live validation and recovered-result handling.
- Added 22 regression cases across both fields. Before the fix, 18 whitespace/recovery cases
  failed while four actual-payload-change controls passed. After the fix, all 243 tests in the
  focused ProposalAI/runtime/handoff suites passed. Cases also assert raw draft preservation,
  blocked start/events, invalid-field focus and a fresh request after substantive correction.
- Recovery cases exercise the existing defensive stored-draft contract; they do not establish
  that a user can edit a locked in-flight form to produce those differing snapshots.
- Managed Python 3.12 doctor, architecture and documentation validation passed. Canonical
  frontend-check passed with serial workspace execution: lint, typecheck, 791 web-app tests,
  336 CE-kit tests, 55 shared-ui tests, 349 Chromium tests, generated API-contract drift check
  and all builds. Live model calls and backend full-check were not repeated for this frontend-only
  change; the earlier sudo environment blocker remains. Production and CI were not checked.
- The first frontend gate caught an unsafe JSON member access in a new draft assertion. Replaced
  it with a structural assertion; the rerun passed the complete gate.
- The owner subsequently authorized committing, pushing and updating the PR description.
  Rejected-value memory still lasts only for the current mounted page; this change adds no
  persisted validation state.

## Review round 3: exhausted corrections and old-client admission

The owner authorized both fixes and regression tests, including a mandatory request contract
marker. Review reproduced an extra START after last-unit semantic rejection in both quota/result
response orders, and old frontend modules rendered/copied a saved missing-input clarification.

Implementation plan:

1. Derive exhausted idle-form availability from the latest accepted quota snapshot, preserving
   inline hints. Use the same condition in button/submit guards and quota feedback. Leave active
   runs, accepted retries and completed-result visibility intact; reservations are not exhaustion.
2. Require `result_contract: proposal_ai.field_errors_v1` in ProposalAI's input schema and send it
   from the web product and eval collector. Bump the input schema version; retain scenario/workflow
   and output identities so existing completed results remain readable. Reuse current schema
   validation before admission/reservation and before worker steps, without a generic gate or DSL.
3. Test missing/unknown markers before any job/reservation/provider call, valid new requests,
   historical results and exact idempotent replay. Exercise an old queued request under the new
   schema: it must fail before a provider call and release its reservation. Old browser tabs must
   reload before creating any new run; their existing generic error UI cannot show new reload copy.
4. Cover both quota/result response orders, positive/failed/stale quota reads, preserved hints,
   correction and handler-level submit blocking. Add current-client marker and old-client rejection
   regressions; update affected schema assertions and eval input contracts, preserving old evidence.
5. Run targeted backend/frontend red-green tests, product/eval suites, config/architecture/docs
   checks and frontend-check. Check the marker's effect on A06 context before deciding the live
   validation scope. No commit, push or GitHub writes are part of this authorization.

Implementation and verification:

- Idle-form exhaustion is derived from the accepted quota snapshot, shared by button state,
  submit guard and quota feedback. Field hints remain visible regardless of whether quota or
  result resolves first. Completed-result regeneration and accepted network retries are unchanged.
- Input schema version 2 requires `result_contract: proposal_ai.field_errors_v1`. The web mapper
  and eval collector send it; drift assertions compare both with the backend schema. Existing
  admission validation rejects missing/unknown/null markers before any execution or reservation.
  Historical eval suites retain their original inputs and hashes; new suites declare the marker.
- Legacy replay returns the existing job. Completed historical results and Copy remain available.
  An unmarked queued job fails before provider calls and releases its reservation under the new
  worker. Scenario, workflow and output identities remain unchanged to preserve those results.
- Before the fix, both exhausted-quota response-order regressions failed while four control
  cases passed; unmarked input was admitted. After the fix, 249 focused frontend tests and 74
  focused API/product tests passed, followed by 533 broader product/eval/API-contract tests.
- Config, architecture and documentation checks passed. Generated documentation was current in
  quick-check; a separate sandboxed invocation failed during LiteLLM import. The first frontend
  gate hit an existing CE-kit ESLint test's five-second timeout; its isolated repeat passed.
- Six live smoke attempts (both fields missing and valid recipe input, each in RU/EN/ES) reached
  the new contract but produced no model output: the provider reported an expired API key at A04,
  followed by deployment cooldown. This is blocked evidence, not a semantic pass. No prompt/model
  change was made. A live unmarked request returned 422 with unchanged session/job/reservation/
  provider-row counts. The local stack was stopped and its database volume preserved.
- Final frontend stages passed: lint/typecheck, 336 CE-kit tests, 55 shared-ui tests, 349 Chromium
  tests, 797 web tests, generated API-contract drift check and all builds. The broad web run first
  caught a locale test's outdated exact request assertion; adding the mandatory marker fixed it.
  Repeated all web tests and completed the remaining canonical stages separately, without
  repeating the already-passing browser suite for a test-only assertion change.
- Canonical quick-check: 3,707 passed, 12 skipped, 657 deselected; the sole failure remains
  `test_activation_marker_is_readable_by_non_root_api_user` (`sudo: interactive authentication
  is required`). No suppression or test skip was added. The final eval-only repeat passed all
  184 tests after the schema-drift assertion was added. No production or CI verification was
  performed. The owner subsequently authorized committing, pushing and updating the PR description.

## Quota smoke correction (2026-11-16)

Review on `fb83faf7` confirmed the dedicated ProposalAI smoke expects an extra START after the
browser has already observed exhausted quota. CI attempt 2 of run 43606935725 reported nine
passes and one 240-second timeout on the disabled Generate button. The owner authorized fixing
the smoke while retaining the real backend 429 assertion and running the complete product smoke.

Implementation plan:

1. Observe zero remaining before aborting further quota reads. After New task, verify that a
   failed refresh and a filled form preserve disabled Generate, the quota notice and no extra
   START, progress or result. Preserve the runtime guard.
2. Reload the same guest with quota reads still unavailable, clearing only the component's quota
   snapshot. Submit from that unknown-quota state and assert one real backend START returning
   429 with the quota notice and no fake progress/result. Reuse the same exhausted guest instead
   of repeating ten successful runs; do not mock START or increase the test timeout.
3. Run smoke-package lint/typecheck and the canonical `proposal-ai-smoke` against dev-up's
   deterministic fake provider, then stop the stack started for this verification. This smoke
   has its own script and CI job; it is not part of frontend-check's `pnpm -r test` stages.

The Brief Decoder, Acceptance Builder and Task Finder quota smokes block quota reads before
their first navigation and therefore never observe an exhausted snapshot. No matching quota
smoke exists for Client Update Writer. No product-code change is needed for this finding.

Implementation and verification:

- The smoke waits for the observed zero balance, aborts the next quota refresh and waits for
  that request to fail. Generate and its quota notice remain consistent after New task and form
  filling. Dispatching submit directly also leaves the START count at ten, with no progress/Copy.
- Reload retains the same nonempty guest ID but clears the component's quota snapshot. With
  quota reads still unavailable, a real eleventh START returns HTTP 429; the quota notice is
  visible and progress/Copy remain absent. Neither START nor its response is substituted.
- `doctor`, smoke-package lint/typecheck and documentation validation passed. Canonical
  `python scripts/agent/runner.py proposal-ai-smoke` built the web app and passed all ten tests
  against the local API/PostgreSQL/worker with the deterministic fake provider: 1.2 minutes total,
  31.7 seconds for the quota scenario. The existing 240-second test timeout was not increased.
- Only the smoke and this execution plan changed. Backend/full frontend gates, live model calls,
  production and remote CI were not rerun for this test-only correction. The local dev stack was
  stopped after verification. The owner subsequently authorized committing, pushing and updating
  the PR description.

## Main integration: example input assertion (2026-11-16)

Frontend CI run 43821077293 tested merge `29904cdd` (feature `585d28bc` plus main `9f9d6ebc`),
not the feature checkout alone. ANY-847 added a first-run example test whose exact request
expectation omits ANY-843's required result-contract marker: 823 web tests passed and one failed.
The separate ProposalAI smoke run 43821077233 passed on the same feature head.

The owner authorized integrating main and correcting the expectation, with a complete frontend
gate on the combined code. Plan: merge main into the existing branch without committing, retain
both features, add the marker from the already-imported backend schema to the exact input
assertion, check other ProposalAI input assertions, and run frontend-check. Preserve the example
test's own-input/draft/event checks and keep the marker requirement unchanged. Record validation
before a separate commit/push request; the reopened result-before-quota review is outside this fix.

Implementation and verification:

- Merged current main `9f9d6ebc` into `feature/ANY-843` without conflicts, retaining ANY-847's
  examples and ANY-843's contract. The verified merge and assertion correction were committed
  locally as `32679418` before the subsequent push request.
- Added `result_contract: proposalInputSchema.properties.result_contract.const` to the example
  test's exact input expectation. Other ProposalAI request assertions were checked; no additional
  mismatch was found. User input, draft/event and sample-text exclusion assertions remain intact.
- All 115 ProposalAI tests passed first. Complete canonical frontend-check then passed with serial
  workspace execution: lint, typecheck, 824 web tests, 336 CE-kit tests, 55 shared-ui tests,
  349 Chromium tests, generated API-contract drift check and all builds. Doctor, documentation
  validation and staged/unstaged whitespace checks passed.
- Backend gates, dedicated product smokes, live model calls, production and remote CI were not
  repeated for this integration. The owner subsequently authorized committing, pushing and
  updating the PR description; the separately reopened delayed-quota finding remains outside
  this verification.

## Shared quota admission lifecycle (2026-11-16)

The owner authorized fixing the repeated result-before-quota finding across the shared runtime.
A terminal result currently reopens submission before its quota read settles, and mode remounts
discard even known exhausted product quota. Seven diagnostic cases reproduced these gaps.

Implementation plan:

1. Separate new-run admission (unknown/checking/available/exhausted) from execution/result phase.
   Own quota state above keyed mode forms, scoped by client, guest, product, policy and dimension.
2. Invalidate old permission after acceptance and terminal outcomes; guard both button and submit.
   Preserve input/result/Copy and same-key or accepted-session recovery. Bounded failed reads remain
   advisory but never erase known exhaustion. Unmetered products do not wait for quota.
3. Add delayed-response regressions for rejected fields, regeneration, New task, terminal failure,
   invalid result, mode remount, stale responses and identity/scope isolation; preserve retry controls.
4. Keep the smoke's real backend 429 after reload with unavailable quota, add a delayed final-quota
   case, run frontend-check and proposal-ai-smoke, and document results. No billing/DSL changes.

Doctor passed with the repository-managed Python 3.12 interpreter. System Python 3.14 lacks the
required modules and is not used for validation.

Implementation:

- Added a page-owned quota store and scoped admission state. ProductPageShell owns it on real
  routes; standalone multi-mode products retain it above their keyed forms. Terminal reads survive
  mode remounts and older boot/reservation answers cannot replace them.
- The submit button and handler use the same admission decision. A prepared key after a definite
  capacity rejection still needs admission because it can create its first execution. Only an
  uncertain send or an already accepted session bypasses the gate for recovery; reserved capacity
  remains distinct from exhausted quota. Guest self-heal selects a new quota scope.
- Results and field hints render immediately; fields remain editable while quota is checked.
  Added the checking status in all seven host locales. Unmetered Client Update Writer requests no
  quota. A request-in-flight guard prevents duplicate same-tick form submissions.
- Added regressions for both rejected fields, normal result/regeneration/New task, failed/expired
  sessions, missing/invalid/unavailable artifacts, positive/zero/failed/timed-out quota reads,
  request ordering, mode changes, scope isolation, guest self-heal and recovery exceptions.
- Extended browser smoke with delayed terminal quota after a real last allowed run, plus corrected
  semantic input with a delayed real quota read. Only the latter's artifact output is substituted
  at the browser boundary because the deterministic worker selects a fixed provider fixture.
  START/session/quota calls stay real. The reload case still exercises a real HTTP 429.

Final verification: canonical frontend-check passed lint, typecheck, **858 web tests** (34 new
regressions), **336 CE-kit tests**, **55 shared-ui tests**, **349 Chromium tests**, generated
API-contract drift checking and all builds. The shared-runtime suite includes 133 tests. Smoke
lint/typecheck, documentation and architecture validation also passed. Existing local-skill
references in unrelated tracked plans were observed and left outside this ticket's changes.


Dedicated ProposalAI smoke passed **11/11** against local API/PostgreSQL/worker with the
repository's deterministic fake provider (1.3 minutes; real quota scenario 37.3 seconds). It
confirmed no extra START before the delayed terminal zero, retained exhaustion after a failed
refresh, and a real HTTP 429 for the same guest after reload with quota reads unavailable.

The first complete frontend attempt reached Chromium and had one unrelated Atom Lab timing
failure: `malformed accepted response keeps the same submission available for safe replay`
asserted the second request synchronously after clicking Retry (one request observed instead of
two). The other 348 Chromium tests passed. That unchanged test then passed three isolated repeats;
no Atom Lab code/test or retry policy was modified. The subsequent complete frontend-check passed,
including that test and all 349 Chromium cases (6.4 minutes for the browser suite).

The smoke dev stack was stopped after verification. Backend full-check, live model calls,
production and remote CI were not rerun. Billing policy and the required result-contract marker
remain unchanged. The owner subsequently authorized committing, pushing and updating the PR
description with this implementation and its verification results.


## Main integration: Portal identity and paid recovery (2026-11-16)

The owner requested updating the current branch from main, now de7c1cd9 (ANY-766).
The overlapping changes are ProductRunPage's new resolved-selection wrapper, paid persistence
and recovery-only boot, plus MultiModeProduct's shared mode/session selection.

Integration plan: preserve the Portal/paid paths and identity-generation guards from main,
keep page-owned guest quota admission and normalized field rejection from ANY-843, and clear
completed paid recovery when a semantic rejection returns the form to editing. Retain the
required result marker, shared mode quota lifetime and unmetered behavior. Validate the merged
web/CE-kit suites including paid recovery and guest quota regressions, then frontend-check.
No backend billing or Portal contract redesign is part of this merge.

Conflict resolution retains the new ResolvedProductRunPage/useProductSelection path, recovery-only
boot and owner-bound paid persistence. Guest admission remains above mode remounts; paid clients
never create a guest quota scope. The common in-flight guard covers both paid and guest sends.
Semantic rejection clears only its completed paid recovery. A restored pending request binds
field hints to a saved form only if that form reproduces the frozen request input; a newer draft
keeps its values without inheriting the older request's errors.

Added four integration regressions for fresh paid submission, accepted-session recovery, pending
replay, and pending replay with a newer draft. The pending case reproduced the lost hints before
the merge correction. All four now pass, together with 410 focused paid/guest/product tests.
Final web suite: 997 tests passed. CE-kit: 408 passed; shared-ui: 55 passed; Chromium: 349
passed. All five backend/frontend renderer-pin contract tests passed, as did documentation and
architecture validation. The canonical frontend-check exposed a typed-input guard error and
then an architecture-boundary violation in its helper import; both were corrected in the existing
runtime comparison helper. After that final correction, the complete affected web suite and
web lint/typecheck passed, and generated API types were confirmed current. Previously passing
unaffected browser/package suites were not repeated. This is staged frontend verification, not
a claim that an uninterrupted final frontend-check command passed.

An unchanged ESLint harness test exceeded its five-second limit while Docker images were being
built; after the build it passed independently and in the next full CE-kit run. No timeout,
assertion, test selection or retry policy was relaxed. The existing dev PostgreSQL volume rejected
configured credentials; smoke uses a separate temporary database volume, preserving the existing
data. All workspace production builds passed. Dedicated proposal-ai-smoke passed 11/11 against
the rebuilt API/worker and isolated PostgreSQL database, including the delayed terminal-quota
read and a genuine backend 429 after reload. The test stack was stopped after verification.

This update is a local merge of de7c1cd9 into feature/ANY-843; no push or GitHub write was requested
for this step. Backend full-check, live LLM calls, an actual peer Portal deployment and remote CI
were not rerun. Existing billing policy and the required input marker remain unchanged.
