# client_update_writer.reply_draft_compose_reply.v1

Draft a single ready-to-send reply to the client's `situation` (the incoming message being
answered), written to accomplish `intent` in the requested `tone`.

Rules:

- `text` must be a complete, self-contained reply the caller can send as-is — do not include
  placeholders such as `[Client Name]`, meta-commentary about the reply, or chain-of-thought.
- Directly address the specific points raised in `situation` — do not write a generic reply that
  could apply to any message.
- Write in the `constraints.language` locale when provided (for example `en` or `en-US`); default
  to the language `situation` is written in otherwise.
- If `constraints.max_length` is set, `text` must not exceed that many characters.
- If `constraints.output_format` is `markdown` or `html`, format `text` accordingly; if it is
  `plain_text` or omitted, `text` must contain no markup.
- Only include `call_to_action` when the reply benefits from a short, explicit next step beyond
  what is already stated in `text`. Omit it when `text` already makes the requested action clear
  on its own.
- Do not include chain-of-thought or explanations outside the schema fields.
