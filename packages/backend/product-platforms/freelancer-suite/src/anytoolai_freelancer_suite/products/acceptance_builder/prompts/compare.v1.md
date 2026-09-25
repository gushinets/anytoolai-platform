# acceptance_builder.compare.v1

Judge whether the delivered work in `subject_text` meets the expectations set by the client brief
in `reference_text`. Classify the outcome into exactly one of `categories` and judge every entry
of `criteria`; both come from the input payload.

Rules:

- `verdict` is one of `categories`, verbatim. Use `meets_expectations` only when no criterion is a
  `mismatch`; use `does_not_meet` only when the deliverable fails the brief on the criteria that
  matter most, which requires at least one criterion to be a `mismatch`; otherwise use
  `partially_meets`.
- `deltas` has exactly one entry per `criteria` id, in the order given, with `criterion_id`
  copied verbatim, `status` one of `match`, `partial`, `mismatch`, and `evidence` quoting or
  closely paraphrasing what `subject_text` and `reference_text` say. Evidence comes from those
  two texts only; never invent facts about the delivery.
- A deliverable text that says too little to judge a criterion is a `mismatch` on it, with
  evidence saying what is missing -- not a `match` by default.
- `confidence` is a number between 0 and 1: lower it when the deliverable text is short or vague.
- `rationale` is at most 500 characters and explains the verdict in plain sentences.
- Do not include chain-of-thought -- return only the JSON fields defined by the output schema.
