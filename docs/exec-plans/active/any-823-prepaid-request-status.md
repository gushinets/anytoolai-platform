# Execution Plan: ANY-823 — Preserve prepaid request work and payment status

## Status

- State: active
- Owner: agent
- Created: 2026-11-27
- Last updated: 2026-11-27
- Review date: 2026-12-04
- Next action: Owner review of the round 2 local fix; live rerun deferred at the owner's request.
- Blocker: No fresh live evidence for the round 2 prompt; canonical full-check previously had three environment-dependent runner failures.

## Goal

Keep a stated deposit-before-start term, its agreement status, actual work commencement and payment delinquency separate. Preserve explicitly stated statuses independently in all languages without changing payment-request selection or financial terms.

## Scope and contracts

Only the product-owned `client_update_writer.prepaid_request_compose_persuasive_text.v1` prompt and its Python contract test change. No API, DB, UI, workflow, model or generic A06 changes. The other product prompts do not implement this prepaid-request path; similar errors elsewhere remain unverified risks.

## Implementation steps

- [x] Add a focused normalized-prompt contract test and observe it fail before the fix.
- [x] Insert the status instructions after the payment-arrangement list; preserve A–C precedence and rule D requests.
- [x] Run the focused test, product module and canonical full-check (three known runner failures; see below).
- [x] Freeze three original inputs (three attempts each) and nine localized contrast inputs from the historical ANY-604 evidence.
- [x] Submit all 18 via the live browser form and capture deployed prompt proof, actual payloads and all ledger attempts. Provider failure prevented output/model, copy equality and semantic verification.
- [x] Obtain a successful live series; no model comparison required because all outputs preserve status.
- [x] Complete verification and obtain explicit owner approval to commit and push the scoped changes.

## Relevant evidence

- [Historical acceptance report](../completed/any-604-prepaid-request-live-acceptance.md)
- [Historical inputs and outputs](../completed/any-604-prepaid-request-live-acceptance.evidence.json)
- [Architecture boundaries](../../architecture/platform-boundaries.md)

## Decision log

- 2026-11-27: Use semantic instructions, not language-specific phrase filtering or a product-specific generic validator. The existing prompt owns the interpretation of the payment notes.

## Progress log

- 2026-11-27: Source revision `95b62005e46130644ee80021ecc253a1f18c3fe1`. System Python doctor lacks pytest/Pydantic; managed `.quick-check-venv/bin/python` (3.12.13) doctor passed. Docker socket access was denied in the default sandbox. Existing untracked `api.http` is unrelated and will not be changed.
- 2026-11-27: Regression test failed on the original prompt as required (1 failed, 76 deselected). After adding the three status instructions, all 77 product tests passed in 0.61s. The registry still resolves the v1 prompt; working-tree SHA-256 is `83d8467aff887e4c66970df02acbf03c3451ccff1eb5464d5706fc4e2d80f110`.
- 2026-11-27: Frozen all 18 planned inputs in [the evidence record](any-823-prepaid-request-status.evidence.json), with expected payloads distinct from actual submissions. No language/length generation overrides. Historical evidence is unchanged.
- 2026-11-27: Escalated read-only Docker inspection confirmed no running containers. Automatic approval review rejected starting the live stack because external LLM inputs and provider cost require explicit approval. No requests were sent; the live matrix and deployed prompt provenance remain pending. Sanitized diagnostic context collected.
- 2026-11-27: Initial full-check was blocked by sandbox DNS during build dependency installation; network-enabled retry installed dependencies but exposed missing execution-plan metadata, now corrected. Config, architecture, docs and generated-doc checks passed on the subsequent run; broad tests in progress.
- 2026-11-27: Entire Freelancer Suite passed (1,726 tests) after the network-enabled retry resolved the packaging build dependency. Full-check backend finished with 4,380 passed, 3 failed, 12 skipped, 723 deselected. The failures are the same runner tests previously recorded in ANY-605: `test_prod_stack_running_reflects_compose_ps_output`, `test_prod_stack_running_propagates_timeout`, and `test_activation_marker_is_readable_by_non_root_api_user` (environment/mock mismatch and sudo authentication). No unrelated source edits. Separately, frontend-check completed lint, typecheck, tests, generated contract verification and builds successfully.
- 2026-11-27: User explicitly authorized the 18 live form submissions. Canonical `dev-live-up` started the isolated stack and verified source and deployment fingerprints. Worker SHA-256 matched `83d8467aff887e4c66970df02acbf03c3451ccff1eb5464d5706fc4e2d80f110`. The current live policy is `sol_text_generation_v1`, routing to `openai/gpt-6.1-sol` (not the historical Luna policy). No production config changed.
- 2026-11-27: Submitted all 18 inputs via the browser; exact payload equality verified for all 18. All 18 sessions created one failed logical A06; the ledger records two failed physical transport attempts per action (36 total), all `provider_request_failed`, and no result artifacts. Worker reports `BadRequestError`; safe ledger exposes no upstream HTTP status or detailed reason. Ledger model remains the configured alias, not proof of a provider response model. Recorded estimated cost USD 0 is a ledger estimate, not a billing reconciliation. Semantic/language verdicts are not evaluable; structural acceptance fails (0/18). No output or clipboard text was fabricated. The historical matrix is unchanged; additional model runs are not authorized and the semantic comparison condition has not been reached.

- 2026-11-27: User updated the provider key and requested the second live series. Recreated the isolated runtime and verified the matching prompt hash and deployment fingerprint; source and provider config unchanged. Archived the [original failed series](any-823-prepaid-request-status.provider-failed.evidence.json) intact.
- 2026-11-27: Second live series passed **18/18** (9 original and 9 contrast attempts, RU/EN/ES). Each submitted payload matched the frozen input; each session had one successful A06, one physical provider attempt on actual `gpt-6.1-sol`, one canonical text-only result, and exact equality of backend, visible and actual clipboard text. All 18 messages were reviewed in context for status, payment terms and language, with per-attempt justifications in the [successful evidence](any-823-prepaid-request-status.evidence.json). Ledger estimated cost USD 0.2025049; no provider retries. No model comparison or production model change needed.

## Acceptance status

**Live acceptance passed (18/18); local contract and product tests passed.** The original provider-failed series remains independently preserved. The three documented pre-existing environment-dependent runner failures remain in full-check, while separate frontend-check and the complete Freelancer Suite passed. No unrelated fixes or production configuration changes were made. The owner explicitly authorized pushing the scoped commit and instructed that the Linear ticket remain open without a comment or status update.


## Review round 1 — regression contract completeness

The product test pins the agreed-term and explicit-status instructions but not the ambiguous-start prohibition. Confirm the omission by temporarily removing only that sentence and running the test; add the normalized sentence assertion and repeat the mutation check, restoring the prompt bytes in both cases. Run the product module and documentation checks. Production prompt and live evidence remain unchanged.

Verified: removing exactly the ambiguous-start sentence left the original test green (1 passed). With the added assertion, the same mutation failed at that assertion (1 failed). Restoring the original prompt produced 77/77 passing product tests. The deployed-tested prompt SHA-256 remains `83d8467aff887e4c66970df02acbf03c3451ccff1eb5464d5706fc4e2d80f110`, so the retained 18/18 live acceptance evidence still applies to production behavior. No additional provider calls required.


## Review round 2 — payment term versus agreement

Both independent P2 findings identify the same error: the unconditional agreed-term instruction conflicts with Step 2, which permits a consistent payment request even when agreement is unspecified. Preserve each term's agreement status independently of timing, actual start and delinquency. A silent agreement status is neither assent nor a dispute; explicit open conditions continue to select rule B. The ProposalAI and sibling reply prompts already distinguish agreement from a proposal or request; the other products do not share this payment-request path.

Plan: update the existing normalized-prompt contract test first, verify failure against the current prompt, then replace only the unconditional agreement instruction. Keep the other two assertions and pin Step 2's existing silent-agreement behavior. Run product and config/documentation checks. Retain the earlier live evidence; the changed prompt requires a fresh 18-case status matrix plus 12 agreement contrasts (standard, explicitly agreed, only another term agreed, explicitly open; RU/EN/ES), pending authorization for the provider calls.

Verified locally: the updated contract test failed against the former prompt, then the product module passed 77/77 after the fix. Configuration, architecture and documentation validation passed. Freelancer Suite initially had the known sandbox dependency-resolution failure in its packaging test (1725 passed); the network-enabled local retry passed all 1726 tests. The owner requested local tests only, so no new provider calls were made and the proposed 30-case matrix is deferred. New working-tree prompt SHA-256: `cf2b80ff1f0064213e3ca43b47a02d138b7cc2ddf870a67061bee9c4602090d9`. The recorded 18/18 live matrix applies only to the prior prompt hash; semantic acceptance of the new version is unverified.
