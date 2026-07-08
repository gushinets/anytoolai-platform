# Action Runner

`ActionRunner` is the platform-core orchestration layer for one runnable action execution.

## Responsibility split

Runtime path:

```text
ActionRunner
  -> resolve action config / prompt / provider policy / schemas from ConfigRegistry
  -> validate input payload against action definition input schema
  -> create platform.action_runs row and emit action.started
  -> call executor selected by action definition executor id
  -> update platform.action_runs to succeeded or failed
  -> return ActionResult
```

`ActionRunner` owns:

- action config resolution by `action_type` + `action_config_id`
- input validation
- action-run lifecycle persistence
- action lifecycle events
- linking output artifacts back to `action_run`
- propagation of execution context dimensions through runtime calls

`ActionRunner` does not own:

- direct provider/model calls
- PydanticAI agent construction
- structured-output validation retries
- provider-call ledger persistence
- artifact persistence as a hidden side effect outside the structured-output path

## Boundaries

- `StructuredLlmActionExecutor` is the only allowed PydanticAI boundary.
- `ProviderGateway` is the only allowed physical provider-call boundary.
- Cached executor/provider objects may use only stable config keys, never run-specific ids.
- Run-specific ids and identity dimensions travel through `ExecutionContext`, action-run metadata,
  provider requests, artifacts, and events.

## First runnable atoms

The first generic runnable atoms are:

- `text.extract_structured_fields`
- `text.detect_issues_by_taxonomy`

For these atoms the repo now includes:

- action definitions in `configs/kernel/action_definitions/`
- kernel demo action configs in `configs/kernel/products/kernel_demo/action_configs.yaml`
- prompt refs in `configs/kernel/products/kernel_demo/prompts.yaml`
- concrete kernel schemas in `configs/kernel/schemas/`
- deterministic fake-provider fixtures in `tests/fixtures/provider/fake_provider_outputs/`

## Persistence and correlation

`ActionRunner` writes or links:

- `platform.action_runs`
- `platform.artifacts` through the structured-output finalizer path
- `platform.event_log` action lifecycle rows

When an executor or input-validation error is raised and the exception escapes the caller's
`transaction_boundary()`, `ActionRunner` still preserves durable failed action state by replaying
`platform.action_runs` failed persistence and the `action.failed` event in an independent recovery
transaction. The original exception is still re-raised to the caller. If the caller catches the
exception inside the active transaction boundary, the normal in-transaction failed update/event
path is committed instead.

Canonical artifact linkage is also runner-owned: `output_artifact_id` may reference only an
existing `structured_output` artifact for the same `action_run`. Arbitrary executor metadata values
and raw debug artifacts must not become the canonical output pointer.

Provider-attempt correlation remains gateway-owned through:

- `platform.provider_calls`
- `provider.request_started`
- `provider.request_succeeded`
- `provider.request_failed`

The required execution context for action runs includes:

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
