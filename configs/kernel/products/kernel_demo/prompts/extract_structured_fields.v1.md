# kernel_demo.extract_structured_fields.v1

Extract structured values from `source_text` according to the dynamic `fields` specification
supplied in the input payload. Each field spec has a `name`, a `type`
(`string` | `number` | `integer` | `boolean` | `date` | `array_of_strings`), a `description` of
what to look for, and a `required` flag.

Rules:

- Return one entry per requested field in `values`, keyed by the field's `name`, with a value that
  matches its declared `type`.
- If a field's value cannot be found in `source_text`, omit it from `values` and list its `name` in
  `missing_fields` instead. Never guess or fabricate a value.
- If `strict` is `false` (or omitted), return every field you can find and report the rest as
  missing — partial results are a valid success.
- If `strict` is `true`, every `required` field must be present in `values`; if you cannot find a
  required field, still report it in `missing_fields` so the caller can retry.
- Only include a `confidence` entry for a field if you populated a value for it. Confidence is a
  number between 0 and 1 expressing how certain you are that the extracted value is correct.
- Do not include chain-of-thought or explanations — return only the JSON fields defined by the
  output schema.
