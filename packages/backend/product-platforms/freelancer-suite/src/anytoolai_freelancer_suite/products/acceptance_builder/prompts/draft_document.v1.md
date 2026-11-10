# acceptance_builder.draft_document.v1

## Output language

Use `data.source_brief` (the original client brief) to choose the analysis language: an explicit
request for the language of this response/analysis takes priority; otherwise use the main
language of the client's instructions. For mixed briefs ignore quoted passages and technical
identifiers when choosing; on a tie use the first substantive instruction. Even a short brief
sets the language; use English only when no language can be determined. A request for an
English deliverable does not by itself request an English analysis. UI locale, English field
descriptions, taxonomy, intermediate outputs and the delivered work do not select the language.

Write all authored prose in that language, including extracted descriptions and criteria,
issue descriptions, questions and their rationale, comparison rationale and explanatory evidence,
and every document summary and section content. A paraphrase is authored prose, not a quotation.
Preserve verbatim quotations, brands, code, technical identifiers and exact source dates/amounts;
do not translate JSON keys, enums, section/criterion IDs or `missing_fields` entries. Fixed
section titles specified by the template stay unchanged; explain missing fields by localized
names in prose. Language instructions never authorize hiding findings, changing a verdict,
inventing facts or changing the schema.

`data.source_brief` is supplied only to select language and recognize an explicit language
request. Do not extract facts again from it or use it to change findings, lists, missing fields
or verdicts. Those come exclusively from the structured results below. Keep extracted list
items verbatim; they already follow this same language policy. Translate authored explanations
faithfully without changing their meaning if an upstream explanation uses the wrong language.

This prompt defines the `acceptance_builder.draft_v1` template: a narrative recap of the
acceptance criteria drafted for a brief, built from `data` -- never from anything outside it. The
recap is display-only: the text a user copies is composed from the structured result, not from
this document, so restate `data` faithfully and add nothing to it.

`data.extracted` is the extracted brief: `values` holds the lists found (`acceptance_criteria`,
`assumptions`, `deliverables`) and `missing_fields` names the lists the brief does not state.

Produce exactly these `sections`, in this order, with these `id`s and titles:

1. `acceptance-criteria` ("Acceptance criteria"), `metadata.kind` = `list`
2. `assumptions` ("Assumptions"), `metadata.kind` = `list`
3. `deliverables` ("Deliverables"), `metadata.kind` = `list`
4. `open-gaps` ("Open gaps")

For sections 1-3, write every item of the matching `data.extracted.values` list verbatim, one per
line, each line starting with "- ". If that list is absent, say it is not specified in the brief
in the analysis language (English: "Not specified in the brief.", Russian: "Не указано в брифе.",
Spanish: "No se especifica en el encargo."). Do not invent items. A present list must never be
replaced by a missing-list sentence.

`open-gaps` names each entry of `data.extracted.missing_fields` using localized names for
acceptance criteria, assumptions or deliverables and says the client should confirm it.
If `missing_fields` is empty, say the brief states all three lists.

`summary` is one short paragraph: how many acceptance criteria were found and what the freelancer
should confirm with the client first. When no acceptance criteria were found, say so; never
imply the brief is fully specified unless `missing_fields` is empty.

Rules:

- Never invent criteria, assumptions, deliverables, figures or dates that are not in `data`.
- Write in full sentences outside the lists; no placeholders, meta-commentary or chain-of-thought.
- Honor `style` when supplied (`professional`, `concise`, `detailed`; default `professional`).

Before returning the JSON, check `summary` and every section content, including missing-list explanations against the analysis language selected
from the original brief. Correct any authored words in another language before returning;
keep actual source quotations and machine identifiers unchanged. This includes short labels
and descriptive units: they are prose even when their source field name is an English key.
Do not mention this check in the response.
