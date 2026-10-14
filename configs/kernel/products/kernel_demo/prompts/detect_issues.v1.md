# kernel_demo.detect_issues.v1

Detect risks, gaps, ambiguities, and blockers in `source_text`, using `context` (if provided) to
judge relevance. Return each finding as an entry in `issues` with:

- `category`: a short label for the kind of issue. If `taxonomy` is non-empty, `category` must be
  one of the given taxonomy values; if `taxonomy` is empty or omitted, choose a concise
  product-neutral label yourself.
- `description`: a non-empty, self-contained explanation of the issue.
- `severity`: `low`, `medium`, or `high`.
- `evidence` (optional): a short quote or close paraphrase from `source_text` that supports the
  finding.

If `source_text` contains no issues, return an empty `issues` array — that is a valid, successful
result. Do not include chain-of-thought or explanations outside the schema fields.

Language for user-facing fields:

- Use an explicit input language constraint when present; otherwise use the language of the
  main input text. Apply it to every generated human-facing string, including explanations,
  rationales, commentary, titles, summaries, labels, extracted descriptive strings and array items.
- Keep schema keys, required enums, supplied option/taxonomy values, IDs, proper names, technical
  identifiers and permitted source quotations unchanged. They are not language violations.
