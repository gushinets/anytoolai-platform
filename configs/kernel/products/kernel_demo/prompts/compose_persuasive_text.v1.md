# kernel_demo.compose_persuasive_text.v1

Compose a single persuasive `text` that pursues `objective`, built only from facts stated in
`context` (do not invent facts not present there).

Rules:

- `text` must be a complete, ready-to-use piece of persuasive writing the caller can send as-is —
  do not include placeholders, meta-commentary about the text, or chain-of-thought.
- Write for `audience` when provided; otherwise write for the reader implied by `context`.
- Emphasize `angle` when provided as the persuasive angle to lead with.
- Match `constraints.tone` (`neutral`, `warm`, or `firm`) when provided.
- Write in the `constraints.language` locale when provided (for example `en` or `en-US`); default
  to the language `objective` is written in otherwise.
- If `constraints.length` is set, `text` must not exceed that many characters.
- If `constraints.format` is `markdown` or `html`, format `text` accordingly; if it is
  `plain_text` or omitted, `text` must contain no markup.
- Do not include chain-of-thought or explanations outside the schema fields.
