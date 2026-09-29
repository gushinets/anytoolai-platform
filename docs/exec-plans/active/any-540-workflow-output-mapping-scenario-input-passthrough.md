# Execution Plan: ANY-540 Workflow output_mapping scenario.input passthrough

## Status

- State: active
- Owner: agent
- Created: 2026-09-29
- Last updated: 2026-09-29
- Review date: 2026-10-06
- Next action: run the validation set, open the PR, address review; then rebase ANY-26 on it.
- Blocker: none

## Goal

Let a workflow step copy `scenario.input[.<field>...]` verbatim into `context.*` through
`output_mapping`, as a generic, product-neutral Platform Core capability. Needed by ANY-26 so the
Brief Decoder artifact can carry the caller's original brief (a handoff mapping can only read the
source artifact).

## Scope

### In scope

- `workflows/mappings.py`: runtime resolution and step-contract validation accept the
  `scenario_input` source root in `output_mapping`; `context.*` and other steps' outputs stay
  rejected.
- `workflows/runner.py`: pass the scenario input to `apply_output_mapping`.
- `docs/architecture/workflow-model.md`: the `output_mapping` contract lists the new source.
- Tests: mapping unit tests, plus a runner-level test on a patched kernel_demo workflow.

### Out of scope

Handoff contract, lifecycle or mapping grammar; new mapping functions (concatenation, truncation,
indexing); any product config (Brief Decoder / Acceptance Builder changes stay in ANY-26).

## Verification

`quick-check`, `validate-architecture`, `validate-docs`, `postgresql-check`.
