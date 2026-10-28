# Execution Plan: ANY-594 Reply Draft Keeps Every Action From the Reply Goal

## Status

- State: active
- Owner: agent
- Created: 2026-10-28
- Last updated: 2026-10-28
- Review date: 2026-10-28
- Next action: merge the ANY-626 PR once CI is green; live acceptance in ANY-627.
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
- ANY-626: Reply Draft names what the client asks about in the client's own words and scope (R01
  "testimonials" became "any new comments or requests"; R04 narrowed "approve it" to the German
  text). The frontend appends `call_to_action` to `text` after a blank line, so both prompts that
  emit `call_to_action` (Reply Draft and Update) now state that the two fields are one message and
  each request appears in only one of them (R01, R02 repeated the final request). Prepaid Request
  emits no `call_to_action`; the issue's reference to a prepaid rule at
  `prepaid_request_compose_reply.v1.md:26-27` is stale (no such file). Tests pin the rule text.

## Out of scope

Frontend deduplication of `text` and `call_to_action`, the author-directions and speaker-identity
rules (ANY-619/620/629), subject and unit distortions in Update (ANY-593/ANY-623), Prepaid Request,
live acceptance (ANY-627).

## Risks

Text tests do not prove model behavior; only live runs (ANY-627) do. Treating everything in
`intent` as content would leak author directions again (R05 "we cannot confirm it was sent");
the opposite drops promised actions. Naming client constraints must not make the model accept
them; the terms-status rule still forbids that. "The client's own words" must not turn into quoting
the client verbatim. The one-request rule could drop the request from both fields; the
`call_to_action` gate and the completeness rule hold it.
