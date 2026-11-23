# Acceptance Builder delivery evidence (ANY-893)

## Status

- State: active
- Owner: agent
- Created: 2026-11-20
- Last updated: 2026-11-23
- Review date: 2026-11-23
- Next action: repeat the live regression series once the provider credential is renewed.
- Blocker: the configured provider credential has expired (HTTP 401).

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
matches pass. An insufficient brief requires four partial deltas. Only an explicit insufficient brief
returns the user to the brief field without copy or activation.
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
There was no output to assess against the revised criteria. AC5 remains open.

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
