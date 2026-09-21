# brief_decoder.generate_questions.v1

Write the clarifying questions a freelancer should send back to the client who wrote the brief,
one per actionable entry in `issues`, using `context` (the original brief) to stay grounded.

Rules:

- Address every question to `target_audience`: plain, polite, answerable by a non-specialist
  client, no jargon and no meta-commentary.
- Each question references exactly one issue through its zero-based index into `issues` in
  `source_issue_index`.
- `rationale` is one sentence explaining why the answer matters for the work.
- `priority` follows the referenced issue's `severity` (`high`, `medium`, `low`).
- `category` reuses the referenced issue's `category`.
- Return at most `max_questions` items (default 5); when there are more actionable issues, keep the
  highest-priority ones.
- Order `questions` by `priority` (`high`, then `medium`, then `low`) and, within the same priority,
  by ascending `source_issue_index`.
- Do not include chain-of-thought or explanations outside the schema fields.
