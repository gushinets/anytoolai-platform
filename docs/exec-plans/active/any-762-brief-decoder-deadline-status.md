# Execution Plan: Brief Decoder deadline status (ANY-762)

## Status

- State: active
- Owner: agent
- Linear: ANY-762
- Created: 2026-11-17
- Last updated: 2026-11-17
- Review date: 2026-11-24
- Next action: product-owner review and acceptance of this iteration; live deadline regression passed.
- Blocker: none for the scoped implementation/live regression; broad repository checks retain the unrelated failures below.

## Goal

Keep a deadline's or budget's stated status with its value through extraction and the short
document: preferred/desired, tentative/estimated, conditional, or agreed/fixed. Do not invent,
upgrade, or downgrade status. Keep the existing string fields and workflow/prompt versions.

## Scope

- `packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products/brief_decoder/prompts/extract_brief.v1.md`
- `packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products/brief_decoder/prompts/generate_summary.v1.md`
- `packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products/brief_decoder/workflows.yaml`
- `tests/fixtures/brief_decoder_eval/deadline_status.json`
- `packages/backend/product-platforms/freelancer-suite/tests/test_brief_decoder_deadline_status_rule.py`

The field and its summary share one semantic contract; no new status field, runtime parser,
frontend behavior, dependency, or model configuration is needed. Keep language-policy and
analysis-directions blocks unchanged. Existing fake-provider fixtures remain unchanged.

Cross-product inspection: ProposalAI and Client Update Writer already preserve commercial-term
status. Acceptance Builder extracts criteria, assumptions, and deliverables, without the structured
deadline/summary pair. No identical extraction rule was found in those three products.

The ANY-850 attachment was retrieved and its document text inspected. It does not contain the
English landing brief or the quoted schedule line. The English regression uses the task's permitted
synthetic fallback and records that provenance; the Russian acceptance input is transcribed verbatim.

## Implementation plan

1. Add the general status-preservation rule to extraction and both field descriptions.
2. Preserve that status in Key details, every document section, and the summary.
3. Add seven RU/EN/ES cases: preferred, conditional, tentative, agreed, and plain terms.
4. Test prompt contracts, original input identity, input schemas, and authored expected statuses.
5. Run repository checks and inspect the configured local stack for three live runs per case.

## Validation

- `python scripts/agent/runner.py doctor`: system Python 3.14 lacks pytest and pydantic.
- `.quick-check-venv/bin/python scripts/agent/runner.py doctor`: passed with Python 3.12.13;
  pnpm 10.34.1 works outside the filesystem sandbox.
- `python scripts/agent/runner.py quick-check`: 4,251 passed, 3 failed, 12 existing skips,
  720 deselected by the existing baseline selection. The first sandboxed bootstrap could not
  reach PyPI; the completed run used the normal managed environment with network access.
- `.quick-check-venv/bin/python scripts/agent/runner.py validate-configs`: passed.
- `.quick-check-venv/bin/python scripts/agent/runner.py validate-docs`: passed after adding
  the required review-date metadata.
- `.quick-check-venv/bin/python scripts/agent/runner.py generate-docs --check`: passed;
  no generated-file changes required.
- `PYTEST_ADDOPTS=-x .quick-check-venv/bin/python scripts/agent/runner.py full-check`:
  failed at the same existing production-stack runner test (313 passed before fail-fast).
  Its frontend/product stages were not reached; independent results are recorded below.

- New regression module: 19 passed. Focused Brief Decoder/language/analysis-directions tests: 123 passed.
- Full product test directory: 335 passed; its packaging test initially failed in the sandbox and
  passed separately with uv cache/download access (336 tests covered in total).
- `frontend-check`: lint and typecheck passed; the unchanged CE-kit test
  `reactHooksAppliesToTsFiles.test.ts` exceeded its 5-second timeout on both the normal run and
  a retry with workspace tasks serialized. It passed in isolation in 3.35 seconds. No timeout or
  assertions were changed; the complete frontend check remains non-green.

### Unrelated broad-check failures

All three backend failures are in unchanged `tests/test_runner.py` / `scripts/agent/runner.py`:

- `test_prod_stack_running_reflects_compose_ps_output`: the existing local `.env.prod` makes the
  environment resolver consume the test's mocked container-ID output as JSON.
- `test_prod_stack_running_propagates_timeout`: the same environment-resolution path reaches the
  mocked subprocess with the env-resolution timeout rather than the stack-query timeout.
- `test_activation_marker_is_readable_by_non_root_api_user`: `sudo -n -u nobody` reports that
  interactive authentication is required on this host.

Collected sanitized context through the repository runner. No tests were skipped, weakened, or
marked expected-failure to hide these results. Existing local-review-command references were also
found in unrelated tracked plans for ANY-17, ANY-339, ANY-391, ANY-221, and ANY-227; left untouched.

### Live verification

On 2026-11-17 the user explicitly authorized sending these seven fixture briefs to OpenAI for
21 live runs and pushing the result to `feature/ANY-762`. This resolved the initial automatic
approval rejection. Exactly three runs per case were collected through `brief_decoder.decode_v1`
over the local API and worker; no extra workflow runs were submitted.

The existing worktree stack was refreshed using `dev-live-up --product brief_decoder` on its
existing API/PostgreSQL ports (8015/5455); both deployment-profile checks passed. The collector
verified that the running extraction prompt, summary prompt, and workflow hashes matched the
changed source files, and that the worker snapshot stayed unchanged throughout all 21 runs.

**Result: 21/21 PASS for deadline status**, based on direct agent reading of each extracted
`deadline`, its Key details line, and the summary for contradictions, plus deterministic checks
of status markers, deadline digits, input/output schemas, and persisted ledger/artifact identity.
This is an agent semantic review, not recorded human acceptance or a full product-quality audit.

| Case | Expected meaning | Extracted deadline | Key details |
| --- | --- | --- | --- |
| BD-RU-05 | Desired 10 days; freelancer has not given a final estimate | 3/3 PASS | 3/3 PASS |
| BD-EN-PREFERRED | Preferred three weeks from kickoff, launch by December 10 | 3/3 PASS | 3/3 PASS |
| BD-RU-CONDITIONAL | Launch December 15 only if designs are ready December 1 | 3/3 PASS | 3/3 PASS |
| BD-ES-TENTATIVE | About four weeks, tentative and pending designer confirmation | 3/3 PASS | 3/3 PASS |
| BD-RU-AGREED | Agreed December 20 delivery | 3/3 PASS | 3/3 PASS |
| BD-EN-AGREED | December 20 agreed with the developer | 3/3 PASS | 3/3 PASS |
| BD-EN-PLAIN | Plain March 3 date, without an invented status | 3/3 PASS | 3/3 PASS |

No new date, duration, final estimate, or confirmation was found in the checked deadline fields
and lines. The agreed/plain cases sometimes ask for the unspecified year; that preserves the
source date and does not turn an agreed term into a tentative one.

All **84 physical provider calls succeeded**, with `actual_provider=openai` and `model=gpt-6-luna`.
The worker router reported `openai/gpt-6-luna` / `reasoning_effort=medium` before and after the runs.
The provider-call ledger's separate reasoning-effort field is null, so the evidence establishes the
configured effort but does not claim independent confirmation of each request's effort.
No model configuration was changed.

[Captured live evidence](any-762-brief-decoder-deadline-status.evidence-20261117.json) contains the
source commit and hashes, fixture/input hashes, all 21 session/job/result identifiers, actual deadline
fields and document outputs, projected provider-call rows, formal check results, and agent review
rationales. Authored canonical fixtures remain separate from these captured responses.

After recording the evidence, `validate-docs` and `generate-docs --check` passed. The latter
needed a network-enabled retry after LiteLLM's model-cost-map import failed inside the sandbox.
All seven input schemas and all 21 recorded formal/semantic verdicts were checked again locally.
No production code changed during live verification, so the earlier broad-check results stand.

### Limits and deferred polish

- Three repetitions per case on one configured model are regression evidence, not a guarantee for
  arbitrary inputs. Budget-status behavior was not live-tested by this deadline-focused suite.
- The English preferred-schedule input is the permitted synthetic fallback, not the original QA brief.
- Some outputs repeat missing-budget or deliverable information, and some mention a missing budget
  in Key details. These presentation issues do not change deadline status and are deferred.
- The scoped fix is good enough for this iteration's product-team review. Keep broader product
  improvement iterative; unrelated repository-check failures above remain visible and unchanged.

## Review correction 1

The inline P2 identified a real test gap: authored canonical strings and any-marker checks
cannot verify a captured workflow result, and a subset-of-digits check permits lost prerequisites.
Local negative probes also accepted reversed dependencies and the negated phrase "not agreed".
The captured live answers remain valid; this correction changes tests, not product prompts.

### Implementation plan

1. Add one output-shaped test helper with closed clause rules for the seven known cases.
   Accept a deadline only when all required facts and their relationship are present in a
   reviewed form. Unrecognized wording fails for review rather than receiving a semantic guess.
2. Replay all 21 captured responses through that helper, independently checking the extracted
   deadline and the actual Key details content; ignore cached verdicts and derived line fields.
3. Assert the exact case/attempt inventory, input hashes, and relevant source hashes. Add
   negative controls for each field, every case, missing/duplicate sections, irrelevant marker
   decoys, lost dates/confirmation, reversed conditions, and negated agreement.
4. Validate and record results, then push the correction and update PR #281 as authorized.

Implemented the shared output check in
[`tests/support/brief_decoder_deadline_status.py`](../../../tests/support/brief_decoder_deadline_status.py).
The regression module now applies it to all seven canonical examples and all 21 saved answers.
The evidence adapter reconstructs `brief.values.deadline` from the captured projection and reads
the persisted document directly; cached verdicts and the derived `deadline_line` do not decide
whether an answer passes. Inventory and source/input hashes guard the capture's provenance.

Negative coverage includes 26 corrupted clauses, each tested independently in the extracted field
and Key details, plus missing/duplicate structure, unrelated qualifier decoys, contradictory
deadline items, and a prerequisite detached from its launch clause. Presentation-only changes
remain accepted. Fixtures, prompts, workflow configuration, and captured evidence are unchanged.

Validation:

- Focused regression module: **107 passed**, including **21/21 captured answers**.
- Freelancer Suite tests: **424 passed**.
- Ruff on both changed Python files: passed.
- Repository doctor, configuration, architecture, documentation, and generated-doc checks: passed.
- `PYTEST_ADDOPTS=-x python scripts/agent/runner.py quick-check`: **313 passed, 1 failed,
  720 deselected**. The unchanged `test_prod_stack_running_reflects_compose_ps_output` still fails
  because the local Compose environment file activates an extra resolver call that its subprocess
  mock does not handle. This is the previously recorded broad-check blocker, not a passing gate.

No additional paid provider runs were made. This replay verifies the recorded answers and the
checker; it does not establish future model behavior. The checker deliberately accepts only
reviewed clause forms and one labeled deadline item: unfamiliar wording/layout requires review.

## Review correction 2

The second P2 exposed a broader gap: the checker ignored summary, other sections, titles,
and additional Key details lines, although these are all included in the copied document.
Contradictions inserted into those surfaces passed while the checked deadline clause stayed valid.
The user authorized checking the complete copied document, negative controls, replaying the 21
saved answers, validation, push, and a PR description update. No paid reruns are needed.

### Implementation plan

1. Keep the clause checks for the extracted deadline and Key details. Separate their narrow
   canonical-example entry point from the complete-output checker so partial fixtures cannot
   silently bypass whole-document validation.
2. Review every saved document and record independent SHA-256 references for its summary and
   ordered section IDs/titles/contents as one complete variant. The persisted evidence remains
   the readable reference; the checker must not derive allowed hashes from the candidate or
   automatically regenerate the approved references. Metadata is not copied and is excluded.
3. Reject unknown document variants pending semantic review. Exercise replacements and appended
   contradictions in summary, every section content/title, and extra Key details lines, across
   all seven cases. Preserve positive coverage of omitted deadlines and missing-year questions.
4. Replay all 21 saved answers, run the product suite and repository checks, record the outcomes,
   and publish the correction. Prompts, runtime behavior, and existing evidence stay unchanged.

Implemented the independent references in
[`reviewed_documents.json`](../../../tests/fixtures/brief_decoder_eval/reviewed_documents.json).
All 21 complete documents were read for deadline-status contradictions; none were found.
Questions about missing years, budget confirmation, and summaries omitting the deadline are
compatible with the reviewed deadline facts. This review does not certify unrelated prose quality.

The complete-output checker requires both the existing clause checks and a reviewed document
fingerprint. Partial canonical examples use the explicitly narrower `assert_deadline_clauses`.
There is no automatic reference regeneration: a new fingerprint requires review of every copied
text field. Neither cached PASS labels nor the candidate itself supply approved references.

Validation:

- Focused module: **295 passed**, including **21/21 saved outputs**.
- Added **180** independent replacement/append contradiction checks across all nine copied text
  fields. Every mutation keeps the extracted deadline and checked Key details clause valid.
  Additional controls cover missing text, removed/duplicated/reordered sections, unknown prose,
  and unchanged copy text when uncopied metadata is removed.
- Full Freelancer Suite: **612 passed**.
- Ruff on changed Python files, repository doctor, configuration, architecture, documentation,
  and generated-doc checks: passed.
- `PYTEST_ADDOPTS=-x python scripts/agent/runner.py quick-check`: **313 passed, 1 failed,
  720 deselected**. It stops at the unchanged
  `test_prod_stack_running_reflects_compose_ps_output`, the same local Compose environment /
  subprocess mock mismatch recorded above. The broad gate is not green.

Prompts, workflow configuration, source briefs, and captured evidence are unchanged; no new paid
runs were made. Exact reviewed variants are a bounded regression guard, not an unrestricted
natural-language contradiction detector; even harmless prose changes require review. Replaying
saved outputs does not establish future model behavior.
