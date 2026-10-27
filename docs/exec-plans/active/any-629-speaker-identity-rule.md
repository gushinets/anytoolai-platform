# Execution Plan: No self-introduction, signature or speaker gender in freelancer prompts (ANY-629)

## Status

- State: active
- Owner: agent
- Linear: ANY-629
- Created: 2026-10-22
- Last updated: 2026-10-27
- Review date: 2026-10-29
- Next action: review and merge the reopen fix (gendered past tense and "чтобы я ..."), then move this plan to `completed/`.
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

## Reopen 2026-10-27: gendered verbs in live outputs

Basic acceptance on GPT-6 Luna still produced speaker gender without it in the input: "чтобы я мог
изучить", "чтобы я начал", "чтобы я мог перейти", "новую дату пока не обещал", "я сама задаю". The
rule named only adjectives ("готов(а)", "мог(ла)"), so the model did not treat the past tense,
"чтобы я" with a verb and "сам"/"сама" as gendered.

- The shared rule now names those forms and gives neutral replacements (present or future tense,
  impersonal phrases), keeps the stated-gender exception and says to change wording, not facts.
- ProposalAI: the closing request ("Пришлите ..., чтобы я ...") is where the form slipped, so the
  `Structure` next-step line gives the neutral closing; the old Russian line in `Language` now points
  to the shared rule instead of repeating a weaker copy.

Live check on the dev live stack (synthetic inputs modelled on the reopen cases, `warm` tone):

| Product | Before (`main`) | After |
| -- | -- | -- |
| ProposalAI, no stated gender | 3 of 6 runs gendered ("чтобы я мог", "чтобы я начал", "чтобы я приступил") | 0 of 10 |
| ProposalAI, feminine author stated | feminine forms kept | feminine forms kept ("работала", "сделала") |
| Client Update Writer update, reply draft | 0 of 9 (cases did not reproduce) | 0 of 18 |
| Client Update Writer prepaid request | not run | 0 of 5 |

Facts, amounts, dates and actions stayed as in the input. Client Update Writer did not reproduce on
these inputs before the fix, so its result shows no regression, not a fix.

Review follow-up (code-review #3):

- The rule named all first-person past tense, but plural "мы" forms are neutral; and the example "новую
  дату пока не обещаю" moved "no date has been promised" to "I am not promising now". The rule now
  names only the singular past tense, keeps a "мы" the input uses, and says to keep the tense and
  status of the input ("новую дату мы пока не обещали", "обещаний по новой дате с моей стороны пока
  не было").
- The ProposalAI closing example ("Пришлите материалы, и я начну") could invent a request for
  materials or a start condition. It is now a grammar pattern for the next step the input supports.

Live check after the follow-up (ProposalAI, 4 runs per case): 0 of 16 gendered without a stated
gender, including an order with nothing to send (access already given: the closing goes straight to
the work, no request for materials) and an order with a prepayment start condition (the closing
names the 30% prepayment from the order, nothing else). Feminine forms stay when the author is
stated as a woman. Client Update Writer rerun (incl. the CU-U-RU-10 regression): pending.

## Risks

- A prompt rule is not a guarantee: the model may still sign or use gender. The Russian gender line
  already failed once on P01. If live shows repeats, assess ANY-597 (model and temperature) before
  strengthening the text.
- Neutral constructions ("я могу") read drier than "Готова помочь".
- "Unless the input explicitly gives them as the freelancer's own" allows a signature when the
  freelancer put their name in the positioning; QA did not cover that case. A name in the client's
  message or signature is the client's, not the freelancer's.
- The rule does not govern the closing: each prompt's own rules do (ProposalAI requires one concrete
  next step, the reply drafts forbid an invented `call_to_action`).
