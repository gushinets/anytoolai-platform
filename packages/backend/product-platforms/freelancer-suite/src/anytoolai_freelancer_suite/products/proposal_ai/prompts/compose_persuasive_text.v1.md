# proposal_ai.compose_persuasive_text.v1

Compose a single persuasive `text` that pursues `objective`: a freelance proposal built only from
facts stated in `context.task_text` (what the client needs) and `context.freelancer_positioning`
(why this freelancer fits), tailored to the task. Do not invent facts, experience, or claims not
present in `context.task_text` or `context.freelancer_positioning`.

`context` may also carry a `tone` and/or `language` key -- ignore them; the already-resolved
`constraints.tone`/`constraints.language` below are what govern tone and language, not `context`.

Rules:

- `text` must be a complete, copy-ready proposal the freelancer can send as-is -- no placeholders,
  meta-commentary about the text, or chain-of-thought.
- Ground every claim in `context.task_text` and `context.freelancer_positioning`; when the task or
  positioning is vague, write a bounded, honest proposal rather than inventing specifics.
- Match `constraints.tone` (`neutral`, `warm`, or `firm`) when provided; otherwise default to a
  warm, professional tone.
- Write in the `constraints.language` locale when provided (for example `en` or `en-US`);
  otherwise default to English (`en`).
- If `constraints.length` is set, `text` must not exceed that many characters.
- If `constraints.format` is `markdown` or `html`, format `text` accordingly; if it is
  `plain_text` or omitted, `text` must contain no markup.
- Do not include chain-of-thought or explanations outside the schema fields.
