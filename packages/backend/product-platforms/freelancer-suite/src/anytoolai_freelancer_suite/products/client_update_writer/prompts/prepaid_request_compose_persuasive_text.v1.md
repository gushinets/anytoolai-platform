# client_update_writer.prepaid_request_compose_persuasive_text.v1

Write the final, ready-to-send message that accomplishes `objective`, built only from facts stated
in `context`: `context.notes` (what the payment covers), `context.amount` and — when given —
`context.due_date`. Do not invent facts that are not there. Depending on the notes the message is a
prepayment request, a request to confirm the payment terms, a hold-off acknowledgment or a settled
acknowledgment. Decide which first, in three steps.

Step 1. Attribute every fact to this payment or not.

Only facts about *this* payment (the one `context.amount` is for) can agree with, contradict or
settle its terms. A project total, a separate later instalment or balance (one the notes present as its own
payment) and its due date, a currency named only for other amounts, penalties, or any other payment
are facts about something else: they
are never a conflict with `context.amount` / `context.due_date` and never a reason to confirm terms
(for example `amount: USD 500`, `due_date: 15 October` against "deposit USD 500 due 15 October,
remaining USD 1,500 due 30 November" is consistent). What is left of *this* amount after a partial
receipt is part of this payment, not another one: its stated due date is a due date for this
payment (`due_date: 15 October` against "remaining USD 750 due 30 October" is a different due date). When it is unclear whether a fact concerns
this payment, treat the condition it touches as open (Step 2): a question costs less than an
unfounded payment demand.

Step 2. Decide which conditions of this payment are open (not needed when rule A below applies).

`context.notes` take precedence over `context.amount` and `context.due_date`. An essential
condition of this payment (its amount, currency, deposit terms, due date, payment method or
schedule) is open when any of these holds:

- the notes say it is not agreed, disputed, awaiting confirmation or contradicted, or that no
  payment demand may be sent until it is confirmed;
- the notes state a different current amount or due date for this payment than `context.amount` /
  `context.due_date` (an earlier proposal the notes call rejected, superseded or replaced is history,
  not a conflict), or an amount that the notes' own terms determine (for example "50% of an agreed
  total of USD 2,000" is USD 1,000, against `amount: USD 1,200`), even without calling it a mismatch and even if the notes call that value agreed (for example `amount: USD 1,200` against
  "deposit is 50%, USD 1,000"; `due_date: 7 October` against "payment due after delivery on
  20 October");
- `context.amount`, or a given `context.due_date`, is a placeholder such as "TBD" or "to be
  agreed" (an absent `due_date` is not a placeholder);
- `context.amount` names no currency (a bare number, or one with other words such as
  "500 (deposit)") and the notes do not tie a currency to this payment (a currency named only for
  other amounts, or several currencies with none named for this payment, does not count);
- part of this amount was received (and not reversed) and the notes do not state the remaining figure, or the
  received part, the stated remainder and `context.amount` do not add up (for example
  "500", "200 received", "remaining 400").

Never open by themselves: a missing `due_date`, payment details still to come (for example in a
separate invoice), a balance due after delivery, or a request in the notes to go gently. Notes that
merely describe the payment consistently with the fields, without saying anything about agreement,
open nothing.

Step 3. Pick the kind of message: the first matching rule wins.

Only rule D may ask for payment. Rules A–C never ask the client to pay or remit, never turn
`context.amount` or `context.due_date` into an amount or date to pay ("once you confirm, please pay
X by Y" is a payment ask too), and never ask the client to report a payment.

- A. The notes say that, as things stand now, this payment is received in full and stays settled,
  or is cancelled → settled
  acknowledgment, whatever else is open (an obsolete "TBD" included), unless the notes say the received amount or
  its terms are still disputed, or ask for clarification or a refund: a live dispute is an open
  condition (rule B) and wins over the settled status. A payment that was reversed, refunded,
  charged back or whose status is unclear is not settled: its status is an open condition (rule B): a
  short thank-you for the payment, or a note that the request is withdrawn, without restating
  `context.amount` as owed.
- B. Any condition is open → terms confirmation. Ask the client to confirm only the open
  conditions, named as stated or discussed, never as agreed; anything the notes call agreed and
  that conflicts with nothing stays stated as agreed. A value the notes call agreed that differs
  from `context.amount` / `context.due_date` is still an open point: ask the client to confirm it
  without presenting either value as settled or repeating the notes' agreement claim. Asking for the information the terms need (for example which currency applies,
  or the amount still due) is fine. Never print a placeholder as a value: ask the client to confirm
  that amount or due date instead.
- C. The notes say not to ask for payment yet (for example "do not request payment yet, we are
  waiting for the client's review"), whether or not they call the terms agreed → hold-off
  acknowledgment: a short note that you will wait.
- D. Otherwise → payment request for the amount still due: the remaining figure the notes state if
  part was already received, else `context.amount`. Follow a "go gently" note in the wording.

Rules:

- `text` must be a complete, self-contained message the caller can send as-is — do not include
  placeholders such as `[Client Name]`, meta-commentary about the message, or chain-of-thought.
- In a payment request, ground the request in what `context.notes` states (what the payment
  covers). Do not invent a reason the payment is urgent, gating, or blocking (for example that other work will stall
  without it) beyond what `notes` itself says.
- In a payment request (rule D) state the amount still due exactly as given: the stated remaining
  figure after a partial receipt, else `context.amount`, never both. A terms confirmation shows an
  amount or due date only as the stated value of an open point; rules A and C never present an
  amount or due date as owed or upcoming.
- In a payment request, when `context.due_date` is a real, non-placeholder due date or deadline (a
  calendar date or a relative term such as "Net 30 after invoice" or "within 14 days of delivery")
  and the notes give no other due date for the amount still due, state it exactly — do not tighten
  it to an earlier date (for example writing "before Friday" when the due date is "Friday"; use
  "by Friday" or "due Friday"). A placeholder (`TBD`, "to be agreed") is never stated as a value:
  ask the client to confirm that amount or due date instead.
- If `context` has no `due_date`, do not state or imply any date, deadline or time frame (for
  example "by end of week" or "within 3 days") unless `context.notes` itself states one. In a payment request, keep the
  urgency of `objective` ("promptly") without turning it into a date, and do not soften it into an
  open-ended timeframe (for example "when you get a chance").
- Other billing-note details that matter to the request (for example what is and is not agreed)
  are kept as stated, but briefly: when `constraints.length` is set, shortening the notes takes
  precedence over keeping every detail; in a terms confirmation, drop other detail before the open
  points. `text` (including the closing line) never exceeds `constraints.length`. If the limit is too short
  to name every open value, name none of them: ask the client to confirm only the conditions that
  are actually open (or "the unresolved payment terms" if even those labels do not fit), without
  stating or endorsing any value and without raising anything the notes call agreed.
- End the message matching its kind. Payment request (rule D): ask the client to let the caller
  know once the payment has been sent; do not phrase it as the client confirming *receipt* of
  something (the client is sending the payment). Terms confirmation (rule B): end with a short
  request to reply with the confirmation. Rules A–C never ask the client to report a payment.
- Do not state a payment method, link, reference, or account details (for example a bank name,
  PayPal address, invoice number, or "the account on file") unless `context.notes` states it —
  `context.amount` and `context.due_date` never contain any, so any other such detail would be
  invented. Naming an open payment condition (for example "the payment method") is fine.
- Match `constraints.tone` (`neutral`, `warm`, or `firm`) when provided.
- Write in the `constraints.language` locale when provided (for example `en` or `en-US`); default
  to the language of `context.notes` otherwise.
- If `constraints.length` is set, `text` must not exceed that many characters.
- If `constraints.format` is `markdown` or `html`, format `text` accordingly; if it is
  `plain_text` or omitted, produce literal copy-ready text: paragraphs and ordered/unordered list
  markers are allowed, but do not use Markdown styling such as headings, emphasis, links, images,
  code blocks, tables, blockquotes, or HTML.
- Do not include chain-of-thought or explanations outside the schema fields.
