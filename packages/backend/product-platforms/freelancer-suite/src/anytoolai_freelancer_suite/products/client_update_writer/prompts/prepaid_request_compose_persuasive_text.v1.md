# client_update_writer.prepaid_request_compose_persuasive_text.v1

Compose a single persuasive `text` that pursues `objective` (getting the client to send the
requested prepayment promptly), built only from facts stated in `context` (the billing notes,
amount, and — when given — due date; do not invent facts not present there).

Rules:

- `text` must be ready-to-use persuasive framing the caller can fold into a payment request — do
  not include placeholders, meta-commentary about the text, or chain-of-thought.
- Ground the persuasive angle in exactly what `context.notes` states (what the payment covers) —
  do not invent a reason the payment is urgent, gating, or blocking (for example that other work
  will stall without it) beyond what `notes` itself says.
- State the payment amount and, when `context` includes a due date, the due date explicitly — this
  is the only step in the workflow that sees `context`, so omitting either here means it never
  reaches the client at all. Do not state or imply a payment amount or due date beyond exactly what
  `context` provides — in particular, do not tighten a due date to an earlier one (for example
  writing "before Friday" when `context` says the due date is "Friday"; use "by Friday" or "due
  Friday" instead) — and do not state a payment method, link, reference, or account details (none
  are available at this step; do not invent any).
- Match `constraints.tone` (`neutral`, `warm`, or `firm`) when provided.
- Write in the `constraints.language` locale when provided (for example `en` or `en-US`); default
  to the language `context` is written in otherwise.
- If `constraints.length` is set, `text` must not exceed that many characters.
- If `constraints.format` is `markdown` or `html`, format `text` accordingly; if it is
  `plain_text` or omitted, produce literal copy-ready text: paragraphs and ordered/unordered list
  markers are allowed, but do not use Markdown styling such as headings, emphasis, links, images,
  code blocks, tables, blockquotes, or HTML.
- Do not include chain-of-thought or explanations outside the schema fields.
