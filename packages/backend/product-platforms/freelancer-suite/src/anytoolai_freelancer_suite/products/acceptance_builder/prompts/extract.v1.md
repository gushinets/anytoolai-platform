# acceptance_builder.extract.v1

Extract, from `source_text`, the acceptance-related facts of a client brief according to the
`fields` specification in the input payload. The brief is written by a client for a freelancer;
report only what the brief itself states. Extract, do not invent: an acceptance criterion is a
condition the brief already imposes on the finished work, never a plausible one you would add.

Rules:

- Each requested field must either have a non-empty array of strings in `values`, keyed by the
  field's `name`, or be omitted from `values` and have its `name` listed in `missing_fields`
  instead. An empty array is not an extracted value: if the brief states nothing for a field,
  omit it and list it in `missing_fields`. Never guess or fabricate an item.
- `acceptance_criteria`: one short, checkable condition per entry, each traceable to a statement
  in the brief (for example "must work for all existing courses" becomes "The certificate is
  issued for every existing course"). Do not add conditions the brief does not imply.
- `assumptions`: things the brief states as given or assumed. Do not list your own assumptions.
- `deliverables`: the concrete things the client expects to receive, one per entry.
- Entries are plain non-empty sentences or phrases; never placeholders such as "TBD".
- `strict` is `false`: a vague brief is a valid, successful result -- return what you can find and
  report the rest as missing.
- Only include a `confidence` entry for a field you populated, as a number between 0 and 1.
- Do not include chain-of-thought or explanations -- return only the JSON fields defined by the
  output schema.
