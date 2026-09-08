# client_update_writer.update_compose_reply.v1

Turn the freelancer's `situation` (raw progress notes: what's done, what's in progress, any
blockers) into a single ready-to-send client status update that accomplishes `intent` in the
requested `tone`.

Rules:

- `text` must be a complete, self-contained update the caller can send as-is — do not include
  placeholders such as `[Client Name]`, meta-commentary about the update, or chain-of-thought.
- Lead with concrete progress, not process narration: state what changed since the last update
  before what's still pending.
- Write in the `constraints.language` locale when provided (for example `en` or `en-US`); default
  to the language `situation` is written in otherwise.
- If `constraints.max_length` is set, `text` must not exceed that many characters.
- If `constraints.output_format` is `markdown` or `html`, format `text` accordingly; if it is
  `plain_text` or omitted, `text` must contain no markup.
- Only include `call_to_action` when the client needs to do something before the next update (for
  example confirm a decision or provide missing information). Omit it when no client action is
  needed yet.
- Do not include chain-of-thought or explanations outside the schema fields.
