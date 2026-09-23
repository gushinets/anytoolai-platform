# brief_decoder.generate_questions.v1

Write the clarifying questions a freelancer should send back to the client who wrote the brief,
one per actionable entry in `issues`, using `context` (the original brief) to stay grounded.

Rules:

- Address every question to `target_audience`: plain, polite, answerable by a non-specialist
  client, no jargon and no meta-commentary.
- Each question references exactly one issue through its zero-based index into `issues` in
  `source_issue_index`.
- `rationale` is one sentence explaining why the answer matters for the work.
- `priority` must be `low`, `medium`, or `high`, reflecting the referenced issue's `severity` (a
  `high`-severity issue should normally yield a `high`-priority question, and so on) unless the
  specific question is materially less or more urgent than the issue itself.
- `category` should reuse the referenced issue's `category`; use a different one of the six
  taxonomy values only when the question itself more precisely fits that category.
- Return at most `max_questions` items (default 5); when there are more actionable issues, keep the
  highest-priority ones.
- Order `questions` by `priority` (`high`, then `medium`, then `low`) and, within the same priority,
  by ascending `source_issue_index`.
- Do not include chain-of-thought or explanations outside the schema fields.
