# brief_decoder.detect_issues.v1

Find the risks, gaps, ambiguities and contradictions in the client brief `source_text` that a
freelancer should resolve before starting work. Return each finding as an entry in `issues`.

Rules:

- `category` must be one of the `taxonomy` values: `missing_information` (something a freelancer
  needs is absent), `ambiguity` (a statement can be read in more than one way), `scope_risk`
  (open-ended or unbounded work), `timeline_risk` (missing, unrealistic or conflicting timing),
  `budget_risk` (missing, unrealistic or conflicting budget) or `contradiction` (two statements
  in the brief disagree).
- `description` is a self-contained, one-sentence explanation of the problem.
- `severity` is `high` when work cannot responsibly start without resolving it, `medium` when it
  is likely to cause rework, `low` otherwise.
- `evidence` is a short quote or close paraphrase from the brief; omit it when the issue is an
  absence (nothing in the brief to quote).
- Report only real problems in this brief. If it is clear and complete, return an empty `issues`
  array -- that is a valid, successful result.
- Do not include chain-of-thought or explanations outside the schema fields.
