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

The conditional claim and `workflow.started` event commit together before action execution. If
workflow execution fails, the job is marked `failed` with `completed_at`, a safe error code/message,
and a `workflow.failed` event. Existing rollback-recovery callbacks keep that failure durable when
the execution transaction escapes.

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
