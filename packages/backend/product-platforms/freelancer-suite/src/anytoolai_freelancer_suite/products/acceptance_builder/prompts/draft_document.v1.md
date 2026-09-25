# acceptance_builder.draft_document.v1

This prompt defines the `acceptance_builder.draft_v1` template: an acceptance-criteria document a
freelancer can copy and send to the client, built from `data` -- never from anything outside it.

`data.extracted` is the extracted brief: `values` holds the lists found (`acceptance_criteria`,
`assumptions`, `deliverables`) and `missing_fields` names the lists the brief does not state.

Produce exactly these `sections`, in this order, with these `id`s and titles:

1. `acceptance-criteria` ("Acceptance criteria"), `metadata.kind` = `list`
2. `assumptions` ("Assumptions"), `metadata.kind` = `list`
3. `deliverables` ("Deliverables"), `metadata.kind` = `list`
4. `open-gaps` ("Open gaps")

For sections 1-3, write every item of the matching `data.extracted.values` list verbatim, one per
line, each line starting with "- ". If that list is absent, write the single sentence "Not
specified in the brief." -- do not fill the section with items you made up.

`open-gaps` names, by their plain-language name, each entry of `data.extracted.missing_fields`
and says the client should confirm it. If `missing_fields` is empty, say the brief states all
three lists.

`summary` is one short paragraph: how many acceptance criteria were found and what the freelancer
should confirm with the client first. When no acceptance criteria were found, say so; never
imply the brief is fully specified unless `missing_fields` is empty.

Rules:

- Never invent criteria, assumptions, deliverables, figures or dates that are not in `data`.
- Write in full sentences outside the lists; no placeholders, meta-commentary or chain-of-thought.
- Honor `style` when supplied (`professional`, `concise`, `detailed`; default `professional`).
