# Workflow Model

Workflow is a backend-defined sequential chain of action configurations.

MVP-A keeps the contract intentionally small:

- sequential execution only;
- config-defined steps only;
- no durable workflow engine;
- no nested workflows;
- no parallel branches;
- stop on failed step;
- explicit final workflow artifact.

## Step schema

`WorkflowStepDefinition` supports these fields:

```text
step_id
action_config_id
input_mapping optional
output_mapping optional
when optional
retry_count optional, default 0
```

Existing simple YAML remains valid because every new field is optional.

## Mapping contract

`input_mapping` is a mapping of:

```text
<step input field path> -> <source path>
```

`output_mapping` is a mapping of:

```text
context.<target path> -> steps.<current_step_id>.output[.<field>...]
```

Supported source paths are:

- `scenario.input`
- `scenario.input.<field>...`
- `steps.<step_id>.output`
- `steps.<step_id>.output.<field>...`
- `context.<field>...`

Path rules:

- dotted object paths only;
- no array indexing;
- no wildcards;
- no expression language;
- `steps.<step_id>.output` references must point to an earlier step when used by `input_mapping` or `when`.

If `input_mapping` is omitted, the runner passes the full `scenario.input` object to the step.

Every successful step output is always available to later steps under
`steps.<step_id>.output`, even when `output_mapping` is empty.

## Skip semantics

`when` is a single source path, not an expression language.

The runner resolves the path and applies normal Python truthiness:

- truthy value: run the step;
- falsy value: skip the step and continue the workflow.

Skipped steps are persisted as `action_runs` rows with `status=skipped`.
The skip reason is stored in both:

- `action_runs.metadata.skip_reason`
- `jobs.metadata.workflow_state.steps.<step_id>.skip_reason`

The runner also emits `workflow.step_skipped`.

## Retry semantics

`retry_count` belongs to the workflow runner only.

Rule:

```text
total action execution attempts for one step = 1 + retry_count
```

Important boundary:

- workflow retry wraps `ActionRunner.run(...)`;
- it is not forwarded into LiteLLM, ProviderGateway, or provider policy;
- transport retries still belong to ProviderGateway/provider policy;
- validation retries still belong to PydanticAI inside the structured executor.

If a step still fails after all allowed workflow attempts:

- the workflow stops immediately;
- the job is marked failed;
- no later steps run.

## Final artifact rule

The workflow runner always creates a job-level final artifact on success.

Selection order:

1. use `context.workflow_output` if a step mapped it via `output_mapping`;
2. otherwise use the last successful step output object.

The selected payload is validated against `workflow.output_schema_ref` before the final artifact is
persisted and linked through `jobs.result_artifact_id`.

## Worker-owned execution

The worker claims a `created` job before invoking the runner. The claimed-job runner entrypoint
accepts that existing `running` job and never creates a second job row. Its input comes from the
linked scenario session's `metadata["input"]`; the session and job identifiers remain in the
execution context for every action, provider call, artifact, and event.

For A12, the public runtime API is queue-and-return:

- `POST /v1/products/{product_id}/scenarios/{scenario_id}/start` creates the scenario session first;
- it then creates one linked `created` job and returns immediately;
- `GET /v1/scenario-sessions/{id}` is the frontend-safe polling surface;
- workflow execution still belongs to the worker process, not the API process.

The conditional claim and `workflow.started` event commit together before action execution. If
workflow execution fails, the job is marked `failed` with `completed_at`, a safe error code/message,
and a `workflow.failed` event. If the execution transaction escapes and rolls back, shared
rollback-recovery orchestration rebuilds the durable workflow/action/provider/artifact history in a
separate recovery pass without introducing a durable workflow engine.

The public scenario-session payload intentionally compresses workflow internals into safe runtime
status and checkpoint fields. It must not expose prompts, provider policies, provider/model names,
retry budgets, PydanticAI run ids, or LiteLLM response ids.

## Events

Workflow runtime emits:

- `workflow.started`
- `workflow.canceled`
- `workflow.step_started`
- `workflow.step_skipped`
- `workflow.step_succeeded`
- `workflow.step_failed`
- `workflow.succeeded`
- `workflow.failed`

Real action executions still emit their normal action/provider/artifact events through
`ActionRunner`, `ProviderGateway`, and `ArtifactService`.

## Escaped rollback recovery

MVP-A still uses simple sequential execution inside one caller-owned `transaction_boundary()`.
When a workflow exception escapes that boundary after some rows or events were already flushed,
runtime code does not rely on ad hoc callback registration order to repair durable history.

Instead, the shared rollback executor runs explicit recovery phases:

1. recover durable runtime rows for artifacts, provider calls, action runs, and the workflow job;
2. replay only the missing lifecycle events in causal order.

For a failed workflow, the ordered replay contract is:

1. `workflow.started` first when the running job row exists but its start event is missing;
2. for each persisted step in workflow order:
   - `workflow.step_started` only when the original execution reached that step-start boundary
   - child `action.started`
   - child provider request events in attempt order
   - child `artifact.created` events
   - child action terminal event
   - step terminal event
3. `workflow.failed` or handler-owned `workflow.canceled` last.

The step-start boundary is semantic, not inferred from failure status alone. A `when` resolution
failure happens before the step starts and therefore recovers `workflow.step_failed` without
replaying `workflow.step_started`. Input mapping, action execution, provider, and output mapping
failures happen after the normal runner has emitted `workflow.step_started`, so recovery replays the
step-start event for those failed steps when it is missing.

This recovery is idempotent enough to tolerate partial durable state. Existing rows and existing
events suppress only their own replay. For example, a pre-claimed worker job may already have
durably committed `workflow.started`; later rollback recovery must preserve that row/event pair
without duplicating it while still backfilling any missing downstream events.

Replay uses the original transition timestamps where they are available from recovered rows:

- `jobs.started_at` for `workflow.started`
- `jobs.completed_at` for workflow terminal events
- related action timestamps for step started/terminal events when available

This keeps escaped rollback recovery causally valid while staying inside MVP-A's non-durable
sequential-runner scope.

## Non-goals

MVP-A does not support:

- visual builder;
- long-lived resumable workflows;
- compensation;
- human approval queues;
- workflow graph editor;
- nested subworkflows;
- streaming UI;
- external webhooks as steps.
