# Kernel Demo

Kernel Demo is not a user-facing product. Its backend scenarios and proof CLI belong to MVP-A1;
the thin Chrome Extension smoke surface belongs to MVP-A2 Client Surfaces.

Scenarios:

- `kernel_demo.single_action_smoke_v1`
- `kernel_demo.multi_step_workflow_smoke_v1`
- `kernel_demo.quota_exhausted_smoke_v1`
- `kernel_demo.handoff_smoke_source_v1`
- `kernel_demo.handoff_smoke_target_v1`

The multi-step smoke workflow exercises:

```text
text.extract_structured_fields
-> text.detect_issues_by_taxonomy
-> document.generate_from_template
```

The implemented `kernel_demo_source_to_target_v1` handoff maps the canonical source workflow-result
artifact into a separate safe preview and schema-valid target input. It requires consent, uses the
`immediate` policy, creates a linked target session and queued target job, and proves that worker
action/provider/artifact lineage remains under that target session with the runtime `handoff_id`.

MVP-A1 completion does not depend on the Kernel Demo Chrome Extension, web mirror, or browser
evidence. Those client proofs are part of the MVP-A2 release gate.
