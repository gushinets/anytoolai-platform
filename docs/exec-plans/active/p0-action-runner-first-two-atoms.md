# Execution Plan: P0 ActionRunner First Two Atoms

## Status

- State: active
- Owner: agent
- Created: 2026-07-07
- Last updated: 2026-07-07

## Goal

Implement a runnable generic `ActionRunner.run(action_type, action_config_id, input_payload, context) -> ActionResult`
path that resolves config from the registry, validates input/output, executes through the generic
`StructuredLlmActionExecutor`, persists `action_runs` and output artifacts, emits runtime events,
and supports the first two product-neutral atoms:

- `text.extract_structured_fields`
- `text.detect_issues_by_taxonomy`

## Scope

### In scope

- Generic action-run orchestration in `platform-core/actions`
- Reuse of the existing structured-LLM executor boundary in `platform-actions`
- Input validation before execution and final output validation through the existing structured-output path
- `action_runs` lifecycle updates for `started`, `succeeded`, `failed`
- Output artifact linkage to `action_run` and execution context
- Action/provider/artifact event emission with required correlation dimensions
- First-two-atom config/fixture/schema/prompt alignment in kernel definitions
- Tests for happy path, provider failure, validation failure, context propagation, status transitions, artifact linkage, and emitted events
- Repo-local docs update describing the work

### Out of scope

- Product-specific action semantics
- Freelancer-specific logic
- Direct provider SDK calls outside `ProviderGateway`
- Runtime redesign outside the action-run slice

## Relevant docs read

- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/core-beliefs.md`
- `docs/architecture/platform-boundaries.md`
- `docs/architecture/package-layering.md`
- `docs/architecture/llm-runtime.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/agent/harness-engineering-map.md`
- `docs/architecture/action-model.md`
- `docs/architecture/config-model.md`
- `docs/architecture/provider-gateway.md`
- `docs/architecture/structured-output.md`
- `docs/architecture/runtime-storage.md`
- `docs/architecture/event-taxonomy.md`
- `docs/adr/0004-generic-structured-llm-executor.md`
- `docs/adr/0007-llm-runtime-pydanticai-litellm-sdk.md`

## Contracts touched

- API:
  - Internal runtime contract for `ActionRunner.run(...) -> ActionResult`
- DB:
  - `platform.action_runs`
  - `platform.artifacts`
  - `platform.event_log`
  - existing `platform.provider_calls` linkage/correlation
- Config:
  - action definitions
  - action configs
  - prompts
  - schemas
  - fake provider fixtures
- Events:
  - `action.started`
  - `action.succeeded`
  - `action.failed`
  - existing provider/artifact events emitted by lower layers
- Frontend:
  - none directly; preserve generic runtime dimensions for downstream consumers

## Files expected to change

- `packages/backend/platform-core/src/anytoolai_platform_core/actions/executor.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/actions/models.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/actions/runner.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/context/execution_context.py`
- `packages/backend/platform-actions/src/anytoolai_platform_actions/structured_llm/executor.py`
- `packages/backend/platform-actions/src/anytoolai_platform_actions/definitions/text_extract_structured_fields.py`
- `packages/backend/platform-actions/src/anytoolai_platform_actions/definitions/text_detect_issues_by_taxonomy.py`
- `configs/kernel/action_definitions/text.extract_structured_fields.yaml`
- `configs/kernel/action_definitions/text.detect_issues_by_taxonomy.yaml`
- `configs/kernel/products/kernel_demo/action_configs.yaml`
- `configs/kernel/products/kernel_demo/prompts.yaml`
- `configs/kernel/products/kernel_demo/schemas.yaml`
- `configs/kernel/products/kernel_demo/prompts/extract_structured_fields.v1.md`
- `configs/kernel/products/kernel_demo/prompts/detect_issues.v1.md`
- `configs/kernel/products/kernel_demo/schemas/*.json` for the first two atoms as needed
- `tests/fixtures/provider/fake_provider_outputs/kernel_demo.extract_structured_fields_v1.json`
- `tests/fixtures/provider/fake_provider_outputs/kernel_demo.detect_issues_v1.json`
- `packages/backend/platform-core/tests/unit/test_*.py`
- `packages/backend/platform-actions/tests/test_structured_llm_executor.py`
- repo-local docs file describing the implementation slice

## Implementation approach

### Config resolution

`ActionRunner` will accept both `action_type` and `action_config_id`, resolve the action
configuration from `ConfigRegistry`, verify that the resolved config matches the requested
`action_type`, then resolve:

- action definition
- prompt
- provider policy
- input schema
- output schema

The registry remains the source of truth. No provider/model/prompt/schema details will be
hardcoded in the runner.

### Validation

Input validation will happen in `ActionRunner` before execution using the action definition’s
`input_schema_ref`.

Output validation will stay in the current structured-output path:

- PydanticAI validation retries inside `StructuredLlmActionExecutor`
- final AnytoolAI validation and artifact persistence via `StructuredOutputFinalizer`

Validation failures should mark the action run failed with safe error metadata and preserve the
existing debug-artifact behavior.

### Persistence and events

`ActionRunner` will orchestrate:

1. create/start `action_run`
2. call the executor
3. update `action_run` to succeeded or failed
4. link output artifact id from executor/finalizer metadata onto `action_run`
5. rely on lower layers for provider/artifact events while emitting action lifecycle events through
   `ActionRunService`

Execution context must carry:

- `tenant_id`
- `region`
- `product_id`
- `frontend_id`
- `scenario_session_id`
- `job_id`
- `workflow_id`
- `workflow_version`
- `step_id`
- `guest_id` / `user_id` where applicable

The plan is to keep timestamps, workflow version, provider policy refs, model/provider logging, and
provider-attempt correlation aligned with the existing `action_runs`, `provider_calls`, `artifacts`,
and `event_log` storage contracts instead of introducing new logging shapes.

### First two atoms

Define the first two atoms with real runnable config:

- `text.extract_structured_fields`
- `text.detect_issues_by_taxonomy`

Ensure their action definitions, product action configs, prompts, input/output schemas, and fake
provider fixtures are mutually aligned and actually executable through the generic path.

### Docs impact

Add or update one repo-local docs file after implementation describing the action-runner slice,
touched runtime behavior, and how the first two atoms run through the generic path.

## Validation plan

- `python -m pytest packages/backend/platform-core/tests -q`
- `python -m pytest packages/backend/platform-actions/tests -q`
- `python scripts/agent/quick_check.py`
- `python scripts/agent/runner.py quick-check`

Note:
- `just doctor` was attempted first per `AGENTS.md`, but `just` is not installed in this environment, so fallback commands will be used.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-07 | Keep `ActionRunner` as orchestration only | Matches architecture split: registry/persistence/events in core, PydanticAI only in structured executor, provider calls only through gateway |
| 2026-07-07 | Reuse existing provider/artifact/event services instead of inventing parallel paths | Preserves current timestamps, ledger rows, event correlation, and artifact contracts |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-07 | Read required docs and inspected current action/runtime/provider/storage/event/config code | Implement `ActionRunner` and related contracts |

## Open questions

- Whether `StructuredLlmActionExecutor` should return a richer executor result type instead of a bare `ProviderResponse` to make output artifact linkage explicit in the runner
- Whether prompt variable rendering should remain JSON-append style for the first slice or be tightened while preserving existing tests

## Follow-up debt

- Broader reusable schema-validation helpers for non-structured-LLM actions
- Explicit docs for the final `ActionResult` contract once the generic runner surface settles
