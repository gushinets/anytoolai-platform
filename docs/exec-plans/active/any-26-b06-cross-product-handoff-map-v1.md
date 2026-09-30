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
Core handoff contract ("create draft", not final approval). No Platform Core, handoff
runtime/lifecycle, web, or consent-page changes in this ticket: the workflow `output_mapping`
`scenario.input` passthrough it relies on landed separately in ANY-540.

## Decisions

- Only route implemented: Task Finder, Send-Ready and Scope Guard products do not exist, so the
  three optional routes are out of scope (not rejected on merit).
- `context_mapping` sends `brief_text`, the caller's original brief. The decode workflow passes
  `scenario.input.brief_text` through verbatim into its output using the `output_mapping`
  `scenario.input` source added by ANY-540 (schema identical to the decode input's and the
  target's `brief_text`, pinned by a test), so a valid decode never fails handoff creation and the
  target extracts from the real brief, not the readiness summary. The passthrough was split into
  ANY-540 so this ticket's "no mapping DSL extension in mappings" criterion holds without
  interpretation: `handoffs.yaml` uses only the existing `artifact.content_json.*` grammar and
  contains no Core change.
- Preview maps only `document.summary` and `brief.missing_fields` (no literals).
- Acceptance Builder gets no structured handoff input scenario.
- `brief_text` became a required field of the decode workflow output, so `brief_decoder.decode_v1`
  (workflow) and `brief_decoder.decode_output_v1` (schema) are bumped to version 2: the persisted
  `job.workflow_version` / artifact `schema_version` drift guards must tell pre- and post-deploy
  definitions apart. The input schema and the scenario (advertised next actions unchanged) stay at
  version 1.
- `continue_to_target` is not advertised on `brief_decoder.decode_v1`: the target may be disabled
  in a supported deployment, and the actual same-tab web handoff journey (with target
  availability) belongs to ANY-244. The declarative backend route stays here.
- `brief_text` is excluded from the renderer contract: it is a handoff source, never rendered.

## Verification

`validate-configs`, `validate-architecture`, `quick-check`, `full-check`, `validate-docs`.
