# ADR 0008: Web-First Multi-Product Host

## Status

Accepted. Product release order updated on 2026-09-08 to match
`docs/product-specs/mvp-scope-source-of-truth.md`.

Amended 2026-09-08: the product owner approved a foundation-first ownership split. The shared
`product-runtime` module inside `apps/web-mirror` (the "generic frontend framework" this ADR's
Context/Decision/Follow-up describe below) is extracted directly from ProposalAI alone, as its own
deliverable, before a second product exists -- not after Client Message Decoder independently
re-implements the same pattern. This corrects this ADR's original sequencing below (Context's
"before two products prove the same need", Decision's "implement Client Message Decoder on the
same pattern, and extract only repetition demonstrated by both", and Follow-up's "Use Client
Message Decoder to prove which frontend behavior is genuinely reusable"), so that no product in
the release order waits on another product's completion to start its own web implementation. The
internal-module-vs-standalone-package boundary this ADR draws is unaffected: the foundation stays
inside `apps/web-mirror`, not a new frontend package, exactly as Decision already describes.

## Context

ADR-0005 requires a separate Chrome Extension for each MVP-B product. That decision keeps extension
manifests and product UX isolated while sharing `ce-kit` and the backend runtime.

The first product-validation surface is now the web. Creating a separate web application for every
thin text-first product would duplicate routing, identity, quota, scenario polling, result rendering,
next actions, and analytics. Extracting a generic frontend framework before two products prove the
same need would create an unvalidated abstraction.

The existing `apps/web-mirror` already owns web result, handoff-consent, paywall, and onboarding
routes and consumes frontend-safe Platform API contracts. It is the smallest existing composition
root that can also host product run pages.

## Decision

Use `apps/web-mirror` as the shared multi-product web host.

Product pages use routes under:

```text
/products/{product_id}
```

The host composes two kinds of frontend code:

```text
product-runtime
  shared form/run/poll/result/next-action behavior

products/{product_id}
  product-owned fields, validation, modes, copy, scenario identity, and result presentation
```

The composition layer may import both. Shared `product-runtime` code must not import individual
product definitions or contain Freelancer product meaning. Product definitions may consume the
shared runtime and frontend-safe client contracts.

Do not create a new frontend package or schema-driven application builder for the first product.
Implement ProposalAI in the host, implement Client Message Decoder on the same pattern, and extract
only repetition demonstrated by both. A shared package is justified only when a second application,
outside `apps/web-mirror`, needs the same runtime.

Web pages are the default product Definition of Done for the initial validation set. A dedicated
Chrome Extension is later and optional unless a product explicitly proves that browser-context
capture or extension distribution is required.

ADR-0005 remains valid for products that are delivered as Chrome Extensions. ADR-0008 supplements
it with the composition rule for web delivery; it does not place multiple products inside one
extension.

## Runtime boundaries

The web host may:

- collect and validate product input;
- use existing frontend-safe identity, quota, scenario, result, next-action, and handoff contracts;
- render normalized result artifacts;
- emit allowlisted client events;
- navigate between product routes.

The web host must not:

- contain system prompts or provider/model selection;
- construct or alter workflows;
- own authoritative scenario, quota, artifact, event, or handoff state;
- import backend product bundles;
- add Freelancer semantics to Platform Core.

Product configs, prompts, schemas, workflows, action configs, renderer meaning, and handoff maps
remain product-owned. Atoms, action/workflow runners, Provider Gateway, runtime state, and the
mapping DSL remain platform-owned.

## Handoff

Web-to-web handoff reuses the existing backend-owned bearer-token contract, including safe preview,
expiry, replay protection, acceptance, and source/target session linkage. Web navigation uses the
same tab; it does not introduce a second simplified handoff path.

The initial five-product order does not require a product-to-product handoff pair.
Any delivered web handoff uses only `immediate` target-start policies. Acceptance queues the
target workflow and returns the user to the target product state in the same tab. Deferred target
continuation remains outside the first release because no frontend start path currently exists for
an accepted deferred target session.

For the later Brief Decoder to Acceptance Builder candidate, the consent action means "create draft",
not final approval of acceptance criteria. Editing after the target result appears is local editing or a new ordinary
scenario run; it is not deferred continuation of the accepted handoff.

## Consequences

Positive:

- the first product reuses an existing deployable web application;
- products share one proven browser runtime without copying transport and state-management code;
- product semantics stay outside the shared runtime and Platform Core;
- Chrome Extensions can be added later without redefining backend contracts;
- shared MVP-A2 handoff proof remains valid without extending the handoff runtime.

Negative / accepted tradeoffs:

- `apps/web-mirror` becomes a broader web host despite its historical name;
- the composition root knows the registry of enabled web products;
- product isolation is architectural rather than process-level deployment isolation;
- deferred handoff and extension-specific context capture are not proven by the first web release.

## Follow-up

- Follow the web-first release order: ProposalAI, Client Message Decoder, Scope Creep Guard,
  Send-Ready, Brief Decoder.
- Implement ProposalAI as the first vertical web slice.
- Use Client Message Decoder to prove which frontend behavior is genuinely reusable.
- Revisit package extraction only after another application needs the proven runtime.
