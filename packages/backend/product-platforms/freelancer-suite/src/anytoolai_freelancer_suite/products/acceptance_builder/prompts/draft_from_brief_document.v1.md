# acceptance_builder.draft_from_brief_document.v1

This prompt defines the `acceptance_builder.draft_from_brief_v1` template: an acceptance-criteria
document a freelancer can copy and send to the client, built from `data` -- never from anything
outside it.

`data.brief` is a structured client brief produced by Brief Decoder: `values` holds the facts
found (any of `project_goal`, `deliverables`, `deadline`, `budget`, `target_audience`,
`constraints`; absent keys were not stated) and `missing_fields` names the facts the brief does
not state. `data.issues` are the problems Brief Decoder found in that brief (`category`,
`severity`, `description`, optional `evidence`), possibly empty, and `data.questions` are the
clarifying questions it proposes to ask the client, possibly empty. Brief Decoder's warnings must
stay visible in the result: never present a flagged value as a settled requirement.

Produce exactly these `sections`, in this order, with these `id`s and titles:

1. `acceptance-criteria` ("Acceptance criteria"), `metadata.kind` = `list`
2. `deliverables` ("Deliverables"), `metadata.kind` = `list`
3. `open-gaps` ("Open gaps")
4. `open-issues` ("Open issues and questions"), `metadata.kind` = `list`

`acceptance-criteria`: one checkable condition per line, each line starting with "- ", and each
line restating exactly one entry of `data.brief.values.deliverables`, one entry of
`data.brief.values.constraints`, the `deadline` or the `budget` as a condition the finished work
must satisfy. Never add a condition that is not one of those entries, and never turn
`project_goal` or `target_audience` into a criterion. When an issue in `data.issues` flags the
value a line restates (the value appears in that issue's `evidence` or `description`), end the line
with " (to confirm)"; do not add that suffix to any other line. If none of those values is present, write
the single sentence "Not specified in the brief."

`deliverables`: every item of `data.brief.values.deliverables` verbatim, one per line, each
starting with "- ", or "Not specified in the brief." when absent.

`open-gaps` names, in plain language, each entry of `data.brief.missing_fields` and says the
client should confirm it. If `missing_fields` is empty, say the brief states everything Brief
Decoder looks for.

`open-issues`: one line per entry of `data.issues`, in the given order, exactly
"- [<severity>] <category>: <description>", followed by one line per entry of `data.questions`, in
the given order, exactly "- Ask: <question>". If both are empty, write the single sentence "Brief
Decoder flagged no issues and proposed no questions."

`summary` is one short paragraph: how many acceptance criteria were drafted, how many are still to
confirm, and what the freelancer should confirm with the client first. Never imply the brief is
fully specified unless `missing_fields`, `data.issues` and `data.questions` are all empty.

Rules:

- Never invent criteria, deliverables, figures or dates that are not in `data`.
- Write in full sentences outside the lists; no placeholders, meta-commentary or chain-of-thought.
- Honor `style` when supplied (`professional`, `concise`, `detailed`; default `professional`).
