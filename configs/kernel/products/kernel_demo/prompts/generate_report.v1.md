# kernel_demo.generate_report.v1

Generate a structured document from the `data` provided for `template_ref`, in the requested
`style` (`professional`, `concise`, or `detailed`; default `professional` when omitted).

`data` for this template contains `source_text` (the original text), `extracted` (structured
fields already pulled from it), `issues` (issues already detected in it), and `questions`
(clarifying questions already generated for it, when present). Turn these into a small set of
ordered `sections` that together read as a coherent report — do not just restate the inputs
verbatim.

Rules:

- Each section needs a stable `id` (a short slug, e.g. `overview`, `key-facts`, `risks`), a
  non-empty `title`, and non-empty `content` written in full sentences.
- Order `sections` the way a reader should encounter them (for example: overview, then key facts,
  then risks/open issues).
- Set `metadata.kind` on a section only when it clarifies how to render it (`heading`,
  `paragraph`, `list`, `table`, or `note`); omit `metadata` when the default paragraph rendering
  is fine.
- `summary` is a single short paragraph capturing the report's bottom line; it is not a list of
  the section titles.
- Do not include chain-of-thought, meta-commentary about the generation process, or word counts —
  return only the `sections` and `summary` fields.
