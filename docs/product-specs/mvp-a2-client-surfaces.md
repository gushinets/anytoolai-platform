# MVP-A2 Client Surfaces

## Goal

Deliver shared browser client contracts and the multi-product web host over the frontend-safe
Platform Core contracts proven by MVP-A1. The host supports web-first product validation; the
kernel-demo Chrome Extension remains a reference integration. MVP-A2 does not own product meaning,
workflow execution, provider selection, prompts, artifacts, quota authority, or handoff state.

## Ownership

Client Surfaces owns:

- shared `packages/frontend/ce-kit` transport, storage, identity, quota, start, polling, result, and
  handoff helpers;
- `apps/web-mirror` product, result, handoff-consent, paywall, and onboarding routes;
- shared product-run behavior inside the web host, without product-specific definitions;
- shared `web-result-kit` rendering components;
- the reference `kernel-demo-ce`;
- frontend integration and browser evidence.

Platform Core owns every backend API and authoritative runtime transition. Freelancer Suite owns
product configs, prompts, schemas, workflows, action configs, web definitions/pages, renderer
meaning, events, and handoff maps. Dedicated product Chrome Extensions remain optional and
product-owned when justified.

## Required Client Contracts

- A15a: `PlatformApiClient`, async storage, guest identity, runtime config, safe errors.
- A15b: quota, idempotent scenario start, bounded session polling, next actions.
- A15c: `getResult()` over `GET /v1/results/{artifact_id}`.
- A18a: create-handoff and consent-navigation CE helpers.
- A18b: safe web handoff consent and terminal states.
- A18c: client handoff integration smoke.

Web product pages and optional product extensions use these contracts. Web pages are composed by
`apps/web-mirror`; extensions may open shared result or consent routes but do not own their backend
state.

## Multi-Product Web Host

Required routes:

- `/products/{product_id}` renders an enabled product's input/run/result journey;
- `/r/{artifact_id}` renders a normalized frontend-safe result;
- `/handoff/{handoff_token}` renders backend safe preview and accept/decline/terminal states;
- `/paywall/{product_id}` uses Platform Core email/paywall intent contracts;
- `/onboarding/{product_id}` provides product-safe install/continue state.

The host composes shared product-run behavior with product-owned definitions. Shared runtime must not
import individual products or contain Freelancer semantics. The composition layer may import both.
No new frontend package or generic page builder is required before another application needs the
same proven runtime.

The host must not expose raw/debug artifacts, prompts, provider/model identifiers, provider-call
rows, PydanticAI traces, or LiteLLM response identifiers. It is not a dashboard or account system.

Web-to-web handoff keeps the backend-owned token and uses same-tab navigation. The first validation
set uses only `immediate` target start; deferred continuation has no v1 frontend path.

## Definition Of Done

- Shared client contracts cover guest identity → quota → idempotent start → poll → result, next
  actions, client events, and handoff helpers.
- Frontend typecheck, unit/integration tests, generated contract drift check, and builds pass.
- Web product, result, consent, paywall, onboarding, loading, not-found, and safe-error states are
  covered.
- Kernel demo CE runs the reference client journey without bundled runtime decisions.
- Browser evidence is linked through the Client Surfaces release gate.

## Out Of Scope

- Chrome Web Store publishing;
- registered authentication, billing, subscriptions, or account dashboards;
- product-specific prompts, workflows, schemas, product definitions/pages, or product Chrome
  Extensions;
- provider/model controls, direct provider calls, or raw provider output;
- broad visual polish beyond MVP proof.
