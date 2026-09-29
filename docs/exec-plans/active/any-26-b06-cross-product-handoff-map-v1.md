# Execution Plan: ANY-26 Cross-Product Handoff Map V1

## Status

- State: active
- Owner: agent
- Created: 2026-09-29
- Last updated: 2026-09-29
- Review date: 2026-10-06
- Next action: run the full validation set, open the PR, address review.
- Blocker: none

## Goal

Declare Brief Decoder -> Acceptance Builder as a `handoffs.yaml` route over the existing Platform
Core handoff contract ("create draft", not final approval). No Platform Core, web, or consent-page
changes.

## Decisions

- Only route implemented: Task Finder, Send-Ready and Scope Guard products do not exist, so the
  three optional routes are out of scope (not rejected on merit).
- `context_mapping` sends `brief_text`, the caller's original brief. The decode workflow passes
  `scenario.input.brief_text` through verbatim into its output (schema identical to the decode
  input's and the target's `brief_text`, pinned by a test), so a valid decode never fails handoff
  creation and the target extracts from the real brief, not the readiness summary. This needed one
  small Platform Core change: `output_mapping` may now source `scenario.input.*`
  (`docs/architecture/workflow-model.md`). Not a handoff-contract change.
- Preview maps only `document.summary` and `brief.missing_fields` (no literals).
- Acceptance Builder gets no structured handoff input scenario.
- `brief_text` is excluded from the renderer contract: it is a handoff source, never rendered.

## Verification

`validate-configs`, `validate-architecture`, `quick-check`, `full-check`, `validate-docs`.
