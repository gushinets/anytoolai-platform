# client_update_writer.prepaid_request_compose_reply.v1

Turn the persuasive framing in `situation` into a single ready-to-send prepayment request that
accomplishes `intent` in the requested `tone`.

Rules:

- `text` must be a complete, self-contained message the caller can send as-is — do not include
  placeholders such as `[Client Name]`, meta-commentary about the message, or chain-of-thought.
- State the request plainly: what the payment is for, building on the persuasive framing in
  `situation` without repeating it verbatim. Do not assert a causal or gating claim (for example
  that work will stall or continue on schedule) beyond what `situation` itself states. Preserve
  every concrete fact `situation` states (amount, due date) exactly as stated — do not tighten a
  due date to an earlier one (for example writing "before Friday" when `situation` says "by
  Friday") — `situation` is the only place those facts appear, so `text` is the client's only
  chance to see them.
- Write in the `constraints.language` locale when provided (for example `en` or `en-US`); default
  to the language `situation` is written in otherwise.
- If `constraints.max_length` is set, `text` must not exceed that many characters.
- If `constraints.output_format` is `markdown` or `html`, format `text` accordingly; if it is
  `plain_text` or omitted, `text` must contain no markup.
- Always include `call_to_action` naming the concrete next step (send payment, confirm receipt),
  restating the amount from `situation` when `situation` states one.
- Do not include chain-of-thought or explanations outside the schema fields.
