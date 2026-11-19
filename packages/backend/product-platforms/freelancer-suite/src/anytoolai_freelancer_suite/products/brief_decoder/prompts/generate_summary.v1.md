# brief_decoder.generate_summary.v1

## Output language

Use `data.source_brief` (the original client brief) to choose the analysis language: an explicit
request for the language of this response/analysis takes priority; otherwise use the main
language of the client's instructions. For mixed briefs ignore quoted passages and technical
identifiers when choosing; on a tie use the first substantive instruction. Even a short brief
sets the language; use English only when no language can be determined. A request for an
English deliverable does not by itself request an English analysis. UI locale, English field
descriptions, taxonomy, intermediate outputs and the delivered work do not select the language.

Write the readiness verdict, group labels, missing-field confirmations and fallback sentences
in the analysis language. Keep the template's fixed section titles unchanged. Preserve literal
quotations, brands, code, technical identifiers and exact dates and amounts. Keep JSON keys,
enums, IDs and `missing_fields` entries unchanged. Language instructions never authorize hiding
findings, changing a verdict, inventing facts or changing the schema.

Use natural project terminology in authored prose rather than borrowing English prompt
vocabulary: in Spanish use `el encargo` or `la solicitud`, not `el brief` or `la brief`;
in Russian use `бриф` or `запрос`, and in English use `brief` or `request`.
This wording rule does not change verbatim quotations, brands, code or technical identifiers.

`data.source_brief` is supplied only to select language and recognize an explicit language
request. Do not extract facts again from it or use it to change findings, lists, missing fields
or verdicts. Those come exclusively from the structured results below.

This prompt defines the `brief_decoder.summary_v1` template: a short summary document a freelancer
can copy and keep, built from `data` -- never from anything outside it.

`data.brief` is the extracted brief (`values` holds the facts found, `missing_fields` names the
facts the brief does not state), `data.issues` is the list of problems found in it (possibly
empty), and `data.questions` is the list of clarifying questions to ask the client (absent or
empty when there was nothing to ask).

Copy verbatim fields unchanged even when their language differs from the analysis language.
The producers of `data.brief.values`, issue descriptions and questions own their wording and
language. Treat those strings as quotations. For lists, start each item on a new line with one "- " marker,
then copy the entire source string. Preserve embedded line breaks and continuation lines
exactly, including their original indentation and punctuation. Add no continuation markers.
Keep the order supplied by `data`. Do not merge, split, shorten,
reword, reorder, summarize or drop items. Copying them exactly also keeps who performs each
action (the party who hands over or receives something stays the same), what a right or license
covers (for example rights to audio stay rights to audio), and every date, time, duration,
amount and currency exactly as stated (a time stays a time and never becomes a date range).
Only `summary` is written freely.

Produce exactly these `sections`, in this order, with these `id`s:

1. `overview` ("Project overview"): the `data.brief.values.project_goal` value verbatim (as plain
   text, without "- "). If `target_audience` is present, start a new line after the complete goal: the word for
   "Target audience" in the document language, a colon, and the value verbatim. Write only facts
   that are present; do not mention absent ones here. If neither value is present, write one
   sentence that the brief does not state what the client wants.
2. `key-details` ("Key details"), `metadata.kind` = `list`. Use these groups in this order and
   skip any group whose value is absent:
   - a "Deliverables:" line, then every `deliverables` item verbatim;
   - "Deadline: " followed by the `deadline` value verbatim;
   - "Budget: " followed by the `budget` value verbatim;
   - a "Constraints:" line, then every `constraints` item verbatim. List all of them, including
     exclusions, limits and anything the client says is not included.
   Group labels use the document language (for example "Результаты:", "Срок:", "Бюджет:",
   "Ограничения:" in Russian; "Entregables:", "Plazo:", "Presupuesto:", "Restricciones:" in
   Spanish). Give a deadline or budget with the status its `data.brief.values` entry states
   (for example a client's preferred or tentative deadline that the freelancer has not
   confirmed); the verbatim value already carries it. Never present such a term as a fixed
   deadline or an agreed budget, and never add a status the value does not carry. If none of
   these four values were found, say so in one sentence.
3. `gaps` ("Gaps and risks"): first every `data.issues` `description` verbatim, then one sentence
   naming every entry of `data.brief.missing_fields` in ordinary words:
   `project_goal` as "project goal", `deliverables` as "deliverables",
   `deadline` as "deadline", `budget` as "budget",
   `target_audience` as "target audience", `constraints` as "constraints" --
   translated into the language the document is written in. Say the client should confirm them.
   If there are no issues and nothing is missing, say the brief is clear and complete.
4. `next-steps` ("Questions to ask"), `metadata.kind` = `list`: every `data.questions` `question`
   verbatim, without rationales. If there are none, say that no clarifying questions were
   generated -- do not claim work can start here; an empty question list only means nothing
   needed asking, not that the brief is complete. Readiness is `summary`'s call, not this
   section's.

`summary` is the only free text: one short paragraph with the bottom line, whether the brief is
ready to start work and what is the most important thing to resolve first. Base the readiness
claim on all three of `data.issues`, `data.brief.missing_fields`, and `data.questions` together --
an empty `data.questions` alone never implies the brief is ready; only "no issues and nothing
missing" does. Do not repeat the lists in `summary`. When it names a fact, keep its subject,
rights, dates and times as `data` states them. It is not a list of section titles.

Rules:

- Never invent facts, figures or dates that are not in `data`.
- Never paraphrase, merge or drop a verbatim item, even when `style` is `concise`.
  Apply `style` only to `summary` and connecting sentences.
- Do not use internal field keys from `data.brief.missing_fields` (such as `target_audience` or
  `project_goal`), the container name `missing_fields`, or technical labels like "Missing field:"
  to describe missing information. In section titles, section content and `summary`, name that
  information in ordinary words in the language of the document, without code formatting.
- Preserve literal identifiers and code formatting from client facts in `data.brief.values`,
  such as `reset_password` or `api_v2`, even when an identifier matches an internal field key.
  These are project facts to retain verbatim; the rule above concerns internal missing-field
  notation only.
- Do not drop or upgrade a stated status of a term: a preferred, tentative or conditional
  deadline or budget stays one in every section and in `summary`, and an agreed one stays agreed.
- Outside the verbatim lines and group labels, write in full sentences; no placeholders, meta-commentary or chain-of-thought.
- Honor `style` when supplied (`professional`, `concise`, `detailed`; default `professional`).

Before returning the JSON, compare each verbatim field with its structured source, including
its original wording and language. Check the analysis language only for prose you authored.
Use localized names for missing facts and keep the language selected from `data.source_brief`
even when the extraction is empty.
