# acceptance_builder.check_document.v1

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

`verdict` starts with a sentence expressing `data.comparison.verdict` in the analysis language:
`meets_expectations` means the work meets expectations, `partially_meets` means it partially
meets them, and `does_not_meet` means it does not meet them. It then has one sentence per
`data.comparison.deltas` entry, in the given order, with a localized criterion label and status
(`match`: satisfied, `partial`: partially satisfied, `mismatch`: not satisfied), followed by
the evidence. Preserve the exact meaning of every status; do not recompute the verdict.
It must say that the verdict is judged on the four general review criteria, not item by item
on the acceptance criteria listed below. Translate this explanation as well.

Sections 2-4 list every item of the matching `data.extracted.values` list verbatim, one per line,
each starting with "- ". When a list is absent, say it is not specified in the brief in the
analysis language (English: "Not specified in the brief.", Russian: "Не указано в брифе.",
Spanish: "No se especifica en el encargo."). Never replace a present list with that sentence.
`open-gaps` names every `data.extracted.missing_fields` entry using localized names for acceptance
criteria, assumptions or deliverables and asks the client to confirm it; if none are missing,
say the brief states all three lists.

`summary` is one short paragraph with the bottom line: the verdict and the most important thing
to fix or confirm first, taken from the `mismatch` and `partial` deltas.

Rules:

- Never invent facts, criteria or outcomes that are not in `data`; the verdict and statuses are
  `data.comparison`'s, never your own.
- Write in full sentences outside the lists; no placeholders, meta-commentary or chain-of-thought.
- Honor `style` when supplied (`professional`, `concise`, `detailed`; default `professional`).

Before returning the JSON, check `summary` and every section content, including verdict and status explanations against the analysis language selected
from the original brief. Correct any authored words in another language before returning;
keep actual source quotations and machine identifiers unchanged. This includes short labels
and descriptive units: they are prose even when their source field name is an English key.
Do not mention this check in the response.
