# Freelancer Suite v0

Freelancer Suite v0 is the MVP-B web-first validation bundle. It proves that the platform kernel and
MVP-A2 Client Surfaces can support real products through config, product-owned web definitions, and
thin frontend composition.

## Validation Products

1. ProposalAI.
2. Client Message Decoder.
3. Scope Creep Guard.
4. Send-Ready.
5. Brief Decoder.

The 21 atom-ready concepts remain the wider capability inventory. Client Update Writer,
Acceptance Builder, and External Task Finder & Fit are outside the initial set and have no
committed release order. PrepaidRequest and ReplyDraft remain modes of the later Client Update Writer.

## Recommended Build Order

1. ProposalAI: `A06` for v1; `A09 -> A06` remains a later option.
2. Client Message Decoder: `A01 -> A07`, with `A04` optional.
3. Scope Creep Guard: `A11 -> A07`; comparison results and request data to `A10`.
4. Send-Ready: `A04 + A03`, then a user-selected gap to `A08` in a second scenario run.
5. Brief Decoder: `A01 + A04 -> A05`, results to `A10`.

The release order follows product demand priorities: ProposalAI addresses the most frequent
customer pain; Client Message Decoder combines frequent need with fear of making a mistake;
Scope Creep Guard and Send-Ready have preliminary demand validation; Brief Decoder has high value
across projects. These priority reasons were supplied by the product owner on 2026-09-08.

ProposalAI proves the shortest complete web path. Client Message Decoder is the second product
and proves reuse before shared UI extraction. Scope Creep Guard proves scope comparison, reply,
and document generation. Send-Ready proves the two-run selected-gap flow without extending the
mapping DSL. Brief Decoder completes the initial set with brief analysis, questions, and a document.

Client Update Writer, Acceptance Builder, and External Task Finder & Fit remain in the capability
backlog without a committed release order. Brief Decoder to Acceptance Builder remains a later
handoff candidate, not a dependency of the initial five-product release set.

## Handoff Chains

The initial five-product order does not require a product-to-product handoff pair. Shared MVP-A2
handoff proof remains in scope. Later candidates are:

```text
ProposalAI -> Send-Ready
Brief Decoder -> Acceptance Builder
External Task Finder & Fit -> ProposalAI
```

Any delivered web handoff uses existing backend tokens, `immediate` target start, and same-tab
navigation. Deferred continuation is outside the initial validation set.

## Implementation Rule

Each product is added through:

- product config;
- scenario and workflow config;
- action configs, prompts, and schemas;
- a product definition/page composed by `apps/web-mirror`;
- a product result renderer;
- product events and activation definition;
- a handoff map where applicable;
- deterministic runtime and browser E2E evidence.

Dedicated Chrome Extensions are optional product-owned follow-ups. Product delivery must not add
Freelancer meaning to `platform-core` or change atoms, action/workflow runners, Provider Gateway,
scenario/quota/handoff runtime, or mapping DSL.
