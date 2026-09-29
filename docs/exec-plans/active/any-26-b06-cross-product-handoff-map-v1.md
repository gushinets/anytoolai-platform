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
- `context_mapping` sends `document.summary` as `brief_text`: the only always-present non-empty
  string in the decode output (the raw brief is not stored, `brief.values.*` are optional, and a
  missing mapped path is a hard `HandoffPayloadError`). `decode_output` `document.summary` carries the same `maxLength`/pattern as the target `brief_text`, so a valid decode never fails handoff creation (an over-long summary fails the decode job instead; no truncation). Known v1 limit: the draft may be sparse.
  Enriching the decode output is a separate future ticket.
- Preview maps only `document.summary` and `brief.missing_fields` (no literals).
- Acceptance Builder gets no structured handoff input scenario.

## Verification

`validate-configs`, `validate-architecture`, `quick-check`, `full-check`, `validate-docs`.
