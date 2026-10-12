# client_update_writer.prepaid_request_compose_persuasive_text.v1

Write the final, ready-to-send message that accomplishes `objective` (a prepayment request, or a request to confirm the payment terms — see below), built only from
facts stated in `context`: `context.notes` (what the payment covers), `context.amount` and — when
given — `context.due_date`. Do not invent facts that are not there.

Choose the kind of message first. `context.notes` take precedence over `context.amount` and
`context.due_date`. Default to a payment request unless the notes indicate unagreed or conflicting
terms, `context.amount` or a given `context.due_date` is a placeholder, the currency is
unspecified, the notes say not to ask for payment yet, or the payment is already or partly settled (all listed below). Notes that merely
describe the payment consistently with the fields, without saying anything about agreement, are
not a signal.

- Terms confirmation, only if the notes explicitly say that the amount (or its currency, or the
  deposit terms), the due date or any other essential condition of this payment (for example the
  payment method or schedule) is not agreed, is disputed or awaits confirmation, contradicts
  `context.amount` / `context.due_date`, or that no payment demand may be sent until the terms are
  confirmed. Also when `context.amount` or a given `context.due_date` is itself a placeholder such
  as "TBD" or "to be agreed" (an absent `due_date` is not one), or when `context.amount` names no currency (a bare number, or one with other words such as
  "500 (deposit)") and the notes do not tie a currency to this payment (a currency mentioned only for other
  amounts, or several currencies with none named for this payment, does not count): an
  unspecified currency is an open point, so ask which currency applies and do not ask for payment
  yet. If the notes raise such a problem but it is unclear whether it concerns the amount or the
  due date, choose this too.
- A plain discrepancy also triggers it, even when the notes never call it a mismatch: the notes
  give an amount for this payment or a due date that differs from `context.amount` /
  `context.due_date` (for example `amount: USD 1,200` against "deposit is 50%, USD 1,000", or
  `due_date: 7 October` against "payment due after delivery on 20 October"). A total or balance in
  the notes is not a discrepancy when `context.amount` matches the deposit or prepayment the notes
  describe.
- Hold-off message, when the notes explicitly say not to ask for payment yet for a reason other
  than unagreed terms (for example "do not request payment yet, we are waiting for the client's
  review"), whether or not they call the terms agreed. If a term is also open, the terms
  confirmation takes priority. Write a short
  acknowledgment that you will wait, without a payment ask, without turning `context.amount` or
  `context.due_date` into an amount or date to pay, and without asking the client to report a
  payment.
- Settled message, when the notes say this amount has already been received or the payment is
  cancelled: do not ask for payment; write a short note acknowledging that (thanks for the payment,
  or that the request is withdrawn), without restating `context.amount` as owed. An open term still
  takes priority.
- Partly settled, when the notes say part of this amount was already received: never ask for the
  full `context.amount` again. If the notes state the remaining figure, ask for exactly that; if
  not, write a terms confirmation asking the client to confirm the amount still due.
- Payment request in every other case. These are never a reason to ask for confirmation: a missing
  `due_date`, payment details still to come (for example in a separate invoice), a balance due
  after delivery, or a request in the notes to go gently (follow it in the wording, without
  inventing a date).

In a terms confirmation, ask the client to confirm only the open points, named as stated or
discussed, never as agreed; anything the notes call agreed stays stated as agreed. Do not ask the
client to pay or remit, do not present either version of an open point as agreed, and do not turn
`context.amount` or `context.due_date` into an amount or date to pay ("once you confirm, please pay
X by Y" is also a payment ask). Asking for information the terms need (for example the currency,
which comes before any payment) is fine. Do not show "TBD"-style placeholders as values; ask the
client to confirm that amount or due date instead.

Rules:

- `text` must be a complete, self-contained message the caller can send as-is — do not include
  placeholders such as `[Client Name]`, meta-commentary about the message, or chain-of-thought.
- In a payment request, ground the request in what `context.notes` states (what the payment covers). Do not invent a
  reason the payment is urgent, gating, or blocking (for example that other work will stall
  without it) beyond what `notes` itself says.
- State `context.amount` exactly as given (in a terms confirmation, only as the stated value of an
  open point). When `context.due_date` is a real, non-placeholder due date or deadline (a calendar date or a
  relative term such as "Net 30 after invoice" or "within 14 days of delivery"), state it exactly
  too — do not tighten it to an earlier date (for example writing "before Friday" when the due date is "Friday"; use
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
- End the message matching its kind. Payment request: ask the client to let the caller know once the
  payment has been sent; do not phrase it as the client confirming *receipt* of something (the
  client is sending the payment). Terms confirmation: end with a short request to reply with the
  confirmation, and never ask the client to report a payment.
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
