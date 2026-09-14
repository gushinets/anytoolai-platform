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

MVP-B validates five products in this order:

1. ProposalAI: `A06` for v1; `A09 -> A06` remains a later option.
2. Client Message Decoder: `A01 -> A07`, with `A04` optional.
3. Scope Creep Guard: `A11 -> A07`; comparison results and request data to `A10`.
4. Send-Ready: `A04 + A03`, then a user-selected gap to `A08` in a second scenario run.
5. Brief Decoder: `A01 + A04 -> A05`, results to `A10`.

The release order follows product demand priorities: ProposalAI addresses the most frequent
customer pain; Client Message Decoder combines frequent need with fear of making a mistake;
Scope Creep Guard and Send-Ready have preliminary demand validation; Brief Decoder has high value
across projects. These priority reasons were supplied by the product owner on 2026-09-08.

ProposalAI proves the shortest complete web path; the shared web product runtime foundation is
extracted directly from that single implementation once it proves which parts are product-neutral,
under a foundation-first ownership split approved by the product owner on 2026-09-08 so no product
in this order waits on another product's completion to start its own web implementation. Client
Message Decoder proves the published foundation contract holds unchanged for an independently
built second product. Scope Creep Guard proves scope comparison, reply, and document generation.
Send-Ready proves the two-run selected-gap flow without extending the mapping DSL. Brief Decoder
completes the initial set with brief analysis, questions, and a document.

Client Update Writer, Acceptance Builder, and External Task Finder & Fit remain in the capability
backlog without a committed release order. Brief Decoder to Acceptance Builder remains a later
handoff candidate, not a dependency of the initial five-product release set.

The 21 concepts in `atom-ready-product-inventory.md` remain a capability inventory, not an
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

No product-to-product handoff pair is a mandatory dependency of the initial five-product release
order. Shared handoff contracts and MVP-A2 browser proof remain required in their own scope.

Later handoff candidates include:

```text
ProposalAI -> Send-Ready
Brief Decoder -> Acceptance Builder
External Task Finder & Fit -> ProposalAI
```

Any delivered handoff reuses the existing backend-owned bearer token, safe preview, acceptance,
expiry, replay protection, and source/target session linkage. Navigation stays in the same tab and
the target start policy is `immediate`. Deferred continuation remains outside the first validation set.

For the later Brief Decoder to Acceptance Builder flow, the CTA means "create draft". Acceptance
queues Acceptance Builder immediately; editing the result is local editing or a new ordinary
scenario run, not deferred continuation.

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

MVP-B validation is complete when all five products have:

- a validated product bundle and workflow;
- a working web page using frontend-safe Platform API contracts;
- product-specific activation defined with its producer and blind spots;
- deterministic runtime and browser E2E evidence;
- no product semantics or provider/model decisions in shared frontend or Platform Core code.
