# Execution Plan: No self-introduction, signature or speaker gender in freelancer prompts (ANY-629)

## Status

- State: active
- Owner: agent
- Linear: ANY-629
- Created: 2026-10-22
- Last updated: 2026-10-22
- Review date: 2026-10-29
- Next action: rebase onto `main` after ANY-628 (PR #197) merges, open the PR, then confirm behavior in the ANY-631 live acceptance run.
- Blocker: none

## Goal

The freelancer's name and gender are not in the input, yet the models introduce themselves ("Меня
зовут …"), sign with placeholders (`[Your Name]`) and use gendered forms ("Готова", "мог(ла)",
"готов(а)"). Add one rule, in one wording, to the four prompts that write in the freelancer's voice.

## Scope

- One bullet, verbatim in `proposal_ai/prompts/compose_persuasive_text.v1.md` and in
  `client_update_writer/prompts/` `update_compose_reply.v1.md`, `reply_draft_compose_reply.v1.md`
  and `prepaid_request_compose_persuasive_text.v1.md`, next to the placeholder ban: no
  self-introduction by name and no sign-off with a name, role or contact details unless the input
  states them; construct sentences without the speaker's gender in languages that mark it.
- The existing Russian gender line in ProposalAI `Language` stays; it is now a special case of the
  general rule.
- Prompt versions are not bumped (`v1` edited in place, as in ANY-601..603, ANY-656, ANY-628).
- Test `freelancer-suite/tests/test_prompt_speaker_identity_rule.py` keeps the wording identical in
  all four prompts.

## Out of scope

- Square-bracket validator for `[Your Name]` (ANY-630).
- Exclusions and conditions (ANY-628), live acceptance (ANY-631), non-ASCII serialization (ANY-587).
- Speaker name or gender fields in the forms: the text is built without them.
- Brief Decoder, Acceptance Builder, Task Finder (they do not write first-person text to a client).

## Verification

- New test and the existing `test_proposal_ai_product.py` and `test_client_update_writer_product.py` pass.
- `python scripts/agent/runner.py quick-check` and `validate-configs` pass.
- `full-check`: 2354 tests pass; the only failure is
  `tests/test_runner.py::test_activation_marker_is_readable_by_non_root_api_user`, which needs
  passwordless `sudo -u nobody` and fails the same way on `main` in a sandbox without sudo.
- Live acceptance (ANY-631, needs `OPENAI_API_KEY`): P01 has no "Меня зовут …" and no "Готова", P02
  has no signature placeholder, no result contains "мог(ла)" or "готов(а)", and `warm` tone still
  reads naturally with neutral constructions.

## Risks

- A prompt rule is not a guarantee: the model may still sign or use gender. The Russian gender line
  already failed once on P01. If live shows repeats, assess ANY-597 (model and temperature) before
  strengthening the text.
- Neutral constructions ("я могу") read drier than "Готова помочь".
- "Unless the input explicitly gives them as the freelancer's own" allows a signature when the
  freelancer put their name in the positioning; QA did not cover that case. A name in the client's
  message or signature is the client's, not the freelancer's.
- The branch is stacked on ANY-628 (PR #197); a rewrite of its `Form` section in review could
  conflict.
