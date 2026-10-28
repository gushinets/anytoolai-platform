# Execution Plan: ANY-594 Reply Draft Keeps Every Action From the Reply Goal

## Status

- State: active
- Owner: agent
- Created: 2026-10-28
- Last updated: 2026-10-28
- Review date: 2026-10-28
- Next action: merge the ANY-625 PR once CI is green; ANY-626 extends this plan; live acceptance
  in ANY-627.
- Blocker: none

## Goal

Reply Draft (QA Q-003) dropped content the freelancer asked for: R05 lost "I will send a corrected
invoice", R04 ignored the client's "don't add pages". The reply must state every fact, decision
and promised action from `intent` (`reply_goal`) and address every constraint the client states.

## Scope

- ANY-625: completeness rule in `reply_draft_compose_reply.v1.md`. It draws the boundary with the
  author-directions rule (ANY-619/620): a fact, decision or promised action in `intent` is content
  for the client; only a direction about how to write the reply is followed without being stated.
  The `situation` rule now names constraints (R04). A test pins the rule text.

## Out of scope

`call_to_action` repeating `text` and naming the subject in the client's words (ANY-626), the
author-directions and speaker-identity rules (ANY-619/620/629), Update and Prepaid Request
prompts, live acceptance (ANY-627).

## Risks

Text tests do not prove model behavior; only live runs (ANY-627) do. Treating everything in
`intent` as content would leak author directions again (R05 "we cannot confirm it was sent");
the opposite drops promised actions. Naming client constraints must not make the model accept
them; the terms-status rule still forbids that.
