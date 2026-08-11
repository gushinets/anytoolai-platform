# kernel_demo.generate_clarifying_questions.v1

Generate clarifying questions from the structured `issues` array (each issue has `category`,
`description`, `severity`, and optional `evidence`), using `context` to stay grounded in the
actual situation and `target_audience` to judge what phrasing and level of detail is appropriate
for the person who will answer. Return at most `max_questions` items (default 5) in `questions`.

Rules:

- Only generate a question for an issue that is actually actionable — asking the
  `target_audience` a clarifying question must be able to move the issue toward resolution. Skip
  issues that are not actionable (for example, purely informational observations). If none of the
  supplied `issues` are actionable, return an empty `questions` array — that is a valid,
  successful result.
- Each question must reference exactly one source issue via its zero-based index into `issues` in
  `source_issue_index`.
- `question` must be a single, self-contained, answerable question addressed to
  `target_audience` — no meta-commentary, no chain-of-thought.
- `rationale` must be a concise, one-sentence explanation of why answering this question resolves
  or clarifies the referenced issue.
- `priority` must be `low`, `medium`, or `high`, reflecting the referenced issue's `severity`
  (a `high`-severity issue should normally yield a `high`-priority question, and so on) unless the
  specific question is materially less or more urgent than the issue itself.
- `category` must describe the kind of question (for example reuse the referenced issue's
  `category`, or a more specific label if the question narrows it).
- If more actionable issues exist than `max_questions` allows, keep the highest-priority
  questions first and drop the rest.
- Order `questions` deterministically: by `priority` (`high`, then `medium`, then `low`), and
  within the same priority, by ascending `source_issue_index`.
- Do not include chain-of-thought or explanations outside the schema fields.
