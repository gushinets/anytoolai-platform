# MVP-B Freelancer Validation Bundle v0

## Goal

Validate that real web-first Freelancer products can be added after MVP-A1 Atom Runtime Proof and
on the required MVP-A2 Client Surfaces contracts without changing product-neutral execution
contracts.

MVP-B is not a separate backend. It is a validation bundle made from product configs, prompts,
schemas, workflows, web definitions/pages, result renderers, handoff maps, product events, and
runtime E2E evidence.

## In Scope

- product configs;
- product prompts;
- product schemas;
- product workflows;
- product-specific action configs;
- web product definitions and pages hosted by `apps/web-mirror`;
- result renderers;
- handoff maps;
- product events;
- deterministic fixtures and complete browser/runtime E2E evidence.

Dedicated Chrome Extensions are optional follow-up surfaces. Add one only when browser-context
capture or extension distribution is a validated product requirement.

## Validation Set

MVP-B validates six products in this order:

1. ProposalAI: `A06` / `text.compose_persuasive_text`.
2. Client Update Writer: `A07` / `text.compose_reply`, with PrepaidRequest and ReplyDraft as modes.
3. Brief Decoder: `A01 + A04 -> A05`, results to `A10`.
4. Acceptance Builder: `A01 + A11` or `A02`, results to `A10`.
5. Task Finder: `A11 + A02`, with `A01` and `A09` optional.
6. Send-Ready: `A04 + A03`, then a user-selected gap to `A08` in a second scenario run.

ProposalAI proves the shortest complete web path. Client Update Writer proves real reuse before
shared UI is extracted. Brief Decoder and Acceptance Builder prove one `immediate` same-tab handoff.
Task Finder proves score-based value delivery. Send-Ready proves the two-run selected-gap flow
without mapping DSL array indexing.

The 21 concepts in `atom-ready-product-inventory.md` remain a capability inventory. They are not an
alternative MVP-B release train.

## Product Delivery Shape

Each validation product needs two independently reviewable outcomes:

1. `Bundle And Workflow`: product config, prompts, strict schemas, workflow, action configs,
   renderer contract, events, handoff contracts where applicable, and deterministic fixtures.
2. `Web Runtime E2E And QA`: product page in `apps/web-mirror` and the complete web -> shared client
   -> API -> scenario -> workflow -> result -> activation/handoff proof.

This is a delivery boundary, not a requirement to create a fixed number of Linear child issues.
Product planning may split work further when a reviewable vertical requires it.

Bundle work depends on MVP-A1 and the required atom packs. Web work depends on the bundle and the
required MVP-A2 client-event, result-rendering, product-host, and handoff slices.

## Handoff Validation

The first required handoff is:

```text
Brief Decoder -> Acceptance Builder
```

It reuses the existing backend-owned bearer token, safe preview, acceptance, expiry, replay
protection, and source/target session linkage. Navigation stays in the same tab and the target start
policy is `immediate`.

The CTA means "create draft". Acceptance queues Acceptance Builder immediately; editing the result
is local editing or a new ordinary scenario run, not deferred continuation.

Later supported handoff candidates include:

```text
Task Finder -> ProposalAI
ProposalAI -> Send-Ready
```

Deferred handoff continuation is outside the first validation set.

## Platform Boundary

Product delivery must not:

- add Freelancer meaning to `platform-core`;
- change atoms, action runner, workflow runner, Provider Gateway, scenario/quota/handoff runtime, or
  mapping DSL;
- add product-specific backend endpoints;
- copy shared client transport or state-management code into product pages.

Product-neutral Client Surfaces enablement may add the allowlisted `POST /v1/client-events`
contract, platform event types, shared client support, and tests. That work belongs to MVP-A2 and is
not product-specific MVP-B runtime behavior.

If a product needs a missing generic execution capability, update the controlling platform contract
explicitly rather than hiding the change inside the product bundle. If a second product repeats
frontend behavior, extract only that proven repetition into the shared web runtime.

## Definition Of Done

MVP-B validation is complete when all six products have:

- a validated product bundle and workflow;
- a working web page using frontend-safe Platform API contracts;
- product-specific activation defined with its producer and blind spots;
- deterministic runtime and browser E2E evidence;
- no product semantics or provider/model decisions in shared frontend or Platform Core code.
