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

- The prompt decides the kind of message in three steps, so a new case is a bullet, not a new
  branch with its own priority clause (review rounds 1-10 kept finding pairwise priority gaps
  between enumerated branches):
  1. Attribution: only facts about this payment count. Totals, balances, later instalments and
     their dates, currencies named for other amounts, penalties are never a conflict. Unclear
     attribution makes the condition open.
  2. One definition of an open condition (amount, currency, deposit terms, due date, method,
     schedule): said not agreed / disputed / awaiting confirmation / no demand until confirmed;
     a different current amount (including one the notes' own terms compute, e.g. 50% of an agreed
     total) or date for this payment in the notes, even without the word
     "mismatch" (a superseded proposal is history, not a conflict);
     a placeholder `amount` or given `due_date` ("TBD"), or one that names no single value
     (alternatives like "USD 500 or EUR 460", a range); `amount` with no currency tied to this
     payment; partial payment with no stated remainder or with received + remainder not adding up to
     `amount`; the stated due date of the remainder of this amount differs from `due_date`. Never open by themselves: missing
     `due_date`, details to come in a separate invoice, balance after delivery, "go gently".
  3. Ordered rules, first match wins, only D may ask for payment: A currently received in full (not reversed)
     or cancelled → settled acknowledgment (wins over an obsolete open condition, but not over a live dispute of the received amount; a reversal or
     unclear status is an open condition instead); B open condition → terms
     confirmation (only the open points, nothing presented as agreed, no placeholder printed); C "do not ask yet" → hold-off
     acknowledgment; D otherwise → payment request for the amount still due (stated remainder, else
     `amount`).
- The criteria live in the prompt only; `objective` stays neutral.
- If `constraints.length` is too short, no value is named: the client is asked to confirm only the
  conditions that are actually open.
- Billing notes take precedence over `amount` / `due_date`.
- The A06 output is just `text` (no `call_to_action`), so the closing line of each kind lives in
  `text`; the decision is the model's, so there is no structural flag.

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
