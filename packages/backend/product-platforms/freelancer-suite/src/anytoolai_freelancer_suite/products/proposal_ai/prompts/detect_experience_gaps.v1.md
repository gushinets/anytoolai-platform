# proposal_ai.detect_experience_gaps.v1

Compare a client's task with a freelancer's stated experience and list the requirements of the task
that the experience does not cover. `source_text` is the client's task or job post. `context` is the
freelancer's stated experience and strengths. Return each uncovered requirement as an entry in
`issues`.

Rules:

- `category` is always `experience_gap`.
- A gap is an explicit requirement of the task (a tool, platform, skill, domain or kind of work the
  client asks for) with no matching tool, skill, case or clearly adjacent experience in `context`.
  Do not report a requirement that `context` covers, even if worded differently.
- Report named tools, platforms, protocols, domains and explicitly demanded skills. Do not report
  routine steps of the work (cleaning data, sorting files, sending notifications, writing
  documentation) that anyone experienced in the same field does as a matter of course.
- Do not report wishes about price, timeline or communication, and do not report vague or optional
  nice-to-haves unless the task names them as required.
- `description` is one short sentence naming the missing requirement, written in the language of
  `context` (the freelancer is the reader). Do not suggest what to do about it.
- `severity` is `high` when the task cannot be done without it, `medium` when it is a stated
  requirement but only a part of the work, `low` when it is mentioned as a preference.
- `evidence` is a short quote from `source_text` that states the requirement.
- If `context` covers everything the task requires, return an empty `issues` array. That is a valid,
  successful result.
- Do not include chain-of-thought or explanations outside the schema fields.
