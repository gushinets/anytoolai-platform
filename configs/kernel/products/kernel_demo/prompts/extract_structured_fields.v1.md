# kernel_demo.extract_structured_fields.v1

Extract structured values from `source_text` according to the dynamic `fields` specification
supplied in the input payload. Each field spec has a `name`, a `type`
(`string` | `number` | `integer` | `boolean` | `date` | `array_of_strings`), a `description` of
what to look for, and a `required` flag.

Rules:

- A `date` field's value must be a calendar date string in ISO 8601 `YYYY-MM-DD` format (for
  example `2026-08-07`). If `source_text` only implies a relative or partial date (such as "next
  Friday" or "August"), resolve it to a concrete `YYYY-MM-DD` date using the surrounding context;
  if you cannot resolve a concrete calendar date, treat the field as not found and omit it from
  `values` per the missing-field rule below.

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
- `notes`: one or two plain-language sentences summarizing what was found and what was not — for
  example which fields were populated and which were reported missing. This is read by a
  downstream step, not the end user, so keep it factual and free of chain-of-thought.
- Do not include chain-of-thought or explanations — return only the JSON fields defined by the
  output schema.
