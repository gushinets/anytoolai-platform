# kernel_demo.compare_and_classify.v1

Compare `subject_text` against `reference_text` using exactly the given `criteria` (each with
`id`, `description`, and optional `weight`), then classify the comparison into one of `categories`.
Return:

- `verdict`: exactly one of the given `categories`. Do not invent a category outside this list.
- `confidence`: a number from 0 to 1 reflecting how strongly the evidence supports `verdict`. This
  is a relative signal, not a calibrated probability — do not present it as one.
- `deltas`: exactly one entry per criterion in `criteria`, in any order, each with:
  - `criterion_id`: the matching criterion's `id`, unchanged.
  - `status`: `match` if `subject_text` satisfies the criterion as well as `reference_text` does,
    `partial` if it satisfies it incompletely, `mismatch` if it does not satisfy it.
  - `evidence`: a short, concrete quote or close paraphrase from `subject_text` and/or
    `reference_text` supporting `status`. If a criterion has a `weight`, heavier-weighted criteria
    should carry more influence over `verdict` than lighter ones.
- `rationale`: a concise summary stating the conclusion and the criteria that drove it. State the
  conclusion directly — do not narrate step-by-step reasoning or any other chain-of-thought.

Do not invent criteria, categories, or facts beyond what `subject_text`, `reference_text`,
`categories`, and `criteria` provide.
