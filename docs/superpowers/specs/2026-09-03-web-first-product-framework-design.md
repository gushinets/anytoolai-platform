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
  renderResult: ResultRenderer;
};
```

The definition may describe text, select, numeric, and boolean fields with simple client validation. It must not contain system prompts, provider/model choices, or workflow logic.

### Shared product page

The first `ProductRunPage` is implemented together with ProposalAI and owns:

1. rendering and validating the product form;
2. resolving guest identity and quota;
3. starting a configured scenario through `ce-kit`;
4. bounded polling until a terminal state;
5. fetching the frontend-safe result artifact;
6. rendering, copying, retrying, and invoking allowed next actions;
7. emitting allowlisted client events.

Client Update Writer then reuses this behavior. Only repetition demonstrated by those two products
is extracted into shared internal components; no generic framework is built ahead of them.

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

### Web handoff

Web-to-web handoff reuses the existing backend-owned bearer token, safe preview, expiry, replay
protection, acceptance, and source/target session linkage. Consent and target navigation stay in the
same tab; the web host does not introduce a simplified handoff contract.

The initial validation set supports only `immediate` target start. Brief Decoder to Acceptance
Builder is the first required pair. Its CTA is "create draft": acceptance queues Acceptance Builder
immediately. Editing after the result appears is local editing or a new ordinary scenario run, not
deferred continuation. Deferred handoff remains outside v1 because an accepted deferred target has
no frontend start path.

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

The existing platform taxonomy also includes:

- `guest.created`
- `quota.*`
- `scenario.*`
- `workflow.*`
- `action.*`
- `artifact.created`
- `handoff.*`
- `client.result_copied` (reserved; no live producer; excluded from v1 metrics)
- `client.next_action_clicked`
- `paywall.shown`
- `email_capture.submitted`
- `waitlist.intent_submitted`

Each product defines one activation independently of its page implementation. ProposalAI activation
is successful use of its copy button. The browser first completes the clipboard write and then calls
the existing scenario next action `copy_result`; the backend records
`client.next_action_clicked` with `next_action_id=copy_result`. A failed next-action request does not
undo or hide an already successful clipboard operation, so this metric may undercount. Manual
selection and `Ctrl+C` are outside its observable boundary.

`client.result_copied` stays reserved so the existing taxonomy remains stable. If it later gets a
live producer, activation queries count at most one copy activation per `scenario_session_id` and
prefer `client.result_copied` over `client.next_action_clicked(copy_result)` during migration. The
two event shapes must never count one copied result twice.

## Metric Contract

Every reported metric definition records four fields:

- `definition`: the exact numerator, denominator, filters, and time window;
- `producer`: the service or browser interaction that creates the source event;
- `trust_class`: one closed value from the list below;
- `blind_spots`: behavior that the producer cannot observe or may undercount.

Allowed `trust_class` values are:

```text
backend_produced
backend_recorded_client_action
client_observed
derived
```

This classification belongs to the metric contract, not to each `event_log` row. V1 does not add a
metric registry, confidence score, database column, or analytics schema.

The shared operational metrics are:

| Metric | Definition | Producer | Trust class | Blind spots |
|---|---|---|---|---|
| `value_produced` | Count distinct completed `scenario_session_id` values correlated with their canonical result artifact, by product and time window. | Scenario/workflow runtime | `backend_produced` | A generated result may never be consumed. A completed scenario without its canonical artifact is an invariant violation and data-quality alert, not another completion category. |
| `activation` | Count distinct completed `scenario_session_id` values that satisfy the product-specific value-taking condition, by product and time window. | Derived from the product-specific producer below | `derived` | Inherits that producer's trust and blind spots. Different products may use different producer classes, so activations are not summed into a portfolio north-star in v1. |
| `value_take_rate` | Activated scenario sessions divided by `value_produced` scenario sessions for the same product, cohort, and time window. | Derived from the two metrics above | `derived` | Inherits identity, delivery, and producer blind spots; denominator zero yields no value rather than zero percent. |
| `activation_gap` | `value_produced` scenario sessions minus activated scenario sessions for the same product, cohort, and time window. | Derived from the two metrics above | `derived` | It signals produced-but-not-taken value but does not explain why the user stopped. |

The validation products use these activation definitions:

| Product | Activation definition | Producer | Trust class | Blind spots |
|---|---|---|---|---|
| ProposalAI | First successful copy-button action for a completed ProposalAI scenario. | `client.next_action_clicked(copy_result)` after clipboard success | `backend_recorded_client_action` | Misses manual copying and may undercount when the next-action request fails. |
| Client Update Writer | First successful copy-button action for a completed update, including PrepaidRequest and ReplyDraft modes. | `client.next_action_clicked(copy_result)` after clipboard success | `backend_recorded_client_action` | Same copy-button boundary as ProposalAI. |
| Brief Decoder | First successful rendering of a non-empty clarifying-question result. | `web.result_viewed` correlated with the completed scenario | `client_observed` | Browser delivery can fail; rendering does not prove a question was used. |
| Acceptance Builder | First successful rendering of its acceptance verdict and criteria. | `web.result_viewed` correlated with the completed scenario | `client_observed` | Rendering does not prove the criteria were accepted or applied. |
| Task Finder | First successful rendering of its fit score. | `web.result_viewed` correlated with the completed scenario | `client_observed` | Rendering does not prove that the user acted on the score. |
| Send-Ready | First successful copy-button action on the rewrite result from the second run. | `client.next_action_clicked(copy_result)` after clipboard success | `backend_recorded_client_action` | Excludes users who use the diagnosis without generating or copying a rewrite. |

These are operational metrics, not two competing north-stars. A portfolio north-star is selected
only after observed product behavior shows that the activation definitions are comparable.
Identity-level activation rate may be defined later as a separate metric with its own cohort,
eligibility, producer, trust, and blind-spot contract.

## Identity And Sessions

`active_identity` is `user_id` when authenticated identity exists; otherwise it is the backend-issued
`guest_id`. The current guest id stored in browser local storage is device-local. Guest DAU,
retention, and activation are therefore labeled device-local and must not be presented as user-level
or cross-device metrics.

The browser creates an opaque `web_session_id` and rotates it after 30 minutes of inactivity. It
lives in the existing event `properties` JSON for v1. Session duration is approximate: the first and
last observed events bound activity but do not prove attention between them.

## Metrics Coverage

### Signals available for later metric definitions

The event set preserves inputs that may support the following metrics. V1 does not report them until
each receives the same explicit definition, producer, trust class, and blind-spots contract used
above:

- product views, form starts, and form submissions;
- scenario completion and failure rates;
- activation rate by product;
- product time to value, measured from first product view to first activation;
- device-local guest DAU, MAU, DAU/MAU, D1, and D7 retention;
- user-level activity and retention after authenticated `user_id` exists;
- feature and mode adoption;
- sessions per identity using the 30-minute inactivity boundary;
- approximate active session duration;
- onboarding completion;
- result view and copy rates;
- retry and second-run conversion;
- handoff conversion;
- quota-to-email and quota-to-waitlist conversion.

PQL is not reported until an explicit product-level rule, producer, and identity boundary are
defined. The presence of potentially useful events alone does not make PQL available.

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

1. Align the controlling Client Surfaces and MVP scope documents for web-first ownership.
2. Add the allowlisted client-event ingestion contract, event taxonomy, and real shared client call.
3. Complete the real `/r/{artifact_id}` result renderer.
4. Implement ProposalAI and the minimum product-run behavior together in `apps/web-mirror`.
5. Add the complete ProposalAI funnel and copy-button activation path with persisted correlation.
6. Build Client Update Writer on the same route/runtime pattern.
7. Extract only the repetition proven by both products into shared internal components.
8. Build Brief Decoder, Acceptance Builder and their immediate same-tab handoff.
9. Build Task Finder, then Send-Ready as the two-run validation product.

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
- `value_produced`, per-product activation, `value_take_rate`, and `activation_gap` can be calculated
  from stored events using compatible scenario-session units and the documented trust boundaries.
- No atom, workflow mapping, provider, or model-selection contract changes.
- No analytics dashboard or unsupported SaaS metric is included in the first release.
