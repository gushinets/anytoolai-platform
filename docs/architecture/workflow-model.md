# Workflow Model

Workflow is backend-defined chain of action configurations.

MVP-A supports:

- sequential steps;
- simple input mapping;
- simple output mapping;
- simple `when` condition;
- stop on failure;
- retry per action config;
- job status;
- final artifact;
- workflow events.

Workflow definitions contain:

```text
WorkflowDefinition
  steps[]
    step_id
    action_config_id
    input_mapping
    output_mapping
    when optional
```

MVP-A does not support:

- visual builder;
- parallel branches;
- long-lived resumable workflows;
- compensation;
- human approval queues;
- workflow graph editor;
- nested subworkflows;
- streaming UI;
- external webhooks as steps.
