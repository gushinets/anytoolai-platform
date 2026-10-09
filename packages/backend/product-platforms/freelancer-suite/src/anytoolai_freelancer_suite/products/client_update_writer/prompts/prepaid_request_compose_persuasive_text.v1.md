# client_update_writer.prepaid_request_compose_persuasive_text.v1

Write the final, ready-to-send prepayment request that accomplishes `objective`, built only from
facts stated in `context`: `context.notes` (what the payment covers), `context.amount` and — when
given — `context.due_date`. Do not invent facts that are not there.

Rules:

- `text` must be a complete, self-contained message the caller can send as-is — do not include
  placeholders such as `[Client Name]`, meta-commentary about the message, or chain-of-thought.
- Ground the request in what `context.notes` states (what the payment covers). Do not invent a
  reason the payment is urgent, gating, or blocking (for example that other work will stall
  without it) beyond what `notes` itself says.
- State `context.amount` exactly as given. When `context.due_date` is given, state it exactly too —
  do not tighten it to an earlier date (for example writing "before Friday" when the due date is
  "Friday"; use "by Friday" or "due Friday").
- If `context` has no `due_date`, do not state or imply any date, deadline or time frame (for
  example "by end of week" or "within 3 days") unless `context.notes` itself states one. Keep the
  urgency of `objective` ("promptly") without turning it into a date, and do not soften it into an
  open-ended timeframe (for example "when you get a chance").
- Other billing-note details that matter to the request (for example what is and is not agreed)
  are kept as stated, but briefly: when `constraints.length` is set, shortening the notes takes
  precedence over keeping every detail.
- End the message by asking the client to let the caller know once the payment has been sent. Do
  not phrase it as the client confirming *receipt* of something; the client is sending the
  payment, not receiving one.
- Do not state a payment method, link, reference, or account details (for example a bank name,
  PayPal address, invoice number, or "the account on file") — `context` never contains any, so any
  such detail would be invented.
- Match `constraints.tone` (`neutral`, `warm`, or `firm`) when provided.
- Write in the `constraints.language` locale when provided (for example `en` or `en-US`); default
  to the language of `context.notes` otherwise.
- If `constraints.length` is set, `text` must not exceed that many characters.
- If `constraints.format` is `markdown` or `html`, format `text` accordingly; if it is
  `plain_text` or omitted, produce literal copy-ready text: paragraphs and ordered/unordered list
  markers are allowed, but do not use Markdown styling such as headings, emphasis, links, images,
  code blocks, tables, blockquotes, or HTML.
- Do not include chain-of-thought or explanations outside the schema fields.
