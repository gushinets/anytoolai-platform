# MVP Scope Source Of Truth

This file mirrors the controlling concept document for AnytoolAI MVP-A and MVP-B scope:

```text
D:\Work\AI\AnytoolAI\platform concept\anytoolai-mvp-a-platform-kernel-and-mvp-b-freelancer-validation-bundle.md
```

Keep `AGENTS.md`, `ARCHITECTURE.md`, `docs/**`, configs, tests, and scaffold aligned with this summary. The external concept file remains the source for nuance; this repo-local file exists so future agents can work from repository context.

## Delivery Split

The accepted MVP-A scope is delivered through two sequential milestones:

- **MVP-A1 — Atom Runtime Proof:** the smallest product-neutral backend runtime that can launch all
  11 typed atoms individually and in config-defined composite workflows, persist auditable runtime
  state, and expose normalized results without a UI dependency.
- **MVP-A2 — Client Surfaces:** shared CE-kit, web mirror, handoff consent, paywall/onboarding,
  kernel-demo Chrome Extension, and browser evidence over frontend-safe Platform Core APIs.

MVP-B is Freelancer Validation Bundle: thin CE-first Freelancer products added on top of the kernel through product configs, prompts, schemas, workflows, result renderers, handoff maps, product events, and separate Chrome Extensions.

MVP-B bundle/workflow work may begin after MVP-A1. Product Chrome Extension work depends on the
required MVP-A2 CE-kit slices, not on web mirror completion. If the first real Freelancer bundle
cannot be added without changing `platform-core`, MVP-A1 is not complete.

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
- minimal web mirror result, handoff, paywall, and onboarding pages
- handoff CE helpers and web consent
- email capture/paywall client journey over Platform Core backend contracts
- `kernel-demo-ce`
- frontend build, integration, and browser evidence

## MVP-A Out Of Scope

- real Freelancer products as user releases
- eight production Chrome Extensions
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

## MVP-A2 Web Mirror

MVP-A2 web mirror pages:

- `/r/{artifact_id}`
- `/handoff/{handoff_token}`
- `/paywall/{product_id}`
- `/onboarding/{product_id}`

Web mirror must not become a user dashboard and is not a prerequisite for MVP-A1 or for an
individual Freelancer product Chrome Extension.

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

Product-specific events begin in MVP-B.

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
12. CE-kit scenario/result/handoff clients.
13. Web mirror, paywall/onboarding, and kernel demo CE.
14. MVP-A2 client/browser release gate.

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

- shared CE-kit covers guest identity, quota, idempotent start, polling, result, and handoff helpers
- web mirror supports normalized result, consent, paywall, and onboarding states
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
- CE wrappers
- CE product UX
- result renderers
- handoff maps
- product events

Each of the eight product issues is a coordinating parent with exactly three delivery children:

1. `Bundle And Workflow` for configs, prompts, strict schemas, renderer contract, and fixtures.
2. `Chrome Extension` for the dedicated product surface using CE-kit.
3. `Runtime E2E And QA` for the complete deterministic product vertical.

Product bundle children depend on MVP-A1 and the required atom packs. Product Chrome Extension
children depend on their bundle and the required MVP-A2 CE-kit slices, but never on web mirror.
Product parents complete only when all three children complete.

MVP-B must not change `platform-core`. It is undesirable for MVP-B to change workflow runner, action runner, provider/scenario/event/quota/handoff kernel modules, or to add product-specific backend endpoints.

## MVP-B Products And Order

1. ProposalAI: `A06` / `text.compose_persuasive_text`
2. Acceptance Builder: `A01 + A07 + A10`
3. Case Study + Upsell: `A01 + A09 + A07 + A10`
4. Scope Guard: `A01 + A04 + A11 + A07`
5. Task Finder: `A01 + A11 + A02 + A09`
6. Send-Ready: `A04 + A11 + A02 + A08`
7. Brief Decoder: `A01 + A04 + A05 + A10`
8. Persuasion Lens: `A03 + A04 + A09 + A08 + A06`

ProposalAI is the first real MVP-B product after the kernel because it uses one workflow and one atom, proves the CE path quickly, and gives a clear `result copied` aha moment.

## Scope Protection

Do not say: "Let's build this like ProposalAI / Send-Ready / Brief Decoder."

Say: "Let's verify whether the kernel can run this as a config-defined workflow."

Everything that knows Freelancer product meaning or implements a product-specific Chrome Extension
belongs in MVP-B. Everything that runs atoms, workflows, scenario sessions, events, artifacts,
quota, frontend-safe results, and backend handoff belongs in Platform Core. Shared CE-kit, web
mirror, and shared client journeys belong in MVP-A2 Client Surfaces.
