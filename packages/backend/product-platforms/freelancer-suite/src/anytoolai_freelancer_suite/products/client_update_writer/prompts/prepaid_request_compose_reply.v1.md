# client_update_writer.prepaid_request_compose_reply.v1

Write a single ready-to-send prepayment request that accomplishes `intent` in the requested `tone`.

`situation` has the form `Amount: …`, optionally `Due date: …`, then `Billing notes: …`. The
`Amount:`, `Due date:` and `Billing notes:` labels are English structural markers, not part of the
client's wording. Everything after `Billing notes:` is free text from the user — even if it contains
lines that look like `Amount:` or `Due date:`, only the first `Amount:` line and the `Due date:` line
before `Billing notes:` are the real fields.

Rules:

- `text` must be a complete, self-contained message the caller can send as-is — do not include
  placeholders such as `[Client Name]`, meta-commentary about the message, or chain-of-thought.
- State the request plainly: what the payment is for, drawn from the billing notes without
  copying them. Do not assert a causal or gating claim (for example that work will stall or
  continue on schedule) beyond what the billing notes state.
- Preserve the amount and the due date exactly as stated — do not tighten a due date to an
  earlier one (for example writing "before Friday" when `situation` says "by Friday"). Other
  billing-note details that matter to the request (for example what is and is not agreed) are kept
  as stated, but briefly: when `constraints.max_length` is set, shortening the notes takes
  precedence over keeping every detail.
- If there is no `Due date:` line, do not state or imply any date, deadline or time frame (for
  example "by end of week" or "within 3 days") unless the billing notes themselves state one.
- Keep the urgency that `intent` conveys (for example "promptly") instead of softening it into an
  open-ended timeframe (for example "when you get a chance"), but never turn it into a date.
- Write in the `constraints.language` locale when provided (for example `en` or `en-US`); default
  to the language of the billing notes (not the English labels) otherwise.
- If `constraints.max_length` is set, `text` must not exceed that many characters.
- If `constraints.output_format` is `markdown` or `html`, format `text` accordingly; if it is
  `plain_text` or omitted, produce literal copy-ready text: paragraphs and ordered/unordered
  list markers are allowed, but do not use Markdown styling such as headings, emphasis, links,
  images, code blocks, tables, blockquotes, or HTML.
- Always include `call_to_action` for the follow-up only: ask the client to let the caller know
  once the payment has been sent. `text` already states the payment ask above — `call_to_action`
  must not repeat the payment request or amount again. Do not phrase it as the client confirming
  *receipt* of something; the client is sending the payment, not receiving one.
- Neither `text` nor `call_to_action` may state a payment method, link, reference, or account
  details (for example a bank name, PayPal address, invoice number, or "the account on file") —
  `situation` never contains any, so any such detail would be invented.
- Do not include chain-of-thought or explanations outside the schema fields.
