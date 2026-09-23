# brief_decoder.generate_summary.v1

This prompt defines the `brief_decoder.summary_v1` template: a short summary document a freelancer
can copy and keep, built from `data` -- never from anything outside it.

`data.brief` is the extracted brief (`values` holds the facts found, `missing_fields` names the
facts the brief does not state), `data.issues` is the list of problems found in it (possibly
empty), and `data.questions` is the list of clarifying questions to ask the client (absent or
empty when there was nothing to ask).

Produce exactly these `sections`, in this order, with these `id`s:

1. `overview` ("Project overview"): what the client wants and for whom, from `data.brief.values`.
   Write only facts that are present; do not mention absent ones here.
2. `key-details` ("Key details"): deliverables, deadline, budget and constraints that were found,
   as a list (`metadata.kind` = `list`). If none were found, say so in one sentence.
3. `gaps` ("Gaps and risks"): the `data.issues` in plain sentences, plus the `data.brief.missing_fields`
   by name. If there are no issues and nothing is missing, say the brief is clear and complete.
4. `next-steps` ("Questions to ask"): the `data.questions` as a list (`metadata.kind` = `list`).
   If there are none, say that no clarifying questions were generated -- do not claim work can
   start here; an empty question list only means nothing needed asking, not that the brief is
   complete. Readiness is `summary`'s call, not this section's.

`summary` is one short paragraph with the bottom line: whether the brief is ready to start work and
what is the most important thing to resolve first. Base the readiness claim on all three of
`data.issues`, `data.brief.missing_fields`, and `data.questions` together -- an empty
`data.questions` alone never implies the brief is ready; only "no issues and nothing missing"
does. It is not a list of section titles.

Rules:

- Never invent facts, figures or dates that are not in `data`.
- Write in full sentences; no placeholders, meta-commentary or chain-of-thought.
- Honor `style` when supplied (`professional`, `concise`, `detailed`; default `professional`).
