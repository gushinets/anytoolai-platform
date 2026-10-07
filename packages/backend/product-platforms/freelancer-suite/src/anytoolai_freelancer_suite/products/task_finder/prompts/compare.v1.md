# task_finder.compare.v1

Judge how well the freelancer described in `subject_text` fits the task described in
`reference_text`. Classify the outcome into exactly one of `categories` and judge every entry of
`criteria`; both come from the input payload.

Rules:

- `verdict` is one of `categories`, verbatim, and follows from the `deltas` statuses alone: use
  `strong_fit` only when every criterion is a `match`; use `weak_fit` when at least one criterion
  is a `mismatch`; otherwise (no `mismatch`, at least one `partial`) use `partial_fit`. Never pick
  a verdict that the statuses contradict.
- `deltas` has exactly one entry per `criteria` id, in the order given, with `criterion_id`
  copied verbatim, `status` one of `match`, `partial`, `mismatch`, and `evidence` quoting or
  closely paraphrasing what the two texts say. Evidence comes from those two texts only; never
  invent skills, experience or availability for the freelancer, or requirements for the task.
- A criterion the texts do not let you judge is never a `match` by default, and a missing detail
  is not a conflict. Use `mismatch` only when the texts clearly conflict or the freelancer clearly
  lacks what the task needs (`skills_fit`, `experience_fit`, `scope_fit`). When the task or the
  profile simply does not state the information (typical for `constraints_fit`: no deadline,
  budget or availability given), use `partial` and say in `evidence` what is not stated.
- The criterion weights apply to the score, not to `verdict`: the verdict follows the statuses only.
- `confidence` is a number between 0 and 1: lower it when either text is short or vague.
- `rationale` is at most 500 characters and explains the verdict in plain sentences.
- Do not include chain-of-thought -- return only the JSON fields defined by the output schema.
