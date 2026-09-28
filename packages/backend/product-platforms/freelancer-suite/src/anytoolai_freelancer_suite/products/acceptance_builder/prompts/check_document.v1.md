# acceptance_builder.check_document.v1

This prompt defines the `acceptance_builder.check_v1` template: a narrative recap of a check of a
delivered piece of work against the client's brief, built from `data` -- never from anything
outside it. The recap is display-only: the text a user copies is composed from the structured
result, not from this document, so restate `data` faithfully and add nothing to it.

`data.extracted` is the extracted brief (`values` with `acceptance_criteria`, `assumptions`,
`deliverables`; `missing_fields` for the lists the brief does not state). `data.comparison` is the
verdict of the deliverable against four general review criteria (`scope_coverage`,
`requirement_fit`, `completeness`, `clarity`): `verdict`, `confidence`, `deltas`, `rationale`.

Produce exactly these `sections`, in this order, with these `id`s and titles:

1. `verdict` ("Verdict")
2. `acceptance-criteria` ("Acceptance criteria"), `metadata.kind` = `list`
3. `assumptions` ("Assumptions"), `metadata.kind` = `list`
4. `deliverables` ("Deliverables"), `metadata.kind` = `list`
5. `open-gaps` ("Open gaps")

`verdict` starts with exactly one of "Verdict: meets expectations.", "Verdict: partially meets
expectations." or "Verdict: does not meet expectations.", matching `data.comparison.verdict`
(`meets_expectations`, `partially_meets`, `does_not_meet`). It then has one sentence per
`data.comparison.deltas` entry, in the given order, starting with the criterion's label, a colon
and its status exactly as in `data`: "Scope coverage: partial.", "Requirement fit: match.",
"Completeness: mismatch.", "Clarity: match." (labels for `scope_coverage`, `requirement_fit`,
`completeness`, `clarity`), followed by the evidence. It must say that the verdict is judged on those four general review criteria,
not item by item on the acceptance criteria listed below -- never present it as a check of each
extracted criterion.

Sections 2-4 and `open-gaps` follow the same rules as the `acceptance_builder.draft_v1` template:
list every item of the matching `data.extracted.values` list verbatim, one per line, each
starting with "- ", or write "Not specified in the brief." when the list is absent; `open-gaps`
names each `data.extracted.missing_fields` entry as "acceptance criteria", "assumptions" or
"deliverables", or says the brief states all three lists. A list absent from `values` (named in
`missing_fields`) is always exactly "Not specified in the brief."; a present list is never.

`summary` is one short paragraph with the bottom line: the verdict and the most important thing
to fix or confirm first, taken from the `mismatch` and `partial` deltas.

Rules:

- Never invent facts, criteria or outcomes that are not in `data`; the verdict and statuses are
  `data.comparison`'s, never your own.
- Write in full sentences outside the lists; no placeholders, meta-commentary or chain-of-thought.
- Honor `style` when supplied (`professional`, `concise`, `detailed`; default `professional`).
