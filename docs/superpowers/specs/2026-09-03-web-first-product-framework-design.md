# Web-First Product Framework And Analytics Design

Date: 2026-09-03  
Status: approved design boundary

## Decision

AnytoolAI is web-first. The existing `apps/web-mirror` becomes the shared host for product pages as well as result, handoff, onboarding, and paywall routes.

The first version is a narrow runtime for text-first products, not a generic application builder. It reuses existing Platform API contracts, `ce-kit`, `shared-ui`, and `web-result-kit`. Product atoms, workflows, provider selection, and prompts remain backend-owned.

Analytics is events-first: the framework records truthful raw events with stable correlation dimensions. Derived SaaS metrics are calculated outside the product page. Metrics that require billing, marketing, CRM, survey, support, or accounting data remain unavailable until those sources exist.

## Goals

- Give every product the same web journey: input → scenario start → polling → result → next action.
- Keep each product responsible only for its fields, validation, scenario identity, modes, and result presentation.
- Collect a consistent product funnel without storing user text, prompts, or generated content in analytics.
- Support one-run and user-approved two-run workflows without changing atoms or the mapping DSL.
- Prove the framework with ProposalAI, then reuse it for Client Update Writer.

## Non-Goals

- A schema-driven no-code page builder.
- A dashboard, account system, run history, or workflow editor.
- Billing, CRM, marketing-spend, support, survey, or accounting integrations.
- Computing all SaaS metrics inside the request path.
- Renaming `ce-kit` or extracting a new frontend package before another application needs the runtime.
- File ingestion, PDF extraction, or OCR.

## Current State

`apps/web-mirror` currently owns result, handoff, paywall, and onboarding routes. It does not provide product input pages or start scenarios. The `/r/{artifact_id}` route still returns temporary static content.

The reusable pieces already exist:

- `ce-kit`: identity, quota, scenario start, polling, results, next actions, and local-storage support;
- `shared-ui`: basic controls and feedback states;
- `web-result-kit`: normalized text and structured-result rendering;
- Platform Core event log: durable events, correlation dimensions, sanitized JSON properties, and idempotent `event_id` primary keys;
- Platform API: scenario, result, quota, handoff, and access-lite contracts.

## Architecture

### Product routes

Product pages use `/products/{product_id}` inside `apps/web-mirror`. A static registry maps a supported `product_id` to its product definition. Unknown or disabled products return a safe not-found state.

The first implementation remains internal to `apps/web-mirror`; no new frontend package is created. Extraction is justified only if a second application needs the same runtime.

### Product definition

Each product supplies a small static TypeScript definition:

```ts
type WebProductDefinition = {
  productId: string;
  scenarioId: string;
  title: string;
  description: string;
  fields: ProductField[];
  modes?: ProductMode[];
  activationEvent: string;
  renderResult: ResultRenderer;
};
```

The definition may describe text, select, numeric, and boolean fields with simple client validation. It must not contain system prompts, provider/model choices, or workflow logic.

### Shared product page

`ProductRunPage` owns:

1. rendering and validating the product form;
2. resolving guest identity and quota;
3. starting a configured scenario through `ce-kit`;
4. bounded polling until a terminal state;
5. fetching the frontend-safe result artifact;
6. rendering, copying, retrying, and invoking allowed next actions;
7. emitting allowlisted client events.

The page state is deliberately small:

```text
idle → editing → submitting → running → completed
                          ↘ failed
                          ↘ quota_exhausted
```

For a two-run product:

```text
completed → user selects a gap → second scenario start → completed
```

The selected gap is sent as a string in the second scenario input. Array indexing is not added to the mapping DSL.

### Result rendering

The framework supports the result shapes already produced by the atoms:

- generated text;
- scores and criteria;
- issue lists;
- clarifying questions;
- rewrite variants;
- structured documents.

Product-specific renderers may compose these primitives. Raw debug artifacts and provider metadata remain inaccessible.

## Client Event Contract

Platform API adds one authenticated-or-guest endpoint:

```text
POST /v1/client-events
```

The request contains:

- an idempotent client-generated `event_id`;
- an allowlisted `event_type`;
- `product_id` and `frontend_id`;
- a client `web_session_id` stored in event properties;
- optional `scenario_session_id` when the event follows a run;
- optional allowlisted scalar properties such as mode, field count, or gap category.

The server supplies its own receipt timestamp and derives tenant, region, guest/user identity, and correlated runtime dimensions. It rejects unknown event types, invalid product/frontend combinations, oversized payloads, unsupported property values, and attempts to submit sensitive content.

No event may contain source text, form values, prompts, model output, full URLs with query strings, credentials, or free-form error bodies. Acquisition fields are limited to normalized referrer domain, campaign identifiers, and UTM values.

`web_session_id` stays in the existing JSON `properties` column for v1. No database migration is needed until query volume proves that a dedicated indexed column is necessary.

## Event Taxonomy

The initial web events are:

- `web.product_viewed`
- `web.form_started`
- `web.form_submitted`
- `web.result_viewed`
- `web.retry_clicked`
- `web.mode_selected`
- `web.gap_selected`
- `web.feedback_submitted`
- `onboarding.started`
- `onboarding.completed`

Existing events continue to represent backend truth:

- `guest.created`
- `quota.*`
- `scenario.*`
- `workflow.*`
- `action.*`
- `artifact.created`
- `handoff.*`
- `client.result_copied`
- `client.next_action_clicked`
- `paywall.shown`
- `email_capture.submitted`
- `waitlist.intent_submitted`

Each product defines one activation event. ProposalAI activation is the first successfully viewed generated proposal; copying the result is a stronger downstream signal, not the activation prerequisite.

## Metrics Coverage

### Available from platform and web events

- product views, form starts, and form submissions;
- scenario completion and failure rates;
- activation rate by product;
- product time to value, measured from first product view to first activation;
- DAU, MAU, and DAU/MAU using a documented definition of active identity;
- feature and mode adoption;
- sessions per identity using an inactivity-based session boundary;
- approximate active session duration;
- onboarding completion;
- result view and copy rates;
- retry and second-run conversion;
- handoff conversion;
- quota-to-email and quota-to-waitlist conversion;
- PQL signals once explicit rules are defined.

### Requires future external sources

| Metric group | Required source |
|---|---|
| MRR, ARR, expansion, contraction, revenue churn, trial-to-paid | Billing and subscription ledger |
| Customer/logo retention and churn | Registered accounts plus subscription lifecycle |
| CAC, paid CAC, LTV:CAC, lead velocity | Marketing spend and attribution |
| LTV, ARPU, ARPA, ACV, gross margin | Billing, accounts, contracts, and cost allocation |
| NPS, CSAT, CES, customer health | Survey responses plus identity linkage |
| Support volume, response time, resolution rate | Support system |
| Win rate, sales cycle, pipeline, MQL-to-SQL | CRM |
| Burn, runway, Rule of 40, Magic Number, Quick Ratio, OpEx | Accounting and finance systems |

The framework preserves join keys for future enrichment but does not fabricate unavailable metrics.

## Error And Privacy Rules

- Product pages display only frontend-safe error codes and recovery actions.
- Duplicate client events are harmless because `event_id` is idempotent.
- Analytics failure never blocks the product result; failed event delivery may retry with a small bounded queue.
- Scenario start remains idempotent under the existing `ce-kit` contract.
- Client timestamps are advisory; server receipt time is canonical.
- Event properties use the existing sanitizer and a stricter endpoint-level allowlist.
- Free-form user content is prohibited in analytics and covered by tests.

## Delivery Sequence

1. Update the controlling Client Surfaces and MVP scope documents for web-first ownership.
2. Add the allowlisted client-event ingestion contract and event taxonomy.
3. Implement the ProposalAI product route directly in `apps/web-mirror` using existing kits.
4. Complete the real `/r/{artifact_id}` result renderer.
5. Add ProposalAI funnel events and validate their persisted dimensions.
6. Build Client Update Writer on the same route/runtime pattern.
7. Extract only the repetition proven by both products into shared internal components.
8. Continue the approved web-first product order.

## Verification

- Config validation covers every new event type.
- API tests prove event allowlisting, idempotency, server-derived dimensions, size limits, and sensitive-property rejection.
- Frontend tests cover form validation, running, success, safe error, quota, retry, copy, and analytics-failure states.
- ProposalAI browser E2E proves form → scenario → polling → result → copy.
- Event-log assertions prove the complete ProposalAI funnel and correlation identifiers.
- Existing architecture, docs, frontend, and backend checks remain green.

## Acceptance Criteria

- ProposalAI can be completed entirely from a web page without a Chrome Extension.
- A second product can reuse the runtime without copying transport or state-management logic.
- All defined web events are durable, idempotent, correlated, allowlisted, and content-free.
- Activation, time to value, completion rate, and result-copy rate can be calculated from stored events.
- No atom, workflow mapping, provider, or model-selection contract changes.
- No analytics dashboard or unsupported SaaS metric is included in the first release.
