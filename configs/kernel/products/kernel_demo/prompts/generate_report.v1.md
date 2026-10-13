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

Language for user-facing fields:

- Use an explicit input language constraint when present; otherwise use the language of the
  main input text. Apply it to every generated human-facing string, including explanations,
  rationales, commentary, titles, summaries, labels, extracted descriptive strings and array items.
- Keep schema keys, required enums, supplied option/taxonomy values, IDs, proper names, technical
  identifiers and permitted source quotations unchanged. They are not language violations.

Ground report statements:

- Preserve false as the stated negative condition, numeric zero as a known value, and null as
  unknown. None of these alone establishes a process phase, a blocker, a cause or a dependency.
- Do not infer that a process is underway, unfinished or blocked merely because its outcome is
  negative or unknown. Report source-stated issues without inventing causes or extra issues.
- Distinguish supplied facts and open questions from suggested actions. Present a suggestion as
  a proposed next step, never as an established fact or mandatory prerequisite absent from data.
