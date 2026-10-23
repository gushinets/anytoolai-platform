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

- A slot is a square-bracket group (1-60 characters, no nesting, no newline) whose words name a
  field to fill in (EN/RU field words: `your`, `name`, `contact`, `date`, `client`, `ваш`, `имя`,
  `контакт`, ...). A bracket shape alone cannot tell `[Ваше имя]` from `[Project brief]`.
- Accepted: `[1]`, `[1, 2]`, `[x]`, `[ ]`, `[...]`, `[sic]`, `[FYI]`, `[Project X]`, inline and full-reference Markdown links and shortcut references defined by `[label]: url` in the same text.
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
