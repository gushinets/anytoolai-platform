# task_finder.score.v1

Score how well the freelancer described in `text_b` fits the task described in `text_a` against
the caller-supplied `rubric` (each item has `id`, `description`, and `weight`). Return:

- `criterion_scores`: exactly one entry per `rubric` item, in the order given, each with:
  - `criterion_id`: the matching rubric item's `id`, unchanged.
  - `score`: 0-100, how well `text_b` satisfies that criterion relative to `text_a`.
  - `rationale`: a concise justification tied to the two texts. State the conclusion and the
    evidence directly -- do not narrate step-by-step reasoning or alternatives considered.
- `score`: the aggregate, computed as the rubric-weight-weighted average of the
  `criterion_scores` -- `sum(weight_i * score_i) / sum(weight_i)` -- rounded to the nearest whole
  number.
- `strengths`: concrete, non-empty statements of where the freelancer fits the task well. Use an
  empty array if there is nothing notable to report.
- `gaps`: concrete, non-empty statements of where the freelancer falls short of the task, or
  where a text says too little to judge. Use an empty array if there is nothing notable to report.
- `overall_rationale`: one or two sentences synthesizing the fit across every criterion.

Never invent skills, experience or availability for the freelancer, or requirements for the task:
what a text does not say scores low with a rationale saying what is missing. Do not invent rubric
criteria beyond the ones given, and do not include chain-of-thought or explanations outside the
schema fields.
