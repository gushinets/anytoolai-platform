# kernel_demo.extract_structured_fields.v1

Extract structured values from `source_text` according to the dynamic `fields` specification
supplied in the input payload. Each field spec has a `name`, a `type`
(`string` | `number` | `integer` | `boolean` | `date` | `array_of_strings`), a `description` of
what to look for, and a `required` flag.

Rules:

- A `date` value must be a concrete ISO calendar date in `YYYY-MM-DD` format. Resolve
  a partial/relative date only when source_text supplies enough information, or an explicitly
  authorized reference context supplies the missing components. Prompt examples, the system/current
  date and general assumptions are not authorized reference context. Never supply an unstated year.
  Otherwise omit the field from values and list it in missing_fields; omit its confidence entry.
- Preserve genuinely observed numeric zero and boolean false as extracted values. Missing data
  is neither zero nor false; do not replace either observed value with missing/null.

- Each requested field must either have a correctly typed extracted value in `values`, keyed by
  the field's `name`, or be omitted from `values` and have its `name` listed in `missing_fields`
  instead. Never guess or fabricate a value — a fabricated placeholder (an empty string, a zero, a
  made-up date) is not an extracted value, even if it happens to match the declared `type`.
- If `strict` is `false` (or omitted), return every field you can find and report the rest as
  missing — partial results are a valid success.
- If `strict` is `true`, every `required` field must be present in `values`; if you cannot find a
  required field, still report it in `missing_fields` so the caller can retry.
- Only include a `confidence` entry for a field if you populated a value for it. Confidence is a
  number between 0 and 1 expressing how certain you are that the extracted value is correct.
- Do not include chain-of-thought or explanations — return only the JSON fields defined by the
  output schema.

Language for user-facing fields:

- Use an explicit input language constraint when present; otherwise use the language of the
  main input text. Apply it to every generated human-facing string, including explanations,
  rationales, commentary, titles, summaries, labels, extracted descriptive strings and array items.
- Keep schema keys, required enums, supplied option/taxonomy values, IDs, proper names, technical
  identifiers and permitted source quotations unchanged. They are not language violations.
