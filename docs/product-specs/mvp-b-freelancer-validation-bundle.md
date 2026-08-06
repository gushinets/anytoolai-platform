# MVP-B Freelancer Validation Bundle v0

## Goal

Validate that real CE-first Freelancer products can be added after MVP-A1 Atom Runtime Proof and on
the required MVP-A2 CE-kit contracts without changing `platform-core`.

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

Each product has one coordinating Linear parent and exactly three delivery children:

1. `<Product> Bundle And Workflow` owns product config, prompts, strict schemas, workflow, renderer
   contract, events, handoff contracts, and deterministic fixtures.
2. `<Product> Chrome Extension` owns the dedicated manifest and product UX using
   `packages/frontend/ce-kit`.
3. `<Product> Runtime E2E And QA` owns the complete CE → CE-kit → API → scenario → workflow →
   result → copy/handoff proof.

The parent completes only when all three children complete. Bundle children depend on B01 and the
required MVP-A1 atom packs. Chrome Extension children depend on their bundle and the required
MVP-A2 CE-kit slices, but never on web mirror. Runtime E2E children depend on bundle plus CE and,
where configured, the B06 handoff map and A18 client handoff integration.

## Product Order

After MVP-A1, all 11 atom action types are proven individually and in composite workflows. MVP-B
should mostly be prompts, schemas, workflows, CE UX, renderers, fixtures, and handoff maps.

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

Every product extension completes through CE-kit scenario polling and the frontend-safe result API.
Opening a result in web mirror is optional MVP-A2 integration, not product Definition of Done.

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

If a product bundle requires changing core, update MVP-A1 contracts first; the kernel was not
complete enough. If multiple extensions require missing shared client behavior, update MVP-A2
Client Surfaces rather than duplicating it in product extensions.
