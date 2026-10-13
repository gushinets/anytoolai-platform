# kernel_demo.generate_gap_rewrites.v1

Generate exactly `n` (default 3 if omitted) targeted rewrite alternatives for `source_text` that
close the explicit `gap`. Return `rewrites` and `best_pick`:

- `rewrites`: exactly `n` entries, each with:
  - `text`: a complete, ready-to-use rewrite of `source_text` closing `gap` — no placeholders or
    meta-commentary.
  - `explanation`: a concise summary of why this rewrite closes the gap. State the conclusion
    directly — do not narrate step-by-step reasoning or any other chain-of-thought.
  - `change_made`: a short, concrete description of what changed relative to `source_text`.
  - Each `text` must be substantively different from every other rewrite's `text` — do not submit
    near-duplicates that differ only in whitespace or capitalization.
- Match `style`: `conservative` (minimal, closely follows `source_text`), `moderate` (balanced
  revision), or `bold` (substantially reworked).
- `best_pick`: the zero-based index into `rewrites` of the strongest alternative.

Do not invent facts beyond what `source_text` and `gap` provide, and do not include
chain-of-thought or explanations outside the schema fields.

Language for user-facing fields:

- Use an explicit input language constraint when present; otherwise use the language of the
  main input text. Apply it to every generated human-facing string, including explanations,
  rationales, commentary, titles, summaries, labels, extracted descriptive strings and array items.
- Keep schema keys, required enums, supplied option/taxonomy values, IDs, proper names, technical
  identifiers and permitted source quotations unchanged. They are not language violations.

Preserve meaning in every alternative:

- Keep each person's exact role. Responsibility for review does not imply responsibility for
  preparation, sending or delivery. Do not transfer an action to a person merely to clarify a gap.
- Preserve deadlines as deadlines, including "by"/"before" versus "on"; do not turn the latest
  permitted date into an exact execution date. Preserve the source's level of commitment without
  adding a guarantee, certainty, extra deliverable or other fact.
- Vary communicative emphasis, organization and framing to offer useful alternatives within the
  same facts and requested style. Cosmetic word substitutions alone are insufficient.
- Check all rewrites against source roles, conditions, deadlines and commitments before choosing
  best_pick. Explanations and change_made must accurately describe the change without adding facts.
