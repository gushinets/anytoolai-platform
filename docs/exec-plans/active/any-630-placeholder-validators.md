# Execution Plan: ANY-630 Reject bracket placeholders in compose_persuasive_text and compose_reply

## Status

- State: active
- Owner: agent
- Created: 2026-10-23
- Last updated: 2026-10-24
- Review date: 2026-10-23
- Next action: PR review; move to `completed/` once merged.
- Blocker: none

## Goal

`PersuasiveTextCrossValidator` (A06) and `ComposeReplyCrossValidator` (A07) accepted text such as
`[Your Name]` / `[Contact Information]` although the prompts forbid placeholders. Both now reject a
bracketed slot via the shared `_find_unfilled_placeholder` (`cross_validation/_shared.py`), so the
existing validation retry runs. The check is built in because A07's input schema is closed (no
`forbidden_patterns`) and `kernel_demo` would otherwise stay unprotected.

## Decisions

- A slot is a square-bracket label (1-60 characters, no nesting, no newline) whose head word names a
  field (first or last word: `name`, `description`, `price`, `deadline`, `имя`, `дата`, ...) or that
  starts with a fill-in verb (`insert`, `enter`, `add`, `укажите`, `вставьте`, `введите`). A field
  word elsewhere in the label is prose (code review #2): `[Client update]`,
  `[Your request was received]`. A bracket shape alone cannot tell `[Ваше имя]` from
  `[Project brief]`, hence the EN/RU word list; an unlisted head (`[Scope]`) passes.
- Accepted: `[1]`, `[1, 2]`, `[x]`, `[ ]`, `[...]`, `[sic]`, `[FYI]`, `[Project X]`, code spans, and
  Markdown links the parser resolves (inline links, references with a real definition). A definition
  without a destination or an undefined reference stays text and is checked (code review #2).
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
