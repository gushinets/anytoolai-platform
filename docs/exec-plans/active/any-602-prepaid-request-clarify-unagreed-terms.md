# Execution Plan: ANY-602 Prepaid Request Clarifies Unagreed Terms

## Status

- State: active
- Owner: agent
- Created: 2026-10-08
- Last updated: 2026-10-08
- Review date: 2026-10-15
- Next action: round-1 code-review fixes applied; run full-check, then open the PR after ANY-601 is merged.
- Blocker: stacked on ANY-601 (not yet in `main`); merge after it.

## Goal

QA Q-005: when the billing notes say the amount, due date or another payment parameter is not
agreed, disputed, or contradicts the form fields, the result asks the client to pay. Now the
`prepaid_request_compose_reply.v1` prompt picks between a payment request and a terms
confirmation, and the `intent` literal no longer asks for payment unconditionally.

## Scenarios

- Disputed: notes say the fee and deposit differ from the form's `USD 1,200`, the client has not
  accepted, payment is wanted after delivery rather than by the form's date, and no payment demand
  may go out before the terms are confirmed. Expected: a terms confirmation naming the open points;
  no payment ask, no "pay X by Y", no "tell me once paid".
- Agreed, no due date: agreed total, 50% prepayment, balance after delivery, payment details in a
  separate invoice, due date empty. Expected: a payment request with amount and agreed terms and
  no invented deadline.
- Unspecified currency: `Amount: 500`, notes say the currency still needs clarifying. Expected: a
  question about the currency before any payment.

## Decisions

- Default is a payment request; only an explicit signal in the notes (or a placeholder amount)
  switches to a terms confirmation. The criteria live in the prompt only; `intent` stays neutral.
- Billing notes take precedence over `Amount` / `Due date`.
- One disputed amount, date or parameter makes the whole message a terms confirmation.
- Missing due date, payment details to come and balance after delivery never trigger a confirmation.
- A07 output schema is closed; the decision is the model's, so there is no structural flag.

## Out of scope

- Urgency only when a deadline exists ("as soon as possible" in A01/A03) — "promptly" stays in
  the agreed-terms branch, so Q-005 is not fully closed by this ticket.
- Lost details (balance, payment details, addressee name), schema/DSL/UI changes.
- Live acceptance A04 x3 / A01 x3 (ANY-604); prompt iteration may follow it.
