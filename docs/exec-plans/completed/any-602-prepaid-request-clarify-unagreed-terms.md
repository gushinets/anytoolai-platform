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

- Default is a payment request. Kinds of message, decided by the model from the prompt:
  - Terms confirmation, when the notes say that the amount, currency, deposit terms, due date or
    another essential condition of this payment (for example the payment method) is not agreed,
    disputed or awaiting confirmation, or forbid a payment demand until the terms are confirmed;
    when the notes give an amount or due date that differs from the fields, even without calling it
    a mismatch; when `amount` or a given `due_date` is a placeholder ("TBD", "to be agreed"); or
    when `amount` names no currency (a bare number or e.g. "500 (deposit)") that the notes do not
    state.
  - Hold-off message (a short "we will wait" note, no payment ask), when the notes explicitly say
    not to ask for payment yet for a reason other than unagreed terms, whether or not they call the
    terms agreed; an open term takes priority and gives a terms confirmation.
  - Settled message (a short acknowledgment, no payment ask), when the notes say the amount was
    already received or the payment is cancelled.
  - Payment request otherwise. A real due date, including a relative one ("Net 30 after
    invoice"), is stated exactly; an absent `due_date`, payment details to come in a separate
    invoice, a balance after delivery and a "go gently" note never trigger a confirmation.
- The criteria live in the prompt only; `objective` stays neutral.
- In a terms confirmation only the open points are named, and a placeholder is never printed as a
  value. If `constraints.length` is too short, none of the values is named: the client is asked to
  confirm only the conditions that are actually open.
- Billing notes take precedence over `amount` / `due_date`.
- One open amount, date or parameter makes the whole message a terms confirmation.
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
