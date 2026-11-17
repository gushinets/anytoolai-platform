# Execution Plan: Brief Decoder deadline status (ANY-762)

## Status

- State: active
- Owner: agent
- Linear: ANY-762
- Created: 2026-11-17
- Last updated: 2026-11-17
- Review date: 2026-11-24
- Next action: user review; explicit approval is required for live provider evaluation and GitHub writes.
- Blocker: live evaluation was rejected by automatic approval review; broad checks have unrelated failures below.

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

Live verification not run: automatic approval review twice rejected exporting these seven brief
inputs to the configured paid OpenAI provider and requires the user's specific approval of the
payloads and destination. An explicit approval request is pending; no live case was submitted.

The existing worktree stack was refreshed using `dev-live-up --product brief_decoder` on its
existing API/PostgreSQL ports (8015/5455); both deployment-profile checks passed. Worker readback
before refresh showed `openai/gpt-6-luna` / `medium`; no model configuration was changed.
Three repetitions of each of the seven cases remain to collect and review after approval.
No live pass counts are claimed. Deterministic fixtures are authored expected outputs, not captured
model responses; passing fixture tests is not proof of live behavior.
