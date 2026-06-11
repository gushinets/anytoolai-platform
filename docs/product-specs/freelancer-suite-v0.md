# Freelancer Suite v0

Freelancer Suite v0 is the MVP-B validation bundle. It proves the platform kernel can support real CE-first products through config and thin frontend wrappers.

## Products

1. ProposalAI
2. Acceptance Builder
3. Case Study
4. Scope Guard
5. Task Finder
6. Send-Ready
7. Brief Decoder
8. Persuasion Lens

## Recommended Build Order

1. ProposalAI: quickest end-to-end proof.
2. Acceptance Builder.
3. Case Study + Upsell.
4. Scope Guard.
5. Task Finder.
6. Send-Ready.
7. Brief Decoder.
8. Persuasion Lens.

## Primary Handoff Chains

```text
Task Finder -> ProposalAI
ProposalAI -> Send-Ready
Brief Decoder -> Scope Guard
Brief Decoder -> Acceptance Builder
```

## Implementation Rule

Each product is added as:

- product config
- scenario config
- workflow config
- action configs
- prompts
- schemas
- product result renderer
- separate Chrome Extension using `ce-kit`
- handoff map
- product events

None of this may require changes to `platform-core`.
