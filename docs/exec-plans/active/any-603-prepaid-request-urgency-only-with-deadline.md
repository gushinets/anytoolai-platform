# Execution Plan: ANY-603 Prepaid Request Urgency Only With a Deadline in the Input

## Status

- State: active
- Owner: agent
- Created: 2026-10-10
- Last updated: 2026-10-10
- Review date: 2026-10-10
- Next action: run checks, open PR after ANY-602 merges; live acceptance in ANY-604.
- Blocker: none

## Goal

Prepaid Request (A06 `compose_persuasive_text`, one step) asked for payment "promptly" even when
the input gave no deadline (QA cases A01, A03). Urgency now needs a basis in the input: a given
`due_date`, or notes that express payment urgency. Otherwise the request is neutral; `firm` tone
is not a basis. The closing line by message kind was done in ANY-602 and is only pinned by a test here.

## Scope

- Prompt urgency rule, `objective` literal without "promptly", neutral weak fixture.
- Tests: objective, fixtures, prompt rules (urgency, closing line by kind).

## Out of scope

Message-kind choice (ANY-602), `call_to_action`/A07, schemas/DSL/UI, live acceptance (ANY-604).

## Risks

Text tests do not prove model behavior; only live runs (ANY-604) do. Stacked on ANY-602: rebase
after it merges.
