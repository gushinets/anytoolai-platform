# brief_decoder.extract_brief.v1

Extract the structured facts of a client brief from `source_text` according to the `fields`
specification in the input payload. The brief is written by a client for a freelancer; report only
what the brief itself states.

Rules:

- Each requested field must either have a correctly typed value in `values`, keyed by the field's
  `name`, or be omitted from `values` and have its `name` listed in `missing_fields` instead. Never
  guess or fabricate a value: a brief that does not state a budget has no `budget`, and a
  placeholder such as "TBD" or "unknown" is not an extracted value. An empty string is not an
  extracted value either -- if you find nothing for a text field, omit it and list it in
  `missing_fields`, the same as if it were never mentioned.
- Copy `deadline` and `budget` the way the brief words them (for example "end of Q3", "around
  $2k"); do not normalize or convert them.
- List `deliverables` and `constraints` as separate short items, one per array entry. An empty
  list is not an extracted value: if the brief states none, omit the field and list it in
  `missing_fields` instead of returning `[]`.
- `strict` is `false`: a vague brief is a valid, successful result -- return what you can find and
  report the rest as missing.
- Only include a `confidence` entry for a field you populated, as a number between 0 and 1.
- Do not include chain-of-thought or explanations -- return only the JSON fields defined by the
  output schema.
