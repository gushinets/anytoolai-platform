# kernel_demo.score_match_by_rubric.v1

Score how well `text_b` matches `text_a` against the caller-supplied `rubric` (each item has
`id`, `description`, and `weight`). Return:

- `criterion_scores`: exactly one entry per `rubric` item, each with:
  - `criterion_id`: the matching rubric item's `id`, unchanged.
  - `score`: 0-100, how well `text_b` satisfies that criterion relative to `text_a`.
  - `rationale`: a concise justification tied to the two texts. State the conclusion and the
    evidence directly — do not narrate step-by-step reasoning, alternatives considered, or any
    other chain-of-thought.
- `score`: the aggregate, computed as the rubric-weight-weighted average of the
  `criterion_scores` — `sum(weight_i * score_i) / sum(weight_i)` — rounded to the nearest whole
  number.
- `strengths`: concrete, non-empty statements of where `text_b` matches `text_a` well. Use an
  empty array if there is nothing notable to report.
- `gaps`: concrete, non-empty statements of where `text_b` falls short of `text_a`. Use an empty
  array if there is nothing notable to report.

Do not invent rubric criteria beyond the ones given, and do not include chain-of-thought or
explanations outside the schema fields.
