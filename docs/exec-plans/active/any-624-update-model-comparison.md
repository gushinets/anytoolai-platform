# ANY-624 — Update web-form model comparison

## Status

- State: active
- Owner: human
- Created: 2026-11-03
- Last updated: 2026-11-04
- Review date: 2026-11-04
- Next action: human screening confirmation and finalist selection; no automatic rollout
- Blocker: formal semantic verdicts and finalists await human confirmation

## Goal and scope

Compare Update on luna, GPT-6.1 terra and GPT-6.1 sol at medium/high reasoning,
using real web-form submissions with full output, browser traces and provider ledger.
Preserve product prompts, default model and runtime contracts. No GitHub or Linear writes.

## Implementation steps

1. Prepare local live runtime and Python 3.12 managed environment; run doctor.
2. Freeze twelve U01/U03/U04/U05 RU/EN/ES inputs, criteria, prompt hashes and six configurations.
3. Reuse existing browser selectors and evidence utilities; test missing evidence and failed UI handling.
4. Collect 360 screening attempts (five per input/configuration), retaining failures.
5. Present semantic review and measurements before choosing up to two finalists.
6. After confirmed selection, collect fifteen additional attempts per main input and five per six new variants per finalist.

## Acceptance

Screening: at least 4/5 usable per case/language/configuration, no critical errors,
median submit-to-visible-result at most 60 seconds. Finalists: 19/20 main, 5/5 variants.
Missing evidence or human semantic confirmation stays PENDING. UI failures stay failures
when the backend succeeds later. Unknown provider cost is never zero.

## Relevant docs

- `docs/architecture/llm-runtime.md`
- `docs/agent/worktree-runtime.md`
- `docs/agent/coding-conventions.md`

## Validation

Targeted adapter tests, quick-check, configuration/architecture and documentation checks.
Real-provider evidence is separate from deterministic tests.

## Decision log

- 2026-11-03: User authorized execution after scope/threshold clarification and confirmed the key is current.
- 2026-11-03: Start with screening; confirmed human verdicts are required before finalist selection.

## Progress log

- Initial doctor used system Python 3.14 and reported missing pytest/pydantic. Managed quick-check uses Python 3.12.13.
- Sandbox PyPI DNS blocked initial setup; retry requested with network access. No provider calls yet.

- Managed doctor passed on Python 3.12.13. Isolated live stack started and deployment profile verified in API and worker; web form served locally.
- Implemented browser collection, worker-only router override/readback/restore, frozen twelve-input screening suite, and hash-bound human review report. Product source/prompt/default model unchanged.
- First collector run exposed a mistaken UUID assumption; the platform session uses a prefixed identifier. Corrected the collector, retained the original browser trace/ledger and resumed without replacing the attempt.
- Preliminary semantic finding on luna/medium: all five English U04 outputs omit the internal completion note and its contradiction with acceptance. They preserve the separate release-request/rule conflict. Human verdicts remain pending; no finalist has been selected.
- Baseline validation is limited by this environment: sandbox deployment-lock tests reject the root directory permissions; outside sandbox an existing runner test fails because sudo cannot switch to nobody without authentication. No unrelated runtime/test fixes made. Sanitized context collected.


## Screening outcome

- Completed 360 planned web-form attempts across six configurations, twelve inputs and five repeats; one additional diagnostic repeat is retained separately.
- Reconciled all 363 physical provider calls with stored attempts and costs. Two extra calls were provider retries; every provider call succeeded, which does not establish semantic quality.
- Two external SIGTERM interruptions lost proof of UI delivery. Both original attempts remain FAIL, with backend output and costs retained. One accidental repeat during the first recovery is diagnostic only. Added submission journaling, orphan-evidence refusal, SIGTERM unwinding and small checkpoint batches; no interrupted attempt was silently replaced.
- The first collector's UUID parsing failure did not cause a repeat: its complete output, displayed innerText and latency were recovered from its original Playwright trace. The reconstructed latency source is explicitly recorded.
- Agent reading found the mandatory internal-note/acceptance contradiction absent in all 30 English U04 messages, five per configuration. These are agent observations with full quotes and input/output/criterion hashes; human decisions remain empty. No semantic PASS is asserted and no finalists are suggested. The additional 420 finalist/variant attempts were not run.
- Median UI seconds: luna medium 6.48, luna high 12.28, terra medium 6.21, terra high 6.29, sol medium 6.19, sol high 12.27. Two interrupted attempts have unknown UI latency and remain explicit in the data.
- Total ledger estimated cost: 0.76932436, including diagnostic/retry calls. No independent pre-run tariff snapshot or cache breakdown was frozen, so these are not reconciled invoice costs and do not support a billing recommendation.
- Original worker router restored and read back; all six manifests share one prompt hash and one suite hash. Runtime image IDs, complete outputs, traces, screenshots, journals, provider ledger and reconciliation audit retained locally. Product prompts/default model unchanged; no GitHub/Linear writes.
- Validation: 85 targeted tests passed; new Python/browser-driver lint, config and architecture checks passed. Broad quick-check did not finish green: known existing runner failures include sandbox lock ownership and sudo-to-nobody restrictions; the stalled broad run was stopped. Other broad failures were not fully triaged. Full-check was not run.
- Repo-wide scanning also found pre-existing local slash-command references in unrelated execution plans; those plans were left untouched.

## Review boundary

The live screening is complete. Formal semantic acceptance remains PENDING pending human decisions.
Observed mandatory AC failures are sufficient to withhold any model rollout recommendation.
Further prompt changes, production rollout or another full series require separate scope; this
iteration is not expanded into ongoing prompt tuning.


## U04 remediation and repeat acceptance — 2026-11-04

User explicitly authorized fixing the U04 omission and repeating acceptance.
Root contract issue: the broad internal-detail nondisclosure override suppresses project status
claims, including the very claim whose contradiction must be explained. Distinguish private
business information from operational status evidence, preserve each independent contradiction,
and attribute disputed source claims without endorsing them. Explicit author nondisclosure and
private-cost protection remain in force. Searched all four products and Update's sibling modes;
this broad override occurs only in the Update prompt.

Implementation plan:
1. Replace the broad privacy boundary in the Update prompt; preserve author-direction and identity rules.
2. Add a small prompt-contract regression and RU/EN/ES live controls for mixed private/status notes,
   multiple contradictions and explicit status nondisclosure. Existing fake fixtures are not semantic proof.
3. Load the new live profile and read back the worker prompt hash before any new paid call.
4. Freeze a fresh screening suite with unchanged case inputs, prioritize U04, then repeat the
   twelve-case/six-configuration matrix if the targeted check supports the fix. Never reuse old
   revision verdicts or merge old runs into the new series.
5. Review full results, reconcile ledger/traces and restore the original model configuration.
   No automatic human confirmation, rollout, GitHub or Linear writes.


### Remediation validation and external blocker

- Replaced the blanket internal-detail restriction with an operational-status/private-business
  boundary in the Update prompt. Relevant status discrepancies must retain both attributed
  claims and observations, and each independent contradiction stays separate. Explicit status
  nondisclosure and private costs/margins remain protected. Author and speaker rules unchanged.
- Added a prompt-contract regression and nine RU/EN/ES privacy/explicit-withholding live controls.
  Added an explicit suite input to the existing collector; omitted repeats now use the frozen
  suite's declared count. No new dependencies, model defaults or runtime validators.
- Activated the new local live profile and verified source/API/worker fingerprints. Worker/source
  prompt SHA-256 both equal 53c91f94fced5aac6dac1a63c2d090f724ff035ba64cb6cdedf0a61d449d8bdf.
- Started a fresh U04-first matrix with exactly the original case texts/criteria. Its first
  U04-en attempt failed before receiving model output: OpenAI returned
  `401 AuthenticationError: Your API key has been invalidated.` Both gateway ledger attempts,
  browser trace and UI error are retained. The worker uses the resolved live-file key; no
  alternative host key is present. Stopped further live calls, restored/read back the router,
  and requested an updated key through the existing local secret file.
- No semantic success is asserted. The privacy controls are prepared but not executed; old
  outputs/verdicts were not reused as acceptance of the new prompt.
- 117 targeted tests passed: 102 prompt/identity/eval/quick-check-entry tests and all 15 product
  pipeline tests. The product pipeline hung inside sandbox but passed outside it; the redundant
  stalled sandbox run was stopped. Config, architecture, docs and generated-doc drift checks pass.
- New repeat acceptance remains externally blocked on the provider credential. No GitHub/Linear
  writes or automatic human verdicts.

### Credential refresh and resumed acceptance

- User updated the local secret and explicitly requested continuation. Recreated the live stack and verified the same new prompt hash in worker; no secret printed or copied into evidence.
- Four remaining English U04 and all five Russian/Spanish U04 outputs on luna medium restore the omitted status/acceptance contradiction on full-output agent reading. The original authentication failure remains the first English attempt; no replacement or automatic human verdict.
- Privacy/explicit-withholding controls are now collecting before the remaining full matrix.

### Completed repeat acceptance

- Completed all 360 planned main attempts and 27 additional RU/EN/ES privacy controls on one
  unchanged corrected prompt. Original case texts/criteria are identical; order prioritizes U04.
  386 visible model outputs; the first authentication failure remains FAIL, never replaced.
- Full-output agent reading finds the original U04 omission corrected in all 89 outputs across
  six configurations. All 27 luna/medium privacy controls retain operational evidence, hide
  private figures and obey explicit status withholding. Controls were not run on other models.
- Both luna and terra reasoning configurations fail other mandatory screening criteria: U05
  omits the 48,000 RUB contract amount in 14/15 luna medium, 14/15 luna high, 7/15 terra medium
  and 9/15 terra high outputs. Luna medium also omits the status date in two Russian U05
  outputs; terra high omits it in one Spanish U05. Two luna high English U05 outputs are Russian.
  These are observed acceptance gaps, not a claim that the U04 fix caused them; the earlier
  revision already omitted amounts/status dates in the same case.
- Sol medium/high preserve material criteria on agent reading of all 60 outputs each. Both are
  candidates pending human confirmation, not formal PASS. Sol medium is the first candidate
  for review at 6.20s median versus 12.27s for high. No default model change. Some sol medium
  replies derive generic next steps from unfinished work; human review should check commitments.
  One luna high U04 wording echoes an author direction; recorded for human assessment.
- Median UI seconds: luna medium 6.29, luna high 8.21, terra medium 6.26, terra high 8.21,
  sol medium 6.20, sol high 12.27. Privacy-control median 4.36s. Every series is below 60s.
- Reconciled all 387 unique sessions and 388 physical provider attempts: 386 succeeded,
  two failed on the retained credential error; zero unaccounted calls. Trace, screenshot,
  journal, visible/canonical output, configured model and ledger proof verified for every result.
  Original router restored/read back; source/worker prompt hash remains the corrected revision.
- Total ledger estimate 0.780925505 including controls and failures. No unknown ledger costs;
  no independent invoice, pre-run tariff snapshot or cache reconciliation, so not a billing claim.
- Complete outputs, hash-bound human templates, 386 agent observations and reconciliation audit
  retained locally. Human decisions remain empty. Additional 420 finalist/variant attempts are
  deferred until screening confirmation and finalist selection, as agreed. No production rollout,
  GitHub/Linear writes or new source changes during collection. Earlier 117 targeted tests stand;
  full-check/broad baseline limitations remain as documented.

- Post-live verification: 102 prompt/identity/eval/entry-point tests passed again in 3.43s; documentation validation and diff whitespace checks pass. The earlier 15 product pipeline tests also passed; no source changed during live collection.
