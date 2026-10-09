# Execution Plan: ANY-602 Prepaid Request Clarifies Unagreed Terms

## Status

- State: completed
- Owner: agent
- Created: 2026-10-08
- Last updated: 2026-10-08
- Completed: 2026-10-08
- Note: stacked on ANY-601 (#166); merge after it. Live acceptance stays in ANY-604.

## Goal

QA Q-005: when the billing notes say the amount, due date or another payment parameter is not
agreed, disputed, or contradicts the form fields, the result asks the client to pay. Now the
`prepaid_request_compose_persuasive_text.v1` prompt (the single A06 step since ANY-601) picks between a payment request and a terms
confirmation, and the `objective` literal no longer asks for payment unconditionally.

## Scenarios

- Disputed: notes say the fee and deposit differ from the form's `USD 1,200`, the client has not
  accepted, payment is wanted after delivery rather than by the form's date, and no payment demand
  may go out before the terms are confirmed. Expected: a terms confirmation naming the open points;
  no payment ask, no "pay X by Y", no "tell me once paid".
- Agreed, no due date: agreed total, 50% prepayment, balance after delivery, payment details in a
  separate invoice, due date empty. Expected: a payment request with amount and agreed terms and
  no invented deadline.
- Unspecified currency: `amount: 500`, notes say the currency still needs clarifying. Expected: a
  question about the currency before any payment.

## Decisions

- Default is a payment request. It switches to a terms confirmation on: notes that say a term is
  not agreed, disputed or awaiting confirmation (or forbid a payment demand until confirmed); an
  implicit discrepancy, where the notes give an amount or due date that differs from the fields
  even without calling it a mismatch; a placeholder `Amount` ("TBD"); or a bare-number `Amount`
  with no currency that the notes do not state, even when the notes are otherwise silent. The criteria live in the prompt only; `objective` stays neutral.
- Billing notes take precedence over `Amount` / `Due date`.
- One disputed amount, date or parameter makes the whole message a terms confirmation.
- Missing due date, payment details to come and balance after delivery never trigger a confirmation.
- The A06 output is just `text` (no `call_to_action`), so the closing line of each kind lives in `text`; the decision is the model's, so there is no structural flag.

## Builds on ANY-601 (single A06 step)

- A06 gets the whole `billing_context` as `context`, so the prompt reads `context.notes`,
  `context.amount` and `context.due_date` as separate fields. `amount` and `due_date` are
  single-line and at most 40 characters, so they cannot fake a structural marker.
- A06 returns `text` only: the closing line of each message kind is part of `text`, and
  `constraints.length` (at least 160, from ANY-601) limits all of it. In a terms confirmation the
  open points are kept and other detail is dropped first; the limit is never exceeded.
- ANY-602 owns parent decisions 1 and 4 (notes over fields, one open point means a full
  confirmation). ANY-601 left the `objective` literal containing "promptly"; it is now conditional
  on a payment request. Decision 3 (urgency only with a deadline) stays out of scope.

## Out of scope

- Urgency only when a deadline exists ("as soon as possible" in A01/A03) — "promptly" stays in
  the agreed-terms branch, so Q-005 is not fully closed by this ticket.
- Lost details (balance, payment details, addressee name), schema/DSL/UI changes.
- Live acceptance A04 x3 / A01 x3 (ANY-604); prompt iteration may follow it.
