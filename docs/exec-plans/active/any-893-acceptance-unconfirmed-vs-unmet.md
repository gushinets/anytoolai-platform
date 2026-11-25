# Acceptance Builder delivery evidence (ANY-893)

## Status

- State: active
- Owner: agent
- Created: 2026-11-20
- Last updated: 2026-11-25
- Review date: 2026-11-25
- Next action: owner acceptance of the verified ticket cases.
- Blocker: none for the Linear acceptance criteria.

## Goal and boundaries

Distinguish confirmed, unconfirmed and explicitly unmet requirements in Check deliverable.
A check requires at least one identifiable client condition. Drafting criteria remains independent.

## Implementation plan

1. Capture the local baseline and add the ticket cases to the existing evaluator.
2. Align the product prompt, comparison categories, schema, and fixtures.
3. Validate the outcome in the web parser and reuse field-level validation.
4. Exercise new runs, corrections and restored sessions. Record live and deterministic evidence.
5. After review, preserve every ordinary A11 verdict when A01 omits its lists. Strengthen the
   multilingual controls, restrict suite selection, then repeat the live series on a clean commit.

## Scope

Acceptance Builder owns the comparison and the presentation. The other freelancer products do
not contain this comparison instruction or clarity criterion.

## Initial evidence

The base commit is 5899798e4e7e283f54dc5b757286b23a678ab90b. The historical QA build SHA is unknown.
The former prompt classified missing detail as mismatch, and clarity required listing undone work.

## Implementation decisions

Keep the kernel A11 status enum. Match requires confirmation, partial covers unconfirmed or partial
delivery, and mismatch requires affirmative evidence of a violation. A clear list satisfies clarity.
For meaningful briefs, any mismatch fails, any remaining partial gives partial agreement, and all
matches pass. An explicit insufficient brief returns the user to the brief field without copy or
activation for any combination of the four valid delta statuses. The prompt still requests four
partial deltas when the brief contains no requirements.
Keep prompt v1, quota charging on completed runs, existing dependencies and the two provider calls.
The model still judges dates and evidence from prose.

## Acceptance evidence

The Python matrix covers confirmed, unconfirmed and contradicted requirements and every
allowed insufficient-brief status. The workflow integration test exercises the product
category through A11 and the stored result. Web tests cover ordinary verdicts with empty extracted lists, localized
inline hint, focused field, suppression of copy and activation, restored attachments, fresh
idempotency on correction, and visible evidence for an explicit omission.

The verdict suite contains seven cases in Russian, English and Spanish. The Russian brief
and W1 come from the ticket. Each language includes a greeting, junk, missing reviews,
missing Figma sources, unrelated work and a fully confirmed control.

The isolated dev stack passed readiness and used the configured Sol policy with medium effort.
The first Russian W1 extraction failed twice at provider transport. The worker logged HTTP 401
and an expired credential. The ledger recorded zero estimated cost and no comparison output.
Zero of 63 planned post-change runs completed. The optional historical baseline produced no
model outputs either. Its initial build stopped on source fingerprint drift as edits landed.

[Worker snapshot, run input, session and provider ledger](any-893-acceptance-unconfirmed-vs-unmet.evidence-20261120.json)

After renewing the existing live credential, use a fresh output directory and review the
returned evidence against each case. The worktree API and project are printed by dev-ready.

```sh
python scripts/agent/runner.py dev-live-up --product acceptance_builder
python scripts/agent/runner.py dev-ready
python scripts/agent/brief_language_eval.py run --suite tests/fixtures/acceptance_verdict_eval/cases.json \
  --family verdict --scenario acceptance_builder.check_v1 --project anytoolai-e986bbcb \
  --api-url http://127.0.0.1:18782 --repeats 3 --out /tmp/any893-repeat
```

## Verification and review notes

Doctor passed under the repository-managed Python 3.12.13. System Python 3.14 lacked pytest and pydantic.

The freelancer suite, Acceptance Builder API bundle and evaluator tests passed together
(1,564 tests). The focused web product, language and contract suites passed (81 tests).
Configuration, architecture, documentation, and generated-doc checks passed.

The final full-check stopped at the existing runner test
`test_prod_stack_running_reflects_compose_ps_output` (313 passed before the failure).
With a local Compose environment file present, the test's subprocess double returns process-list
text where the environment probe expects JSON. This failure also appears in the ANY-762 record.

The initial quick-check overlapped implementation (4,250 passed, 12 skipped, four failed).
Its collected API assertion expected the old three-category workflow. The final 59-test API
rerun passed with the four-category contract. The other three failures were the two existing
Compose subprocess tests and the activation marker test requiring passwordless sudo.

The full frontend-check passed on retry, including lint, typecheck, workspace tests,
generated API types and production builds. Its first run timed out in the ce-kit ESLint
configuration test during the Docker build.


### Review corrections and live verification, 2026-11-23

The tested commit was `4a7ca8d971795f5d806eb8f67e9a06aaa3b44229` with a clean checkout.
Both the API and worker passed deployment fingerprint verification. The worker used
`openai/gpt-6.1-sol` with medium reasoning effort. The collector scheduled all 63 runs.
On the first Russian W1 input the provider reported an expired credential (HTTP 401).
Both physical extraction attempts failed with zero estimated cost. Comparison never ran.
The evaluator report returned exit code 1 with 0 PASS, 1 FAIL and 62 PENDING.
The report documents an authentication failure before comparison. AC5 already has regression
coverage and a build identifier. At that point the remaining evidence was a repeat series with assessable
outcomes. Linear specifies neither a live provider nor the 63-run multilingual matrix.

[Per-run statuses, build fingerprints and failed-call ledger](any-893-acceptance-unconfirmed-vs-unmet.evidence-20261123.json)

All 176 targeted Python tests and 85 focused web tests passed. The Python checks cover
suite selection and the canonical schema. The web checks cover each ordinary verdict with
empty lists, including a visible and counted process violation. SonarCloud marked issue
`AaIHNfZINZCHnXHFWfnm` CLOSED/FIXED and passed the quality gate for the tested commit.

Doctor, config, architecture, documentation and generated-doc checks passed. Full-check
again stopped at the Compose environment probe in
`test_prod_stack_running_reflects_compose_ps_output` (313 passed, one failed).
The local frontend gate passed lint and typecheck, then timed out in the ce-kit ESLint
configuration test, including on retry. That test passed in isolation with its original
timeout. All 1,139 web-mirror tests, generated API type verification and workspace builds
passed independently.

### Acceptance against the Linear criteria, 2026-11-23

All nine planned Russian ticket runs passed the evaluator report. The local API and worker
verified the deployment profile on commit `7f06f6a1013a4f291cd33bb73226b702da24522c`.
Only this execution plan had tracked edits during collection. The worker used the Sol policy.
Each completed live session was then opened by session ID in the Russian web client.

| AC | Observed result |
| --- | --- |
| 1 | A + W1 returned `partially_meets` three times. Each answer credited the sections, responsive layout, email form, client domain, Figma and revisions. Each accepted December 3 against December 10 and expressly identified the start-relative duration and personal approval as unconfirmed. |
| 2 | All three W1 answers rated clarity `match` from the description of completed work. |
| 3 | Both the greeting and junk yielded `insufficient_brief` with four partial deltas. In Chromium both sessions showed the Russian requirements hint at the invalid brief field, with no verdict or Copy button. |
| 4 | Missing reviews, withheld Figma sources and the unrelated café logo each yielded `does_not_meet` with the specific violation visible in the web client. FULL yielded `meets_expectations` with four matches. |
| 5 | The regression tests are recorded above. The repeat series records the SHA, deployment and worker fingerprints, nine session and result IDs, complete model outputs, semantic reviews and browser observations. The ledger recorded 18 successful provider calls with an estimated total cost of USD 0.1060338. |

The earlier 63-run authentication failure is retained as a separate historical attempt.
The nine-run series covers the Linear ticket examples on this build.

[Inputs, reviewed outputs, browser checks and provider call ledger](any-893-acceptance-unconfirmed-vs-unmet.ru-live-20261123.json)

### Second review regression, 2026-11-25

The API and worker regression replays the recorded greeting and W1 delivery with one change
to the comparison output. Clarity is `match`. The worker calls extraction and comparison
once each, completes the session and publishes the result. Both a new web run and a restored
session focus the brief field, show the hint and suppress the verdict, Copy and result-view event.
The HELLO and JUNK evaluation criteria in all three languages now score the explicit verdict
and its explanation independently of the delta statuses.
