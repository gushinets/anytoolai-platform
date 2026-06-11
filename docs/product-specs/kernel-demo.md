# Kernel Demo

Kernel Demo is not a user-facing product. It is a technical smoke surface for MVP-A.

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

The handoff smoke may be represented as source and target scenarios as long as it proves source session -> handoff token -> target session.
