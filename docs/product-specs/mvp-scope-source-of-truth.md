# MVP Scope Source Of Truth

This file is the repository-local controlling source for current AnytoolAI MVP-A and MVP-B scope.
It supersedes conflicting delivery-order and client-surface statements in the earlier concept file:

```text
D:\Work\AI\AnytoolAI\platform concept\anytoolai-mvp-a-platform-kernel-and-mvp-b-freelancer-validation-bundle.md
```

Keep `AGENTS.md`, `ARCHITECTURE.md`, `docs/**`, configs, tests, and scaffold aligned with this file.
The external concept file is historical context, not a second controlling source.

## Delivery Split

The accepted MVP-A scope is delivered through two sequential milestones:

- **MVP-A1 — Atom Runtime Proof:** the smallest product-neutral backend runtime that can launch all
  11 typed atoms individually and in config-defined composite workflows, persist auditable runtime
  state, and expose normalized results without a UI dependency.
- **MVP-A2 — Client Surfaces:** shared client contracts, the multi-product web host, handoff consent,
  paywall/onboarding, the kernel-demo reference Chrome Extension, and browser evidence over
  frontend-safe Platform Core APIs.

MVP-B is Freelancer Validation Bundle: thin web-first Freelancer products added on top of the
kernel through product configs, prompts, schemas, workflows, result renderers, handoff maps, product
events, and product pages hosted by `apps/web-mirror`.

MVP-B bundle/workflow work may begin after MVP-A1. Web product work depends on the required MVP-A2
client-runtime and result-rendering slices. Dedicated Chrome Extensions are later and optional unless
a product proves that browser-context capture or extension distribution is required. If the first
real Freelancer bundle cannot be added without changing product-neutral execution contracts,
MVP-A1 is not complete.

## MVP-A1 Runtime Flow

```text
Product Definition
-> Scenario Session
-> Workflow Definition
-> Action Configurations
-> Atomic Actions
-> Provider Gateway
-> Structured Output
-> Artifact
-> Event Log
-> Frontend-safe Result API
```

Every user journey starts with `scenario_session_id`.

## MVP-A1 In Scope

- config loader
- product, frontend, scenario, workflow, action, prompt, and provider policy registries
- scenario session runtime
- workflow runner
- action runner
- job model and action run model
- provider call logging
- structured output validation
- artifact storage
- event log
- guest identity and guest quota
- quota exhausted state
- backend-owned handoff token flow
- frontend-safe `GET /v1/results/{artifact_id}`
- deterministic 11/11 standalone atom proof
- three composite workflows covering all 11 atoms
- one `atoms-proof` command and machine-readable evidence
- credentialed 11-atom live-provider canary outside baseline CI

## MVP-A2 In Scope

- shared `packages/frontend/ce-kit`
- shared multi-product web host in `apps/web-mirror`
- web product, result, handoff, paywall, and onboarding pages
- handoff CE helpers and web consent
- email capture/paywall client journey over Platform Core backend contracts
- `kernel-demo-ce`
- frontend build, integration, and browser evidence

## MVP-A Out Of Scope

- real Freelancer products as user releases
- production Chrome Extensions unless separately justified by a product
- admin panel
- billing, Stripe, YooKassa, subscriptions, wallets, ledger
- registered auth via OTP or magic link
- Talent OS
- dashboards
- DSPy as required runtime
- Content Critic
- Spanish Accent Tutor
- file, audio, or video processing
- CRM
- visual workflow builder
- full multitenancy
- full regional deployment
- product-specific domain tables

## Product-Neutral Action Types

All 11 action types must be registered and runnable through the generic action runner.

| Old atom | MVP-A action type |
|---|---|
| A01 `extract_structured` | `text.extract_structured_fields` |
| A04 `detect_issues` | `text.detect_issues_by_taxonomy` |
| A07 `generate_reply` | `text.compose_reply` |
| A09 `generate_angle` | `text.synthesize_angle` |
| A10 `generate_document` | `document.generate_from_template` |
| A11 `compare_classify` | `text.compare_and_classify` |
| A02 `score_match` | `text.score_match_by_rubric` |
| A06 `generate_proposal` | `text.compose_persuasive_text` |
| A08 `generate_rewrites` | `text.generate_gap_rewrites` |
| A03 `score_multidim` | `text.score_multidimensional_axes` |
| A05 `generate_questions` | `text.generate_clarifying_questions` |

`generate_proposal` must not become a platform action type. ProposalAI uses `text.compose_persuasive_text` through a product-specific action config.

## Forbidden In MVP-A Platform Core

Platform Core must not contain product semantics such as:

- `FreelancerProfile`
- `ExternalTask`
- `Proposal`
- `Brief`
- `ScopeCreep`
- `AcceptanceDocument`
- `CaseStudy`
- `RhetoricalAnalysis`
- `Upwork`
- `Gmail compose`
- `client message`
- `proposal angle`
- `send-ready verdict`

Platform Core may know only neutral runtime identifiers such as `product_id`, `frontend_id`, `scenario_id`, `scenario_session_id`, `workflow_id`, `workflow_version`, `action_type`, `action_config_id`, `prompt_ref`, `provider_policy_ref`, `job_id`, `artifact_id`, `handoff_id`, `guest_id`, `tenant_id`, `region`, and `event_type`.

## Runtime State

Definitions live in YAML/Markdown in the repo. Runtime state lives in PostgreSQL.

MVP-A runtime tables:

- `platform.scenario_sessions`
- `platform.jobs`
- `platform.action_runs`
- `platform.provider_calls`
- `platform.artifacts`
- `platform.event_log`
- `platform.guest_identities`
- `platform.guest_quota_usage`
- `platform.email_captures`
- `platform.paywall_intents`
- `platform.product_handoffs`

Do not add DB tables for products, workflow definitions, action definitions, action configurations, prompt versions, subscriptions, wallets, ledger entries, or admin users in MVP-A.

## Minimal API

```text
POST /v1/identity/guest
GET  /v1/products/{product_id}/quota
POST /v1/email-captures
POST /v1/paywall-intents

GET  /v1/products/{product_id}/runtime-config
POST /v1/products/{product_id}/scenarios/{scenario_id}/start
GET  /v1/scenario-sessions/{scenario_session_id}
POST /v1/scenario-sessions/{scenario_session_id}/next-actions/{next_action_id}

GET /v1/jobs/{job_id}
GET /v1/artifacts/{artifact_id}
GET /v1/results/{artifact_id}

POST /v1/handoffs
GET  /v1/handoffs/{handoff_token}
POST /v1/handoffs/{handoff_token}/accept
POST /v1/handoffs/{handoff_token}/decline

POST /v1/client-events
```

MVP-A handoffs are backend-owned bearer-token flows. Only canonical normalized workflow-result
artifacts may feed config-allowlisted context and preview mappings. User acceptance creates an
auditable linked target session; only an `immediate` config policy queues the target workflow.

## Kernel Demo

`kernel_demo` is an internal smoke-test product only. It is not a user product and not part of Freelancer Suite.

Required smoke scenarios:

- `kernel_demo.single_action_smoke_v1`
- `kernel_demo.multi_step_workflow_smoke_v1`
- `kernel_demo.quota_exhausted_smoke_v1`
- `kernel_demo.handoff_smoke_v1`, implemented as source and target sessions where useful

The multi-step smoke workflow should exercise:

```text
text.extract_structured_fields
-> text.detect_issues_by_taxonomy
-> document.generate_from_template
```

## MVP-A2 CE Kit

MVP-A2 owns shared `packages/frontend/ce-kit`; MVP-B must not copy API/session/quota/result/handoff
code across CEs. Product-specific Chrome Extensions remain owned by Freelancer Suite.

Required kit capabilities:

- `createGuestIdentity()`
- `getRuntimeConfig()`
- `startScenario()`
- `pollScenarioSession()`
- `getScenarioSession()`
- `getResult()`
- `createHandoff()`
- `openHandoffConsent()`
- `captureEmail()`
- `trackClientEvent()`
- `renderQuotaState()`
- `renderJobStatus()`
- `renderError()`

Guest quota is backend-enforced. Chrome Extensions may store the opaque guest id locally, but quota
is checked and consumed by the backend on accepted scenario start, not on frontend click and not from
provider usage or retry telemetry.

A13 is backend-complete for guest identity/quota. In MVP-A2, A15a delivered the shared client/storage
foundation, A15b delivered real quota/start/polling helpers, guest-id propagation, typed
`429 quota_exhausted` handling and CE-kit integration tests, and A15c owns result fetching over the
A12b frontend-safe result API. A18 owns shared client handoff integration.

## MVP-A2 Web Host

The existing `apps/web-mirror` is the shared multi-product web host. Shared product runtime must not
import individual product definitions or contain Freelancer product meaning. Product pages are
composed under:

```text
/products/{product_id}
```

Shared routes remain:

- `/r/{artifact_id}`
- `/handoff/{handoff_token}`
- `/paywall/{product_id}`
- `/onboarding/{product_id}`

The web host must not become a user dashboard and is not a prerequisite for MVP-A1. It reuses
frontend-safe platform contracts and must not own prompts, workflows, provider/model choice, quota,
scenario state, artifacts, or handoffs.

Web-to-web handoff uses the existing backend-owned bearer token and same-tab navigation. The first
validation set supports only `immediate` target start. Deferred continuation stays out of the first
web release.

## Event Taxonomy

MVP-A platform events:

- `guest.created`
- `product.opened`
- `quota.checked`
- `quota.consumed`
- `quota.exhausted`
- `email_capture.submitted`
- `paywall.shown`
- `waitlist.intent_submitted`
- `scenario.started`
- `scenario.checkpoint_reached`
- `scenario.completed`
- `scenario.failed`
- `workflow.started`
- `workflow.canceled`
- `workflow.succeeded`
- `workflow.failed`
- `action.started`
- `action.succeeded`
- `action.failed`
- `provider.request_started`
- `provider.request_succeeded`
- `provider.request_failed`
- `artifact.created`
- `handoff.created`
- `handoff.viewed`
- `handoff.accepted`
- `handoff.declined`
- `handoff.consumed`
- `client.result_copied`
- `client.next_action_clicked`

Product-specific events begin in MVP-B. `client.result_copied` remains reserved in the taxonomy but
has no live producer and is not used by v1 metrics. ProposalAI v1 defines activation as successful
copy-button use recorded through `client.next_action_clicked` with `next_action_id=copy_result`.

## Delivery Sequence

1. Contracts and config loader.
2. Runtime storage and event log.
3. Provider gateway and structured output.
4. Action runner and first atom definitions.
5. Workflow runner.
6. Scenario runtime.
7. Guest quota and backend handoff core.
8. All 11 strict atom contracts, prompts, configs, and deterministic fixtures.
9. Eleven standalone and three composite runtime proofs.
10. Frontend-safe result API, `atoms-proof`, and live-provider canary.
11. MVP-A1 release gate.
12. Shared client scenario/result/handoff contracts.
13. Web host result, consent, paywall, onboarding, and product-route foundation.
14. Kernel demo CE as reference integration; product CEs remain optional.
15. MVP-A2 client/browser release gate.

## MVP-A1 Definition Of Done

MVP-A1 is complete when:

- backend starts and validates configs
- runtime DB tables exist for sessions, jobs, actions, artifacts, and events
- generic action runner exists
- provider gateway exists
- structured output validation exists
- workflow runner exists
- every scenario start creates `scenario_session_id`
- artifact storage exists
- event log exists
- guest quota exists
- all 11 atom action types are registered and runnable
- every atom passes the deterministic standalone matrix
- three composite workflows use all 11 atoms with real mappings
- `GET /v1/results/{artifact_id}` exposes only normalized canonical results
- `atoms-proof` reports 11/11 and 3/3 with auditable rows/events/artifacts
- a recent live-provider canary proves schema-valid execution for all 11 atoms
- no web mirror, CE, email/paywall UI, or handoff-consent dependency exists in the A1 gate

## MVP-A2 Definition Of Done

MVP-A2 is complete when:

- shared client contracts cover guest identity, quota, idempotent start, polling, result, next
  actions, client events, and handoff helpers
- the web host supports normalized product, result, consent, paywall, and onboarding states
- backend email/paywall intent contracts support the client conversion journey
- kernel demo CE runs through CE-kit without prompts or provider/model controls
- frontend checks and browser evidence pass

## MVP-B Scope

MVP-B adds product-level assets only:

- product configs
- product prompts
- product schemas
- product workflows
- product-specific action configs
- web product definitions and pages
- result renderers
- handoff maps
- product events

The validation set contains six web products. Each product needs a product bundle/workflow and one
complete web runtime E2E/QA vertical. A dedicated Chrome Extension is not part of the default product
Definition of Done.

Product bundle work depends on MVP-A1 and the required atom packs. Web product work depends on its
bundle and the required MVP-A2 shared client/web-host slices.

Product delivery must not add product semantics to `platform-core` or change atoms, workflow runner,
action runner, Provider Gateway, scenario/quota/handoff runtime, or mapping DSL. Product-neutral
Client Surfaces enablement, including the allowlisted `POST /v1/client-events` contract, belongs to
MVP-A2 and may change `apps/platform-api`, the platform event taxonomy/service, and shared frontend
clients without introducing product-specific backend behavior.

## MVP-B Validation Set And Order

1. ProposalAI: `A06` / `text.compose_persuasive_text`.
2. Client Update Writer: `A07` / `text.compose_reply`, with PrepaidRequest and ReplyDraft as modes.
3. Brief Decoder: `A01 + A04 -> A05`, results to `A10`.
4. Acceptance Builder: `A01 + A11` or `A02`, results to `A10`.
5. Task Finder: `A11 + A02`, with `A01` and `A09` optional.
6. Send-Ready: `A04 + A03`, then a user-selected gap to `A08` in a second scenario run.

ProposalAI is first because one scenario and one atom prove the complete web path quickly. Client
Update Writer is second to prove reuse before a shared abstraction is extracted. Brief Decoder to
Acceptance Builder is the first `immediate` same-tab handoff: the CTA creates an editable draft and
does not represent final approval. Task Finder proves score-based activation. Send-Ready is the final
validation product because it proves the two-run selected-gap flow without extending mapping DSL.

The 21 concepts in `atom-ready-product-inventory.md` are a capability inventory, not 21 committed
releases and not an alternative delivery order.

## Scope Protection

Do not say: "Let's build this like ProposalAI / Send-Ready / Brief Decoder."

Say: "Let's verify whether the kernel can run this as a config-defined workflow."

Everything that knows Freelancer product meaning or implements a product-specific web page or Chrome
Extension belongs in MVP-B. Everything that runs atoms, workflows, scenario sessions, events,
artifacts, quota, frontend-safe results, and backend handoff belongs in Platform Core. Shared client
contracts, the multi-product web host, and shared browser journeys belong in MVP-A2 Client Surfaces.
