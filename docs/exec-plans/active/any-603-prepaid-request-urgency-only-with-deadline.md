# Execution Plan: ANY-603 Prepaid Request Urgency Only With a Deadline in the Input

## Status

- State: active
- Owner: agent
- Created: 2026-10-10
- Last updated: 2026-10-12
- Review date: 2026-10-12
- Next action: merge PR #168 once CI is green; live acceptance in ANY-604.
- Blocker: none

## Goal

Prepaid Request (A06 `compose_persuasive_text`, one step) asked for payment "promptly" even when
the input gave no deadline (QA cases A01, A03). Urgency now needs urgency expressed in the input: in the
notes or in the free text of `due_date` (for example "Friday — ASAP"). A plain date alone is not a
basis. Otherwise the request is neutral; `firm` tone is not a basis. The closing line by message kind was done in ANY-602 and is only pinned by a test here.

## Scope

- Prompt urgency rule, `objective` literal without "promptly", neutral weak fixture.
- Tests: objective, fixtures, prompt rules (urgency, closing line by kind).

## Out of scope

Message-kind choice (ANY-602), `call_to_action`/A07, schemas/DSL/UI, live acceptance (ANY-604).

## Risks

Text tests do not prove model behavior; only live runs (ANY-604) do, including a case with explicit
urgency ("ASAP") to check it is preserved. ANY-602 is already in `main`.
