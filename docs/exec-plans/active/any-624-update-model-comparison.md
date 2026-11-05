# ANY-624 — Update web-form model comparison

## Status

- State: active
- Owner: mixed
- Created: 2026-11-03
- Last updated: 2026-11-05
- Review date: 2026-11-05
- Next action: verify SonarCloud reanalysis after the authorized commit and push
- Blocker: remote SonarCloud reanalysis pending; local regression tests and quick-check pass

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

### Interactive human review — implementation plan

User requested the same terminal review workflow as ProposalAI, with a named reviewer.
1. Add an offline review subcommand to the existing Update collector, preserving collection CLI.
2. Read validated manifests/runs and hash-bound agent observations; show one full input/output
   and criterion at a time, with explicit yes/no/unknown, skip and quit choices.
3. Append partial human verdicts after each decision; resume matching decisions, reject stale
   suggestions, and record reviewer/time. Never automatically promote an agent suggestion.
4. Ask about critical errors explicitly, preserve the existing report contract, and test resume,
   disagreement, stale hashes, interruption and compatibility with report aggregation.
No model calls, dependency, frontend changes, automatic verdicts or external writes.

### Interactive review delivered

- Added the collector's offline `review --directory <results-directory> --series sol-medium
  --reviewer Putilin` mode. The series filter is optional. Collection CLI stays compatible.
- Displays one original input/full output, model/reasoning and current hash-bound agent
  observation, then explicit per-criterion yes/no/unknown/skip/quit. Yes records human
  confirmation; no/unknown require a reason and allow a quote. No automatic agent confirmation.
- Every completed decision appends to the existing verdict stream with reviewer/time and
  input/output/criteria hashes. Partial decisions resume; stale suggestions are withheld,
  a new reviewer never inherits another reviewer's partial answers, corrupt partial state fails
  explicitly, and changed criteria decisions invalidate the old critical-error assessment.
- Existing confirmed PASS/FAIL rows are skipped. Unknown/skipped decisions remain PENDING.
  Run one terminal review process per result directory, as with the ProposalAI workflow.
- 98 targeted eval/ProposalAI/entry-point tests pass; Ruff, documentation validation and diff
  checks pass. Tested real saved sol medium queue with quit before any decision: no human
  verdict created and no provider inference. Full-check was not rerun. No commit or external write.

### User-confirmed batch acceptance and technical retest

User explicitly confirmed viewing all responses and requested marking the rest passed,
with failed testing repeated. Record existing visible responses as Putilin's explicit chat
acceptance, retaining earlier agent findings and all verdict history. Do not turn the
credential failure into an answer. Freeze a separate one-case repeat of its exact input,
model/reasoning and corrected prompt; collect new UI/ledger proof and restore the router.
The new unseen response is not covered by the user's approval of existing responses.
Refresh reports and reconcile additional calls; preserve original failure and earlier audit.

### Batch acceptance and technical retest outcome

- Recorded Putilin's explicit chat confirmation: 292 additional screening verdicts and 27
  controls, preserving 67 already-confirmed screening verdicts. All 359 existing screening
  outputs and 27 controls are human-accepted. Reports regenerated as PASS under that confirmation;
  earlier agent deviations remain unchanged. This is acceptance, not proof those omissions vanished.
- Backed up verdicts and retained exact confirmation messages, scope, timestamp and provenance.
  The original missing-output authentication attempt was not marked accepted.
- Repeated its exact U04-en input once, separately, on luna/medium and the same prompt. Result
  delivered in 12.36s; one provider call succeeded. Agent reading retains both contradictions,
  3/8 Safari failures, sandbox-only payment capture, investigation/no ETA and hold confirmation.
  This new unseen result remains PENDING human review, not a fabricated Putilin decision.
- Original FAIL and its two failed gateway rows retained. New UI evidence/model/ledger checked;
  router restored/read back. All 389 physical attempts accounted for: 387 succeeded, two failed
  on the historical key error. Incremental ledger estimate 0.0004283, not an invoice claim.
- Doctor, documentation and diff checks pass; no source changes during this operation.
  Interactive-review changes remain uncommitted. No finalist series, full-check, production
  rollout, GitHub/Linear writes or default-model change.

### Technical retest human confirmation

Putilin explicitly confirmed the new retest response in chat with no errors observed.
Recorded a hash-bound human PASS, regenerated the separate report and updated acceptance audits.
Original screening, privacy controls and technical retest are now user-accepted. The original
key failure remains historical evidence, not silently replaced. No new provider calls, source
fixes, finalist series, model default change, full-check or external write.

### Finalist phase — sol medium selected by user

User selected sol/medium as the only finalist and authorized continuation. Freeze one corrected
prompt revision, copy the same-model/same-input accepted five attempts into the twenty-attempt
main groups with original hashes/evidence/human verdicts, and collect exactly 180 new main
attempts plus 30 variant attempts. No old-prompt or other-model data is reused.

Implementation plan:
1. Freeze six new inputs before calls: two RU (email desktop/tablet dependency; 9 videos ×18 min,
   4/3/2, Riga deadline, contract/exclusion), two EN (unknown inventory/barcodes/current source;
   explicit status withholding with public failures/private costs), two ES (internal readiness
   versus Firefox acceptance plus publication rule/private costs; 10 audios ×15 min, 6/2/2,
   Bogota deadline, 950 USD and French exclusion). Preserve original main inputs verbatim.
2. Check doctor, worker prompt/router and runtime; freeze pre-run ledger and SDK pricing metadata.
3. Collect variants first, then main attempts 6–20 in checkpoint batches with full web/ledger proof.
   No prompt tuning mid-series or silent retries. Main threshold 19/20, variants 5/5, zero critical
   errors and median UI <=60s. New outputs are not covered by prior human acceptance.
4. Read full outputs, reconcile old seeds/new calls/costs/evidence and restore the router.
5. Generate both reports and present new outputs for human review. Attempt full-check separately;
   no production rollout/default model change, extra model comparison or external publication.

### Final variant gate outcome

- Completed all 30 new variant attempts on sol/medium; no transport/UI failures. Full-output
  agent reading finds 950 USD contract amount absent in V06 Spanish attempts 1, 2 and 3,
  though the input explicitly provides the amount as contract context, not a payment request.
  Attempts 4 and 5 preserve it. This violates the agreed 5/5 variant criterion; new human
  verdicts remain PENDING and were not inferred from prior approval of different outputs.
- No critical problem observed in the other 25 new outputs, including contradictory status
  alongside private costs and explicit status withholding. Derived generic next steps remain
  a human-review caveat. Original prompt/default model unchanged; no tuning during the series.
- Stopped before the 180 additional main attempts and asked the user whether to fix this
  omission or explicitly continue the unchanged series despite the variant gate failure.
  Sixty accepted seed outputs remain separate, hash-matched and linked to original evidence.
- All 30 new physical calls reconcile with new sessions and UI evidence; zero unaccounted calls,
  no unknown ledger cost. Router restored/read back. Median variant UI 5.28s; incremental
  ledger estimate 0.0759181. Pre-run installed SDK pricing metadata frozen; invoice/cache
  charges are not independently reconciled. No new provider calls after the observed failure.
- Full reports, immutable inputs/criteria and agent observations retained for user assessment.
  Doctor/config/docs/diff checks pass; full-check not run. No new source behavior changes,
  external writes, commits or rollout. New variant fixture and previous review-tool changes
  remain uncommitted. A future prompt change cannot reuse these seeds as proof of its behavior.

### V06-es amount omission — analysis and proposed implementation plan (2026-11-05)

User requested investigation and a proposed correction, not implementation or new paid evals.
Confirmed facts: the browser trace submits the complete 950 USD sentence to the start endpoint;
there is no max_length constraint in that request. UI text matches canonical output. The five
outputs are complete (619–689 main-text characters, 204–219 output tokens), all calls succeeded
with the same 2,031 input-token count/model/reasoning/prompt. Amount absent in attempts 1–3,
present in 4–5. Thus transport/input loss or renderer truncation does not explain the omission.

Contract gap: the Update prompt separates fidelity of INCLUDED facts from completeness, but
completeness enumerates results, blockers, requests and next steps without explicitly requiring
client-facing commercial terms. The workflow intent likewise emphasizes progress/next steps.
The privacy rule protects own costs/margins/private figures but does not positively distinguish
client contract terms. A no-payment-request statement means no demand to pay, not suppressing
the stated contract amount. These are observable ambiguities; the model's exact latent reason
cannot be established from these five outputs without a controlled revised-prompt comparison.
The generic compose-reply validator checks length/format/placeholders, not semantic fact coverage.

Scope checked: all four products and Update's sibling modes. This exact prompt/completeness
boundary is used only by Update; ProposalAI has explicit Terms rules and Reply Draft explicitly
preserves client-facing intent facts. No confirmed matching defect in other products; their
behavior was not live-tested in this investigation. No shared platform/schema/DSL change proposed.

Proposed plan, pending user's implementation instruction:
1. Amend Update's completeness rule to cover supplied client-facing commercial terms: contract
   or quoted amount/currency, with the input's actual agreement/payment status and conditions.
2. Clarify that no-payment-request text does not suppress the amount; preserve contract context
   without inventing an invoice, debt, due date or payment request. Distinguish these terms from
   the freelancer's own private costs/margins, retaining explicit author nondisclosure priority.
   No literal 950/USD/Spanish-specific branch or numeric-extraction runtime validator.
3. Add a small prompt-contract test, then freeze live RU/EN/ES regressions: exact V06 and its
   translations, contract plus private costs/margins, explicit amount withholding, and quoted
   versus agreed/paid status. Existing U04/unknowns and non-payment intent must remain intact.
4. Compare unchanged baseline and new prompt on sol medium before a full restart; no accepted
   old-prompt seeds or verdicts can establish acceptance of a new prompt. Preserve old evidence.
   If the clarification does not reliably pass, stop prompt looping and reassess model/contract.

No source/config/test behavior changed. No new provider calls or full-check in this analysis.

### V06 correction implementation — 2026-11-05

User explicitly authorized the proposed Update prompt rule and V06 checks.
1. Add client-facing commercial terms to the completeness contract, preserving stated status,
   non-payment intent, private business protection and explicit author withholding priority.
2. Add a prompt-contract regression and frozen V06 RU/EN/ES cases, mixed contract/private-cost
   controls and explicit amount-withholding controls; preserve original failed Spanish input.
3. Run focused Python tests and config/docs checks. Verify prompt effects on sol/medium using
   a fresh 45-attempt targeted live suite (nine inputs, five repeats) if runtime/key available.
   No old human verdicts or old-prompt seeds are reused; no full finalist restart in this step.
4. Reconcile new UI/ledger evidence and restore router. Report semantic observations separately
   from human approval. No default model change, new dependencies or platform validators.

### V06 correction verification outcome

- Added one general completeness rule to Update: supplied client-facing contract/quoted amounts,
  currencies and stated status/conditions remain context even without a payment request. No
  invented invoice/debt/due date/payment demand; private own costs/margins and explicit author
  withholding retain precedence. No case-specific USD/950/language branch or platform validator.
- Added two prompt-contract checks, an immutable original-V06 fixture check and nine input-schema
  checks. The live suite contains base V06, mixed client/private figures and explicit amount
  withholding in RU/EN/ES, five repeats each. Original Spanish input and criteria remain exact.
- 126 focused Python tests passed; new-file Ruff, doctor, configuration, architecture, docs and
  diff checks pass. Fake/output-schema tests are not claimed as model semantic proof.
- Fresh sol/medium live validation completed all 45 attempts on prompt SHA-256
  ddda3dcaa9c00993b5ac914cb5721e2275bb6cd464c3bccdb2a3e743810424c1.
  On full-output agent reading, original V06 Spanish preserves 950 USD in 5/5 versus 2/5 on the
  previous prompt. All 30 base/mixed outputs retain it without payment demands; all 15 explicit
  withholding outputs omit it, and own supplier costs/margins remain undisclosed. V06 quantities,
  dates, transcript request and French exclusion remain. Derived generic next steps and one
  awkward English cutoff phrasing are retained as human-review caveats, not polished indefinitely.
- All 45 physical calls and unique UI sessions reconcile; traces/screenshots/journals and visible
  versus canonical text/model checked. Router restored/read back. Median UI 6.26s; ledger estimate
  0.1487641. Pre-run SDK cost metadata captured; no invoice/cache billing reconciliation claimed.
- New outputs remain PENDING human confirmation. Old accepted verdicts/seeds were not copied
  into the new revision. Full final series/full-check/rollout not performed. No default model
  change, dependency additions, commits or external writes. Prior uncommitted changes retained.

### V06 targeted human acceptance

Putilin explicitly confirmed viewing all 45 fresh targeted outputs with no errors and asked
to mark them passed. Recorded hash-bound human PASS decisions with reviewer/time and exact chat
provenance; regenerated the targeted report as PASS (45/45, zero critical errors). Prior history
and old-prompt evidence remain unchanged. No provider calls. Complete final acceptance of the
new prompt, full-check and committing the pending changes remain outside this confirmation.

### Corrected-prompt full final acceptance — user authorized start

User authorized the remaining work: 240 new main attempts (12 inputs ×20) and 25 new variant
attempts. Five already human-accepted V06 Spanish outputs on the identical corrected prompt,
input and criteria are imported with original evidence/verdicts; no old-prompt seed is used.

Implementation plan:
1. Freeze the original main inputs and six variant inputs, thresholds and corrected prompt hash.
2. Run full-check before the web server to avoid frontend build/dev artifact collisions; fix
   task-owned failures without weakening architecture checks. Preflight ledger/runtime/pricing.
3. Collect remaining variants first, then the 240 main attempts in checkpoint batches. Preserve
   failures, outputs, journals/traces and ledger; no silent retries or prompt tuning mid-series.
4. Read full outputs, reconcile new calls and imported seeds, restore router and generate reports.
   New human verdicts remain empty. Present findings and record any acceptance limitation.
5. Commit the authorized source/test/tool changes locally with the ANY-624 title convention;
   no GitHub writes or production/default-model change.

Initial full-check passed config/architecture-script/docs/generated-doc checks but its architecture
pytest found a literal provider/model example in the collector docstring. Replaced that example
with a generic placeholder; no allowlist exemption or runtime behavior change. Dedicated guard
rerun and the full check will verify the correction. This also removes a local ignored evidence
path from that touched example. No unrelated reference cleanup.

### Final-phase verification and runtime checkpoint

- Full-check reached backend pytest with 3040 passed, 12 skipped and 486 deselected; its sole
  remaining failure is the host sudo-to-nobody activation-marker test requiring interactive
  authentication. No skip/allowlist was introduced. Sanitized failure context collected.
- Separate full product suite exposed stale literal expectations for the pre-U04 blanket privacy
  rule. Updated the affected assertions to retain private-business protection and explicit
  withholding while permitting operational status evidence; all 240 product tests now pass.
  Prompt bytes unchanged. Separate frontend lint/types/tests/API-drift passed; first production
  build failed /404 prerender, clean generated-output rebuild passed. Next's auto-added Node
  type dependency/package-lock changes were captured and reverted; no frontend source/dependency
  change remains in the patch.
- Collected all 25 new variants alongside five same-prompt accepted V06 seeds. Agent reading flags
  V02 English attempt 3: stock quantities staying unchanged until the client's answer is not
  explicit. Other new variants preserve material criteria. No human rating was fabricated.
- Main collection started. U04 English attempts 1–3 delivered results retaining both contradictions;
  attempt 4 failed technically with provider 401 invalidated key. Both gateway failures and UI
  evidence retained; router restored. Environment already contains a different configured key,
  so canonical live refresh is underway before resuming the remaining 236 planned attempts.
  No output/attempt replacement, prompt tuning or automatic UI retry.

### Final-phase credential blocker and reconciled checkpoint

- Canonical live refresh was attempted twice, including activation and collection inside one
  execution context. Worker credential equality with the resolved configured environment and
  unchanged prompt were verified without recording secret values. The provider still rejected
  the credential: earlier logs reported invalidation; the latest reports 401 AuthenticationError,
  incorrect API key. Collection stopped; a working credential is required to continue.
- All 25 new variants completed; five accepted same-prompt V06 seeds remain accepted. Main has
  six original attempts: three delivered U04 English answers and three retained technical failures
  (attempts 4–6). There are 234 unattempted main slots. No failed attempt was replaced or removed.
  With three technical failures, this original U04 English group cannot reach 19/20; any recovery
  series must remain separate and its acceptance treatment explicit.
- Reconciled all 31 new sessions with 34 physical provider-call rows: 28 successful calls and
  six failed gateway calls, zero unexplained rows. Ledger estimate is 0.0693913, not invoice cost.
  All trace hashes and successful visible/canonical outputs verified; router restored/read back.
  Reports are main FAIL (technical threshold), variants PENDING. All 28 new delivered outputs
  were read by the agent but remain pending human review; no earlier human approval was reused.
- V02 English attempt 3 omits the instruction that stock quantities remain unchanged until the
  client's answer. Its full output and hash-bound agent observation are retained for review;
  it was not accepted automatically or patched during the frozen series.
- Full acceptance remains incomplete. Full-check also remains red on the host sudo-to-nobody
  requirement described above; product tests pass and frontend stages pass with the clean build
  retry. No default-model switch, production rollout, push or external write was performed.
- Final focused eval/commercial regression rerun: 44 passed. Collector/reviewer/new-test Ruff,
  documentation validation and diff whitespace checks passed. The existing product test file
  still has nine baseline long-line lint findings; verified their exact text is unchanged.

### User-authorized recovery after credential replacement

User replaced the credential and explicitly requested resubmitting all failed attempts. Refresh
the canonical live stack, verify the frozen prompt/router, and replay the three technical U04
English failures as three separate recovery attempts with exact source-input mappings. Also
repeat the flagged V02 English output once as a separate semantic diagnostic. Preserve all
original failures and human decisions; successful diagnostic generation alone does not erase
the original omission. Continue the 234 unattempted main slots without prompt changes, then
reconcile all calls/evidence and present original and recovery results separately. No new
human verdicts are implied by this instruction.

Recovery checkpoint: the updated env file was used, with no host-key override. Canonical live
activation completed; worker and adapter both received the configured key, without unresolved
env sentinel, surrounding whitespace/quotes or a custom API endpoint. The first U04 replay again
failed with provider 401 AuthenticationError / Incorrect API key. Its UI evidence and two failed
gateway calls are retained separately; the other replays and 234 main slots were not submitted.
All 32 new attempts now reconcile to 36 provider-call rows (28 succeeded, eight failed), with
unchanged 0.0693913 ledger estimate. Router restored and frozen prompt verified. Await a credential
accepted by the provider; no further retries, source changes or fabricated human verdicts.

User then explicitly requested Docker recreation. Canonical live rebuild/force-recreate completed;
API/PostgreSQL are healthy. The worker key matches the updated env-file resolution. A separate
execution context contained a different host key, so verification was explicitly anchored to
the env file without that override. After recreation all three technical U04 replays delivered
answers, and the frozen main series resumed. The semantic V02 replay also delivered an answer
but again omitted the unchanged-stock-until-client-answer condition; the finding remains open.
These outcomes establish successful authentication after recreation, not a general credential
lifetime diagnosis. Original failures remain intact, and new outputs await human review.

### Completed collection after Docker recreation

- All remaining 234 main slots completed. Together with three explicit successful U04 technical
  replays, there are 240 delivered main outputs and all 30 variants (including five previously
  human-accepted same-prompt V06 seeds). No further UI/provider failures after successful refresh.
- The full history contains 270 new physical UI attempts, 266 delivered outputs and four retained
  technical failures. All 276 provider-call rows reconcile: 268 succeeded and eight failed. Two
  successful U04 Spanish sessions used semantic attempts 1 and 2 through the existing PydanticAI
  validation retry path. No automatic UI retry or omitted call. Ledger estimate 0.5231401;
  no invoice/billing reconciliation claimed. Router restored and prompt SHA unchanged.
- Created a separate current-main review view with 240 original planned slots, mapping successful
  replays into the three failed slots and retaining source/session provenance. Raw main and earlier
  recovery reports still retain their technical FAIL history; no originals or verdicts were edited.
  Current-main is PENDING, median UI 6.18 seconds. All 266 new unique outputs await human review.
- Agent reading covered every delivered output, using full initial texts and lossless comparisons
  of subsequent texts with source/criteria. Main quantities, contract amounts/currencies, dates,
  exclusions and operational contradictions are preserved. V02 English's unchanged-stock-until-
  client-answer condition remains omitted in the original flagged output and semantic replay.
- Fifteen U05 Spanish outputs refer to late transcripts as arriving after the indicated deadline,
  with October 9 delivery in the main paragraph and October 5 transcript submission in the CTA.
  Both dates remain present; this referent ambiguity is a human-review caveat, not an established
  critical failure. Some inferred generic next steps and minor repeated wording are also deferred
  review caveats, consistent with the iterative product-validation scope.
- Full-check was not repeated after this environment-only recreation: its recorded host sudo
  failure remains open; focused/product/frontend results stand as recorded. Documentation and
  whitespace checks pass. No source/prompt/model-default change, push or external write.

### V02 operational restriction versus editorial instruction — brainstorming and plan

User explicitly requested fixing V02 and using brainstorming to find and address the cause.
The unchanged V02 input says, "Do not change stock quantities until the client answers."
Two of six delivered outputs omitted this condition. The neighbouring U03 expresses its hold
declaratively, and all 60 delivered main outputs preserve it. The shared author-directions rule
forbids reporting directions even as the freelancer's own plan. This supports an instruction-role
classification conflict, not a ledger/UI defect; model internal reasoning is not observable.

Selected small change: clarify that non-reporting applies only to editorial instructions about
the message. Restrictions on doing the actual work remain client-relevant content, including
imperative wording; preserve both the restricted action/status and its release condition.
Explicit nondisclosure and business privacy still win. Do not infer a project commitment from
a direction about wording/calculations. Avoid a stock-specific exception, a second extraction
stage, schema/DSL changes or another model search; sol/medium remains the chosen configuration.

Implementation plan:
1. Clarify the identical author-directions block in Update, Reply Draft, Prepaid Request and
   Proposal; all four have reachable configured workflows. Extend their shared contract test.
2. Preserve exact original V02 and add RU/EN/ES imperative/declarative pairs, message-only
   counterexamples, explicit-withholding and mixed-private-information controls. Freeze cases
   before live calls. No change to the original acceptance criteria or historical verdicts.
3. Run focused and full product tests plus config/docs checks. Evaluate the new Update revision
   on the focused matrix in all three languages, five repeats, through the existing web collector.
   Exercise affected sibling modes with live smoke cases where the existing stack supports them;
   report source-derived risks separately if behavior is not live-verified. Check earlier privacy,
   operational-contradiction and commercial-amount protections in the regression scope.
4. Read outputs and reconcile calls/traces; restore router and record findings. New human review
   stays pending. A focused success does not retroactively accept the new prompt under the old
   full final series; decide the next acceptance scope from its evidence before another full run.

Brief Decoder and Acceptance Builder were inspected: their analysis rule already distinguishes
instructions addressed to the analysis from requirements on actual work, so the same blanket
generation rule is absent. No defect is asserted for those products and no speculative edit.

### V02 implementation and focused live evidence

- Added the same seven-line boundary clarification to the four reachable generation prompts;
  no stock-specific branch, extraction stage, schema/DSL, provider, default-model or frontend change.
  Extended the existing shared author-directions test. Added a frozen 15-case RU/EN/ES matrix
  and schema/original-input tests; the exact failing V02 English input and criteria are unchanged.
- Doctor, config/architecture/docs validation and whitespace checks passed. Full product/eval
  rerun passed 288 tests, including packaging with normal cache access after its sandbox failure.
  The final shared-rule/fixture rerun passed 28 tests after formatting the same string constant.
  New lines pass Ruff; three unchanged long-line warnings remain in the existing shared test.
- New Update prompt SHA-256 is
  fcd8e22d2d18fa13ce3d7c2543d83590f40ea9d86e1457984ee28fe964cdf14f.
  All 75 targeted web outputs were collected and read on sol/medium: imperative/declarative
  pairs retain the hold; message-only instructions do not invent one; explicit withholding
  hides it; publication guards remain present without exposing private supplier costs/margins.
  Exact original English V02 retains its condition in 5/5, versus omission in 2/6 delivered
  English outputs on the prior revision. Its three-language counterparts retain it in 15/15.
  These observations support the instruction-role hypothesis; model internal reasoning is unknown.
- Ran 30 original U04/V06 web regressions across RU/EN/ES. Both U04 contradictions remain in
  all 15; V06's 950 USD remains in all 15 without a payment demand. Source quantities, dates,
  required transcripts and the French exclusion remain. This is agent evidence, not human PASS.
- All affected sibling modes were live-exercised through the existing API/Gateway: 15 Reply Draft,
  15 Prepaid Request and 15 Proposal outputs across RU/EN/ES. Work guards remain, VAT/editorial
  instructions are not disclosed, the 500 USD deposit and agreed 800 USD price remain. API evidence
  does not claim browser proof. Proposal's local profile was activated then Client Update Writer
  restored and verified; every temporary router override was restored.
- All 150 fresh sessions and 165 successful provider calls reconcile; the extra 15 calls are
  Proposal's detect_gaps step, not retries. No failed physical calls or second semantic attempts.
  Browser traces/visible versus canonical outputs and frozen suites/prompts verified for web runs.
  Ledger estimate 0.4065981, without invoice/billing reconciliation. No accepted seed/verdict reuse.
- All new human decisions remain empty. Keep review caveats explicit: U04 English attempt 4's
  qualified "release remains on hold" may sound like an enacted decision despite its subsequent
  confirmation question; V06 Russian attempt 4 has awkward "after the cutoff — before July 7"
  wording. Other relative cutoff references, inferred generic next steps and repetitions are
  retained for review. These are not automatically classified as critical FAIL or human PASS.
- For this product iteration, the targeted V02 boundary change is ready for review; broader
  polishing is deferred. The full final matrix on this revision was not repeated and the prior
  host-sudo full-check failure remains open. No source commit, production change or external write.

### V02 targeted human acceptance

Putilin explicitly confirmed reviewing all current 150 outputs without errors and requested
recording acceptance on their behalf: "все проверил, ошибок не вижу, пометь автоматически от моего
имени". Recorded hash-bound human PASS for every criterion and critical_error=false, with reviewer,
UTC timestamp, exact chat provenance and assistant-as-recorder attribution. Backed up mutable
reports/status first; raw runs, manifests, frozen inputs and original agent observations remain
byte-identical. Prior caveats are preserved as agent history and accepted by the reviewer, not
deleted or retroactively presented as absent.

All four scoped reports now PASS: 75 Update boundary outputs, 30 U04/V06 regressions, 30 Reply
Draft/Prepaid API outputs and 15 Proposal API outputs; 150/150 human PASS, zero pending and zero
critical errors within this scope. No provider calls or source/config/test changes for this
recording step. This does not accept older different-prompt runs or the uncollected full final
matrix. Fifteen compatible U04 main seeds and ten V02/V06 variant seeds on this revision are now
human accepted; absent further prompt changes, 225 main and 20 variant attempts remain. The prior
full-check host-sudo blocker, source commit and full final acceptance remain outstanding.

### User-authorized completion of final acceptance, full-check and local commit

User explicitly requested completing the final acceptance, full-check and commit. Keep the
accepted fcd8e22d prompt revision fixed: import 15 accepted U04 main seeds and ten accepted
V02/V06 variant seeds with exact inputs/criteria, hashes, evidence and human verdicts. Collect
225 remaining main slots and 20 variants on sol/medium, preserving all attempts and failures.
New outputs are not covered by the earlier human confirmation and remain pending human review.

Implementation plan:
1. Freeze a new final directory and copy accepted compatible seeds without altering their sources.
2. Complete canonical full-check before starting the browser collection, avoiding frontend
   build/dev artifact collisions. Host sudo-to-nobody is unavailable even outside the sandbox;
   use an isolated validation container with real sudo, a real nobody identity, Python 3.12,
   Node 24 and pinned pnpm. Do not modify host sudo policy, mock user switching or skip the test.
3. Collect variants then main in checkpoint batches; read outputs and reconcile physical calls,
   prompt/configuration hashes and browser evidence. Restore the original worker router.
4. Generate current reports, recording new human review separately from agent observations and
   accepted seeds. Commit the complete task patch locally with the ANY-624 title convention;
   no push, GitHub writes, production rollout or default-model change.

### Canonical full-check completed

Canonical full-check exited zero in the isolated validation environment: 3,041 backend tests
passed (12 standard skips, 486 deselected), frontend unit suites passed 323 + 52 + 424 tests,
all 88 Atom Lab browser tests passed, production builds and generated-contract checks passed,
and all 256 product tests passed. Real sudo switched to uid 65534; no mocked identity, skipped
permission test, increased timeout or host sudo-policy change. Python 3.12, Node 24 and pinned
pnpm were used. Four CPUs and workspace concurrency=1 avoided frontend resource contention.

Earlier environment failures remain recorded: missing Docker CLI, missing Chromium, then one
5-second ESLint startup timeout under parallel load. Those were resolved by providing the
actual prerequisites and limiting concurrency; the final complete run passed unchanged checks.
The subsequent Next dev bootstrap initially could not resolve an already installed transitive
Node type package. A local node_modules link to its locked installation restored resolution;
no tracked dependency file changed and no model request had started during that failure.

### Final collection and evidence audit on fcd8e22d

Completed the frozen sol/medium matrix: 240 main slots (12 inputs × 20) and 30 variants
(six inputs × five), including 25 exact-input, exact-criteria, same-prompt human-accepted seeds.
All 245 new web attempts delivered results. Their 245 successful physical provider calls reconcile
with the ledger and unique sessions; no failed calls or second semantic attempts. Browser evidence,
trace hashes, frozen suites and prompt verified; original router restored. UI median is 4.317 s
for main and 4.300 s for variants, below the 60 s threshold. New-call ledger estimate is
0.4852774, without provider-invoice reconciliation. Historical failed runs remain untouched.

Agent read all 270 full outputs against the frozen criteria, using complete first outputs and
lossless comparisons for repetitions. No recurrence of the original U04 contradiction omission,
V02 guard omission or commercial-amount omission was found. Agent observations include quotations
and per-criterion yes/unknown suggestions; they are not human verdicts. Sixty-one new outputs have
review caveats: stronger wording of an operational hold, inferred generic next steps, explicit
not-a-payment-request explanations, repeated source-file requests or relative transcript cutoffs.
Their potentially affected criteria remain unknown rather than silently PASS. These caveats are
not automatically classified as critical defects; non-critical polish is deferred in line with
the agreed iterative product-testing approach. No prompt tuning during the final series.

At completion of collection, formal reports were PENDING: 25 imported human PASS and 245 new
outputs needing confirmation.
A complete reviewable report with all inputs/outputs/criteria, separate caveats, audit and successful
full-check evidence is prepared. The earlier confirmation of 150 targeted outputs does not accept
these new outputs. Requested a new human decision while proceeding with the authorized local
commit. No production/default-model change, push, GitHub or Linear write.

### Final human acceptance recorded

Putilin explicitly instructed: "245 - пометь как все хорошо, ошибок нету, а вот 61 расскажи
детальней". Recorded hash-bound PASS for all 245 new outputs, with named reviewer, UTC timestamp,
full quotations, exact chat provenance and assistant-as-recorder attribution. The 61 outputs with
agent caveats are a subset of these 245, not an additional queue. Earlier 25 accepted seed verdicts
are unchanged. Reports now PASS: 240/240 main, 30/30 variants, no pending decisions or critical
errors in the confirmed verdicts. Raw runs, manifests, frozen inputs and original agent observations
remain byte-identical; mutable reports were backed up before acceptance. No additional provider
calls or source/config/test edits for recording acceptance.

The preserved 61 caveat rows cover overlapping themes: inferred next actions (49), explicit
not-a-payment-request explanations (21), relative transcript-cutoff references (11), stronger
operational-hold wording (2), and repeated price-source requests (2). These are historical agent
observations, not 61 confirmed failures. Full outputs remain available with the accepted verdicts.

Source commit c243cbe3 contains the verified implementation. Full-check passed before that commit;
this follow-up changes only the acceptance record. No production/default-model change, push,
GitHub or Linear write. Implementation and agreed final acceptance are complete for this iteration.

### SonarCloud Docker argument validation — approved follow-up

User explicitly authorized fixing both S8705 findings, the shared helper and adding tests.
The two findings cover write_router's docker exec/restart calls, which accept an unchecked
CLI project name. The shared Proposal _docker helper uses the same project-to-container pattern.
The reported HTTP/LLM source is not a reachable application route: this is local evaluation CLI
input, passed as an argv list without a host shell. Arbitrary command execution was not proven;
acceptance of invalid option-like/project strings was reproduced with subprocess intercepted.

Implementation plan:
1. Add one shared Compose-project-name validator using the documented ASCII lowercase/digit,
   dash and underscore contract with an initial letter/digit. Call it before any subprocess in
   write_router and _docker. Add -- before container operands in exec and restart. Keep all
   content on stdin, the fixed container Python command, timeouts and readback behavior.
2. Add security regression tests for invalid names rejected without subprocess, valid project
   names, option separators, stdin preservation and router readback errors. Existing collector
   restoration and offline-review tests must continue passing. No new dependencies or abstractions.
3. Run doctor, focused Proposal/Update eval tests, quick-check and documentation/diff checks.
   Record Sonar reanalysis as pending until the changed revision is analyzed remotely. Do not
   repeat paid live collection: prompts and the accepted final outputs remain byte-identical.

The source changes remain on the checked-out feature/ANY-624 branch. No Sonar suppression,
GitHub comment/review/thread resolution or production/default-model change is part of this fix.

### Sonar follow-up implementation and validation

Added a shared _validate_compose_project guard in the existing Proposal helper module, used
by both _docker and Update write_router before subprocess. It rejects empty names, leading
options/underscores, uppercase or non-ASCII characters, spaces, control characters and shell
metacharacters; valid Compose names are unchanged. All three Docker exec/restart invocations
now place -- before the container operand. Router content stays on stdin; fixed container Python
code, restart timeout, readback failure and the collector's restoration behavior are preserved.

Added 41 parameterized security/positive regression cases across the existing two eval test files.
The focused Proposal/Update set passed all 126 tests. Canonical quick-check exited zero on the
current merged source plus this patch: 3,104 passed, 12 standard skips and 628 deselected. Config,
architecture, docs and generated-doc checks passed. The validation container used Python 3.12,
Node 24, pinned pnpm and real sudo-to-nobody uid 65534 without modifying the host sudo policy.
Docker's real CLI accepted the -- terminator for exec/restart and reported only missing operands;
no container target or operation was supplied for that parser check.

No Ruff findings on changed lines; 331 pre-existing findings in the large legacy eval scripts/tests
remain outside the edited lines. Whitespace validation passed. Product prompt and accepted live
evidence hashes remain unchanged, including all 270 accepted outputs and original observations.
No paid runs, live-stack restart, product/default-model changes or analysis suppression. Full-check
was not repeated for this CLI-only patch; quick-check is the current broad backend gate. At
completion of local validation, the source changes were uncommitted and unpublished. The two remote findings
remain unverified until the updated revision is published and SonarCloud reanalyzes it.

User subsequently explicitly requested "commit and push" for this validated follow-up. Commit
the five scoped files on feature/ANY-624 and push normally to origin; do not force-push. Remote
SonarCloud results remain pending until the new revision is analyzed.
