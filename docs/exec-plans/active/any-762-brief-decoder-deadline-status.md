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
