# Execution Plan: ANY-630 Reject bracket placeholders in compose_persuasive_text and compose_reply

## Status

- State: active
- Owner: agent
- Created: 2026-10-23
- Last updated: 2026-10-24 (code review #4)
- Review date: 2026-10-23
- Next action: PR review; move to `completed/` once merged.
- Blocker: none

## Goal

`PersuasiveTextCrossValidator` (A06) and `ComposeReplyCrossValidator` (A07) accepted text such as
`[Your Name]` / `[Contact Information]` although the prompts forbid placeholders. Both now reject a
bracketed slot via the shared `_find_unfilled_placeholder` (`cross_validation/_markup.py`), so the
existing validation retry runs. The check is built in because A07's input schema is closed (no
`forbidden_patterns`) and `kernel_demo` would otherwise stay unprotected.

## Decisions

- Code review #3 replaced the rules of rounds 1-2 (any field word, then the first or last word) with a
  two-part contract, because each open-world rule left a new bypass or false rejection for the next
  review:
  1. Read what the reader sees in the requested format (`_reader_text`, shared with
     `_has_visible_text`): formatting inside brackets disappears, line breaks and block boundaries
     are whitespace, invisible format characters are dropped, genuine Markdown links lose their
     brackets, malformed or undefined references stay literal, code is not read.
  2. A slot is a label made only of words from the closed EN/RU slot vocabulary (field words plus
     fillers) and separators (whitespace, `/ , & . : - _ …`), with at least one field word.
- Code review #4 found both parts too loose: digits and signs were ignored (`[Price: $100]` was a
  slot) and `<br>`/block boundaries were dropped (`[Your<br>Name]` passed). Part 2 now covers every
  character of the label, not only its words, and part 1 keeps visible breaks.
- Boundary: a slot with a word or character outside the contract passes (`[Your Awesome Name]`,
  `[Price: TBD]`); prose made of slot words and separators alone (`[Project Price]`) is a slot by
  definition; only ASCII square brackets are read. Extend the vocabulary from live data.
- Tests are one corpus of slot labels and one of prose labels, each run through A06 and A07 in
  `plain_text`, `markdown` and `html` with every spelling the reader still sees as brackets.
- No exemption for slots that appear in the action input (code review #1, P1): a `[Client Name]` in
  the brief is still unfilled in the output.
- Not covered: `{name}`, `<name>`, `%NAME%` (legitimate in code/HTML); products opt in through A06
  `forbidden_patterns` as ProposalAI does. Gender forms and "Меня зовут …" stay with the prompts.
- Failure after the second validation attempt fails the action, same as length and markup rules.
- Reasons: `text_contains_unfilled_placeholder:<slot>`,
  `call_to_action_contains_unfilled_placeholder:<slot>`.

## Verification

- `TestUnfilledPlaceholder` in `platform-actions/tests/test_cross_validation.py`.
- `quick-check`, `atoms-proof`.
