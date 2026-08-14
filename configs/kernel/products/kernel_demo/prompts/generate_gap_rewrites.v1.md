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
