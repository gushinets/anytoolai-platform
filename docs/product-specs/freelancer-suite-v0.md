# Freelancer Suite v0

Freelancer Suite v0 is the MVP-B web-first validation bundle. It proves that the platform kernel and
MVP-A2 Client Surfaces can support real products through config, product-owned web definitions, and
thin frontend composition.

## Validation Products

1. ProposalAI.
2. Client Update Writer, including PrepaidRequest and ReplyDraft modes.
3. Brief Decoder.
4. Acceptance Builder.
5. Task Finder.
6. Send-Ready.

The 21 atom-ready concepts remain the wider capability inventory; they are not all committed Suite
releases.

## Recommended Build Order

1. ProposalAI proves one-atom web execution and copy-button activation.
2. Client Update Writer proves reuse before shared UI extraction.
3. Brief Decoder proves the first composite document workflow.
4. Acceptance Builder proves an `immediate` same-tab handoff from Brief Decoder.
5. Task Finder proves score-based value delivery and can later hand off to ProposalAI.
6. Send-Ready proves a user-selected gap and second workflow run without changing mapping DSL.

## Handoff Chains

The first required validation chain is:

```text
Brief Decoder -> Acceptance Builder
```

Later supported candidates are:

```text
Task Finder -> ProposalAI
ProposalAI -> Send-Ready
```

The first release uses existing backend tokens, `immediate` target start, and same-tab navigation.
Deferred continuation is outside this validation set.

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
