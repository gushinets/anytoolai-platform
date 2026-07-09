# Execution Plan: Action Executor Response Contract Tightening

## Status

- State: active
- Owner: agent
- Created: 2026-07-07
- Last updated: 2026-07-07

## Goal

Tighten the `ActionExecutor.execute` response contract so `ActionRunner` no longer type-checks
against `Any` while assuming provider response fields at runtime, while keeping the executor
response generic and making provider details optional.

## Scope

### In scope

- Verify whether `ActionRunner` still consumes response fields from an untyped executor result.
- Add the smallest shared response protocol or concrete response type needed by `platform-core`.
- Update `StructuredLlmActionExecutor` and related typing/tests to implement the stricter contract.
- Run targeted validation for the changed backend modules.

### Out of scope

- Redesigning executor registration or workflow orchestration.
- Changing runtime behavior beyond the type contract needed for executor responses.
- Adding new executor implementations beyond what current tests require.

## Relevant docs

- `AGENTS.md`
- `docs/architecture/package-layering.md`
- `docs/architecture/llm-runtime.md`
- `docs/core-beliefs.md`

## Contracts touched

- Runtime: action executor request/response typing between `ActionRunner` and executors
- Runtime: optional provider-call details for provider-backed executors only
- Tests: executor and runner type-shape coverage

## Implementation steps

- [x] Verify the reported issue against current code.
- [x] Introduce the minimal typed response contract at the action executor boundary.
- [x] Update structured LLM executor typing and any dependent helpers/tests.
- [x] Run targeted validation and record outcomes.

## Validation

- [x] `uv run python scripts/agent/runner.py doctor`
- [x] `D:\Devpy\anytoolai-platform\.venv\Scripts\python.exe -m pytest packages/backend/platform-core/tests/unit/test_action_runner.py -q --basetemp D:\Devpy\anytoolai-platform\.pytest-tmp\platform-core`
- [x] `D:\Devpy\anytoolai-platform\.venv\Scripts\python.exe -m pytest packages/backend/platform-actions/tests/test_structured_llm_executor.py -q --basetemp D:\Devpy\anytoolai-platform\.pytest-tmp\platform-actions`
- [ ] `python scripts/agent/quick_check.py`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-07 | Use generic executor response dataclasses with optional `provider_call` details instead of a provider-shaped protocol. | The runner should depend on action-level output and metadata only, while provider-backed executors can attach optional provider information without forcing those fields on all executors. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-07 | Read required repo docs and verified that `ActionExecutor.execute` currently returns `Any` while `ActionRunner` dereferences `provider_policy_ref`, `provider`, `model`, `structured_output`, and `metadata` from the result. | Add a minimal typed response protocol and validate the existing structured executor against it. |
| 2026-07-07 | Replaced the provider-shaped executor response protocol with generic dataclasses: `ActionExecutorResponse` plus optional `ProviderCallInfo`. Updated `ActionRunner` to read provider data only from `response.provider_call`, and adapted `StructuredLlmActionExecutor` from `ProviderResponse` into the generic response shape. | Validate the affected runner/executor tests and close out the fix. |

## Open questions

- None currently.

## Follow-up debt

- Consider exporting the executor response contract through `platform-sdk` if third-party executor implementations become a supported extension surface.
- Some broad repo checks still depend on local pytest temp-directory behavior on this Windows machine; targeted validation was run with explicit workspace-owned `--basetemp` paths to keep this fix verifiable.
