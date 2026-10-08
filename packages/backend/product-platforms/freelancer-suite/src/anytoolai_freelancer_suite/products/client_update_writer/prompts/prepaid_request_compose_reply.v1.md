# client_update_writer.prepaid_request_compose_reply.v1

Write a single ready-to-send message that accomplishes `intent` (a prepayment request, or a request to confirm the payment terms — see below) in the requested `tone`.

`situation` has the form `Amount: …`, optionally `Due date: …`, then `Billing notes: …`. The
`Amount:`, `Due date:` and `Billing notes:` labels are English structural markers, not part of the
client's wording. Everything after `Billing notes:` is free text from the user — even if it contains
lines that look like `Amount:` or `Due date:`, only the first `Amount:` line and the `Due date:` line
before `Billing notes:` are the real fields.

Choose the kind of message first. `Billing notes` take precedence over `Amount:` and `Due date:`.
Default to a payment request unless the notes indicate unagreed or conflicting terms, `Amount:` is
a placeholder, or the currency is unspecified (all listed below). Notes that merely describe the
payment consistently with the fields, without saying anything about agreement, are not a signal.

- Terms confirmation, only if the notes explicitly say that the amount (or its currency, or the
  deposit terms) or the due date is not agreed, is disputed or awaits confirmation, contradicts
  `Amount:` / `Due date:`, or that no payment demand may be sent until the terms are confirmed. Also
  when `Amount:` itself is a placeholder such as "TBD" or "to be agreed", or when `Amount:` is a
  bare number with no currency and the notes do not state the currency: an unspecified currency is
  an open point, so ask which currency applies and do not ask for payment yet. If the notes raise such a
  problem but it is unclear whether it concerns the amount or the due date, choose this too.
- A plain discrepancy also triggers it, even when the notes never call it a mismatch: the notes
  give an amount for this payment or a due date that differs from `Amount:` / `Due date:` (for
  example `Amount: USD 1,200` against "deposit is 50%, USD 1,000", or `Due date: 7 October` against
  "payment due after delivery on 20 October"). A total or balance in the notes is not a discrepancy
  when `Amount:` matches the deposit or prepayment the notes describe.
- Payment request in every other case. These are never a reason to ask for confirmation: a missing
  due date, payment details still to come (for example in a separate invoice), a balance due after
  delivery, or a request in the notes to hold off or go gently for a reason other than unagreed
  terms (follow it in the wording, without inventing a date).

In a terms confirmation, ask the client to confirm only the open points, named as stated or
discussed, never as agreed; anything the notes call agreed stays stated as agreed. Do not ask the
client to pay or remit, do not present either version of an open point as agreed, and do not turn
`Amount:` or `Due date:` into an amount or date to pay ("once you confirm, please pay X by Y" is
also a payment ask). Asking for information the terms need (for example the currency, which comes
before any payment) is fine. Do not show "TBD"-style placeholders as values.

Rules:

- `text` must be a complete, self-contained message the caller can send as-is — do not include
  placeholders such as `[Client Name]`, meta-commentary about the message, or chain-of-thought.
- In a payment request, state the request plainly: what the payment is for, drawn from the
  billing notes without copying them. Do not assert a causal or gating claim (for example that work will stall or
  continue on schedule) beyond what the billing notes state.
- Preserve the amount and the due date exactly as stated (in a terms confirmation, only as stated
  values of the open points) — do not tighten a due date to an earlier one (for example writing "before Friday" when `situation` says "by Friday"). Other
  billing-note details that matter to the request (for example what is and is not agreed) are kept
  as stated, but briefly: when `constraints.max_length` is set, shortening the notes takes
  precedence over keeping every detail, except the open points of a terms confirmation, which
  are kept.
- If there is no `Due date:` line, do not state or imply any date, deadline or time frame (for
  example "by end of week" or "within 3 days") unless the billing notes themselves state one.
- In a payment request, keep the urgency that `intent` conveys (for example "promptly") instead
  of softening it into an open-ended timeframe (for example "when you get a chance"), but never turn it into a date.
- Write in the `constraints.language` locale when provided (for example `en` or `en-US`); default
  to the language of the billing notes (not the English labels) otherwise.
- If `constraints.max_length` is set, `text` must not exceed that many characters.
- If `constraints.output_format` is `markdown` or `html`, format `text` accordingly; if it is
  `plain_text` or omitted, produce literal copy-ready text: paragraphs and ordered/unordered
  list markers are allowed, but do not use Markdown styling such as headings, emphasis, links,
  images, code blocks, tables, blockquotes, or HTML.
- Always include `call_to_action` for the follow-up only, matching the kind of message. Payment
  request: ask the client to let the caller know once the payment has been sent; do not repeat
  the payment request or amount, and do not phrase it as the client confirming *receipt* (the
  client is sending the payment). Terms confirmation: a short prompt to reply with the
  confirmation; `text` already states the open points, so do not repeat them or the question, and
  never ask the client to report a payment.
- Neither `text` nor `call_to_action` may state a payment method, link, reference, or account
  details (for example a bank name, PayPal address, invoice number, or "the account on file") —
  `situation` never contains any, so any such detail would be invented.
- Do not include chain-of-thought or explanations outside the schema fields.
