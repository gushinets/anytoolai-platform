# Execution Plan: ANY-628 ProposalAI Keeps Exclusions, Limits and Start Conditions

## Status

- State: active
- Owner: agent
- Created: 2026-10-22
- Last updated: 2026-10-22
- Review date: 2026-10-29
- Next action: open PR; live acceptance in ANY-631.
- Blocker: none

## Goal

QA Q-001: ProposalAI offered work the order excluded, dropped named limits (one revision round,
separate payment for original changes, glossary needed before start) and named amounts (EUR 300).
`compose_persuasive_text.v1.md` now has a "Scope and conditions from the order" section, and
`Price and terms` separates the client's stated terms from the freelancer's own offer.
Client Update Writer Update and ReplyDraft prompts get the same rule (same class of problem).

## Scope

- ProposalAI prompt section, `Price and terms` alignment (ANY-656 pinned fragments stay).
- Update and ReplyDraft prompt rule. PrepaidRequest already covers it (ANY-602), unchanged.
- Prompt-fragment tests in both products. Prompts stay at `v1` (precedent ANY-656, ANY-601-603).

## Out of scope

Name and gender placeholders (ANY-629), square-bracket validator (ANY-630), live acceptance
(ANY-631), non-ASCII serialization (ANY-587), fixtures, schemas, validators.

## Risks

- Restating client amounts may bring back "client budget as my price" (D-04); the rule keeps
  "is not your offer". Only live runs in ANY-631 prove it.
- P05-like orders may exceed the 120-200 word target; conditions outrank it, `constraints.length` does not.
