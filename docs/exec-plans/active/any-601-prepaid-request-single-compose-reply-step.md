# Execution Plan: ANY-601 Prepaid Request Single compose_reply Step

## Status

- State: active
- Owner: agent
- Created: 2026-10-08
- Last updated: 2026-10-08
- Review date: 2026-10-15
- Next action: run full-check and the Client Update Writer smoke, then open the PR.
- Blocker: none

## Goal

`prepaid_request_v1` was a two-step chain (`compose_persuasive_text` then `compose_reply`). The
second step saw only the first step's text, so the billing notes and any "not agreed" signal
never reached it (QA Q-005 root). It is now one `compose_reply` step whose `situation` carries
the billing notes, amount and due date.

## Decisions

- Parent ANY-588 decision 2 (one `compose_reply` step instead of a chain of two) is confirmed.
- The mapping language could not join several fields into one string, and kernel schemas are
  closed. Chosen: a small Platform Core `template:` source for `input_mapping`
  (`docs/architecture/workflow-model.md`); an absent `{?path}` placeholder drops its whole line.
  Rejected: building the string in the web client (moves product meaning into the frontend).

## Scope

- `template:` source in `workflows/mappings.py`, with unit tests and architecture docs.
- `prepaid_request_v1` reduced to one step; the persuasive-text step, action config, prompt and
  fake-provider fixtures removed; the compose_reply prompt reworded for the new input.
- Product and platform-api tests updated; new test that the step input holds notes, amount and
  due date.

## Out of scope

Parent decisions 1, 3, 4 (notes override form fields, urgency only with a due date, clarify a
disputed amount or date) and the literal `intent` containing "promptly". Q-005 is therefore not
fixed by this change; live acceptance is ANY-604.
