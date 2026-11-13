# Execution Plan: ProposalAI input sufficiency (ANY-843)

## Status

- State: active
- Owner: agent
- Linear: ANY-843
- Created: 2026-11-13
- Last updated: 2026-11-13
- Review date: 2026-11-20
- Next action: owner review of the verified round 2 normalized-value comparison fix.
- Blocker: local full-check cannot pass the unchanged activation-marker test without passwordless sudo.

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
