# MVP-A2 Client Surfaces

## Goal

Deliver the shared web and Chrome client surfaces over the frontend-safe Platform Core contracts
proven by MVP-A1. MVP-A2 does not own workflow execution, provider selection, prompts, artifacts,
quota authority, or handoff state.

## Ownership

Client Surfaces owns:

- shared `packages/frontend/ce-kit` transport, storage, identity, quota, start, polling, result, and
  handoff helpers;
- `apps/web-mirror` result, handoff-consent, paywall, and onboarding pages;
- shared `web-result-kit` rendering components;
- the reference `kernel-demo-ce`;
- frontend integration and browser evidence.

Platform Core owns every backend API and authoritative runtime transition. Freelancer Suite owns
product configs, prompts, schemas, renderers, events, handoff maps, and eight product-specific
Chrome Extensions.

## Required Client Contracts

- A15a: `PlatformApiClient`, async storage, guest identity, runtime config, safe errors.
- A15b: quota, idempotent scenario start, bounded session polling, next actions.
- A15c: `getResult()` over `GET /v1/results/{artifact_id}`.
- A18a: create-handoff and consent-navigation CE helpers.
- A18b: safe web handoff consent and terminal states.
- A18c: client handoff integration smoke.

Product extensions use these contracts but do not depend on web mirror. A web result link is an
optional integration. Handoff consent is the only journey that intentionally opens a shared web
surface.

## Web Mirror

Required routes:

- `/r/{artifact_id}` renders a normalized frontend-safe result;
- `/handoff/{handoff_token}` renders backend safe preview and accept/decline/terminal states;
- `/paywall/{product_id}` uses Platform Core email/paywall intent contracts;
- `/onboarding/{product_id}` provides product-safe install/continue state.

Web mirror must not expose raw/debug artifacts, prompts, provider/model identifiers, provider-call
rows, PydanticAI traces, or LiteLLM response identifiers. It is not a dashboard or account system.

## Definition Of Done

- CE-kit covers guest identity → quota → idempotent start → poll → result and shared handoff helpers.
- Frontend typecheck, unit/integration tests, generated contract drift check, and builds pass.
- Web result, consent, paywall, onboarding, loading, not-found, and safe-error states are covered.
- Kernel demo CE runs the reference client journey without bundled runtime decisions.
- Browser evidence is linked through the Client Surfaces release gate.

## Out Of Scope

- Chrome Web Store publishing;
- registered authentication, billing, subscriptions, or account dashboards;
- product-specific prompts, workflows, schemas, or product Chrome Extensions;
- provider/model controls, direct provider calls, or raw provider output;
- broad visual polish beyond MVP proof.
