# MVP-B Freelancer Validation Bundle v0

## Goal

Validate that real CE-first Freelancer products can be added on top of Platform Kernel without changing `platform-core`.

MVP-B is not a separate backend. It is a validation bundle made from product configs, prompts, schemas, workflows, CE wrappers, result renderers, handoff maps, and product events.

## In Scope

- product configs
- product prompts
- product schemas
- product workflows
- product-specific action configs
- CE wrappers
- CE product UX
- result renderers
- handoff maps
- product events

## Product Set

MVP-B contains eight thin Freelancer validation products:

- ProposalAI
- Acceptance Builder
- Case Study
- Scope Guard
- Task Finder
- Send-Ready
- Brief Decoder
- Persuasion Lens

Each product should have product-specific config under the Freelancer Suite bundle and a separate Chrome Extension wrapper that uses `packages/frontend/ce-kit`.

## Product Order

After MVP-A, all 11 atom action types already exist. MVP-B should mostly be prompts, schemas, workflows, CE UX, and handoff maps.

Recommended order:

1. ProposalAI: `A06` / `text.compose_persuasive_text`
2. Acceptance Builder: `A01 + A07 + A10`
3. Case Study + Upsell: `A01 + A09 + A07 + A10`
4. Scope Guard: `A01 + A04 + A11 + A07`
5. Task Finder: `A01 + A11 + A02 + A09`
6. Send-Ready: `A04 + A11 + A02 + A08`
7. Brief Decoder: `A01 + A04 + A05 + A10`
8. Persuasion Lens: `A03 + A04 + A09 + A08 + A06`

ProposalAI should be the first real product after the kernel because it has one workflow, one atom, a clear CE surface, and a quick `result copied` aha moment.

## Handoff Examples

Real Freelancer handoffs appear in MVP-B, including:

- Task Finder -> ProposalAI
- ProposalAI -> Send-Ready
- Brief Decoder -> Scope Guard
- Brief Decoder -> Acceptance Builder

## Rule

MVP-B must not change Platform Kernel.

Allowed:

- add `product.yaml`
- add `scenarios.yaml`
- add `workflows.yaml`
- add `action_configs.yaml`
- add prompts
- add schemas
- add CE result renderer
- add handoff map

Undesirable:

- changing workflow runner
- changing action runner
- adding product-specific backend endpoints
- adding Freelancer-specific code in `platform-core`

If a product requires changing core, update MVP-A contracts first; the kernel was not complete enough.
