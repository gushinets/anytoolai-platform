# brief_decoder.generate_summary.v1

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

Before returning the JSON, check `summary` and every section content, including labels and names of missing facts against the analysis language selected
from the original brief. Correct any authored words in another language before returning;
keep actual source quotations and machine identifiers unchanged. This includes short labels
and descriptive units: they are prose even when their source field name is an English key.
Do not mention this check in the response.
When naming missing facts or introducing a list, use natural words in the analysis
language, never copy `missing_fields` keys as prose. An empty extraction still uses the
language of `data.source_brief`. The questions and their rationales must also use that
language; translate an upstream explanation faithfully without changing its finding.
