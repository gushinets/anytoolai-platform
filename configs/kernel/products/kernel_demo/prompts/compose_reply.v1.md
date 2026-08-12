# kernel_demo.compose_reply.v1

Compose a single ready-to-use reply for the described `situation`, written to accomplish
`intent` (the action the recipient should take after reading it) in the requested `tone`
(`neutral`, `warm`, or `firm`).

Rules:

- `text` must be a complete, self-contained reply the caller can send as-is — do not include
  placeholders such as `[Name]`, meta-commentary about the reply, or chain-of-thought.
- Write in the `constraints.language` locale when provided (for example `en` or `en-US`); default
  to the language `situation` and `intent` are written in otherwise.
- If `constraints.max_length` is set, `text` must not exceed that many characters.
- If `constraints.output_format` is `markdown` or `html`, format `text` accordingly; if it is
  `plain_text` or omitted, `text` must contain no markup.
- Only include `call_to_action` when the reply benefits from a short, explicit next step beyond
  what is already stated in `text` (for example a scheduling link or a due date restated as a
  prompt). Omit it when `text` already makes the requested action clear on its own.
- Do not include chain-of-thought or explanations outside the schema fields.
