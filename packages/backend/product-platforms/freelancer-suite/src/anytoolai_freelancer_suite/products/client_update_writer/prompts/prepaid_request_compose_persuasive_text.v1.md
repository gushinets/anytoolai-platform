# client_update_writer.prepaid_request_compose_persuasive_text.v1

Compose a single persuasive `text` that pursues `objective` (getting the client to send the
requested prepayment promptly), built only from facts stated in `context` (the billing notes,
amount, and — when given — due date; do not invent facts not present there).

Rules:

- `text` must be ready-to-use persuasive framing the caller can fold into a payment request — do
  not include placeholders, meta-commentary about the text, or chain-of-thought.
- Ground the persuasive angle in the concrete project context given (what the payment covers, why
  it is needed now) rather than generic urgency language.
- State the payment amount and, when `context` includes a due date, the due date explicitly — this
  is the only step in the workflow that sees `context`, so omitting either here means it never
  reaches the client at all. Do not state or imply a payment amount or due date beyond exactly what
  `context` provides, and do not state a payment method (that is a later step's concern).
- Match `constraints.tone` (`neutral`, `warm`, or `firm`) when provided.
- Do not include chain-of-thought or explanations outside the schema fields.
