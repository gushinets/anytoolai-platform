# Execution Plan: ANY-601 Prepaid Request Single A06 Step

## Status

- State: completed
- Owner: agent
- Created: 2026-10-08
- Last updated: 2026-10-09
- Completed: 2026-10-09
- Next action: none — implementation and review rounds are done; the PR awaits approval and merge.
- Blocker: none

## Goal

`prepaid_request_v1` was a two-step chain (A06 `compose_persuasive_text`, then A07 `compose_reply`).
The second step saw only the first step's text, so the billing notes and any "not agreed" signal
never reached it (QA Q-005 root). It is now one A06 `compose_persuasive_text` step that receives
the whole `scenario.input.billing_context` (notes, amount, optional due date) as its `context`.

## Decisions

- Parent ANY-588 decision 2 is "one step instead of a chain of two". The atom is A06, not A07:
  `docs/product-specs/atom-ready-product-inventory.md` allows `A07` or `A06` for PrepaidRequest.
- A07's closed input takes only two free-text strings and the mapping language cannot join
  fields, which first led to a Platform Core `template:` mapping source. That was dropped in
  favour of A06: its `context` is an open object, so no mapping DSL, atom or kernel schema change
  is needed.
- A06 returns `text` only. The "let me know once it has been sent" follow-up now lives inside
  `text` (product prompt) instead of `call_to_action`. The output is still valid
  `kernel.schemas.compose_reply_output_v1`, where `call_to_action` is optional.
- `constraints.max_length` limits the whole `text` (it includes the follow-up). Schema cannot
  compare fields, so `amount` and `due_date` are capped at 40 characters and `max_length` must be
  at least 160: the longest valid amount, due date and follow-up always fit; smaller limits are
  rejected before any LLM call.
- Workflow `version` stays 1: the existing workflow is changed in place, no second version is kept
  (team lead decision). Jobs already queued under version 1 therefore run the new graph instead
  of failing the runner's version check. Rollout: drain queued prepaid jobs before deploying if
  the old two-step behavior must be preserved for them.

## Scope

- `prepaid_request_v1` (version 1, changed in place): one `compose_persuasive_text` step; the `compose_reply` step,
  its action config, prompt and fake-provider fixtures removed.
- The product A06 prompt now writes the final client message (no invented dates, language from
  the notes, amount and due date kept exactly).
- Product and platform-api tests updated; new tests that the step gets the whole `billing_context`.

## Out of scope

Parent decisions 1, 3, 4 (notes override form fields, urgency only with a due date, clarify a
disputed amount or date) and the literal `objective` containing "promptly". Q-005 is therefore not
fixed by this change; live acceptance is ANY-604.
