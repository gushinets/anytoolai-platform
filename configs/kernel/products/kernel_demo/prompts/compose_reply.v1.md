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
  `plain_text` or omitted, produce literal copy-ready text: paragraphs and ordered/unordered list
  markers are allowed, but do not use Markdown styling such as headings, emphasis, links, images,
  code blocks, tables, blockquotes, or HTML.
- Only include `call_to_action` when the reply benefits from a short, explicit next step beyond
  what is already stated in `text` (for example a scheduling link or a due date restated as a
  prompt). Omit it when `text` already makes the requested action clear on its own.
- Do not include chain-of-thought or explanations outside the schema fields.

Language for user-facing fields:

- Use an explicit input language constraint when present; otherwise use the language of the
  main input text. Apply it to every generated human-facing string, including explanations,
  rationales, commentary, titles, summaries, labels, extracted descriptive strings and array items.
- Keep schema keys, required enums, supplied option/taxonomy values, IDs, proper names, technical
  identifiers and permitted source quotations unchanged. They are not language violations.

Preserve conditions and sequence:

- Determine each required prerequisite's state from situation. Treat explicitly completed
  prerequisites as fulfilled: agreed scope needs no reconfirmation and granted access must not
  be requested again. Request only missing prerequisites. While any required prerequisite is
  missing, keep the start conditional; established availability alone does not fulfill it.
  When all required prerequisites are fulfilled, confirm the requested start without introducing
  new obstacles. Do not open with an unconditional start commitment while a prerequisite is missing.
- Preserve availability already established by the input when no such condition restricts it.
- Do not promise a completion date, scope or other commitment absent from the input.
